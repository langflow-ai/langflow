"""Cold-start benchmark driver.

Orchestrates hyperfine + pyinstrument + `python -X importtime` captures for
the all scenarios scenario set. Produces:
  - `reports/<scenario>.json`: hyperfine wall-clock JSON.
  - `reports/<scenario>.html`: pyinstrument HTML profile (where enabled).
  - `reports/<scenario>.importtime.log`: raw `python -X importtime` trace.
  - `reports/<scenario>.speedscope.json` + `.importtime.json`: sidecar
    conversions via importtime-convert.
  - `reports/<scenario>_checkpoints.json`: lfx._bench checkpoint dump (where
    captured).
  - `{baseline_dir}/baseline-YYYY-MM-DD.md`: human-readable baseline narrative.
  - `{baseline_dir}/baseline-YYYY-MM-DD.json`: machine-readable sidecar with
    `measurement_mode: "bytecode_compile_delta"` at the top level.

Bytecode-variant production (Option A1 per 01-CONTEXT.md). Plan 04's landed
Dockerfile is NOT modified. Instead this driver generates a thin wrapper
Dockerfile ON TOP of the landed `benchmarks-lean` image that strips
`__pycache__`/`.pyc`/`.pyo` from `/app/.venv` and tags the result as
`benchmarks-lean-uncompiled`. The prebaked measurement variant is the landed
`benchmarks-lean` image AS-IS (the Dockerfile's `UV_COMPILE_BYTECODE=1` ENV
already produced .pyc during uv sync). The landed `benchmarks-prebaked` image
is NOT used here because its `uv pip install openai...` step is the wrong
differentiator  (dep-install is not the MEAS-07 signal; bytecode
compile cost is).

--verify mode is the CI-gate backend. It reads `thresholds.json`, compares the
current run's means against the stored baseline, warns on `measurement_mode`
mismatch without failing, exits non-zero on any `delta_pct >
allowed_regression_pct/100`, and writes `reports/regression_comment.md` on
failure. Plan 06's workflow `gh pr comment --body-file` step consumes this
file.

Container runtime auto-detection: prefers podman (local dev) and falls back
to docker (CI). Override via `CONTAINER_CMD` env var.

The word `dep-install` appears in this file only in comments that explain why
it is NOT the differentiator (see D-12a). It never appears in user-visible
narrative strings.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

# Module-level import of scenario definitions. Lean import cost because scenarios are
# plain dataclasses with no heavy deps.
from src.backend.tests.benchmarks.scenarios import (
    Scenario,
)
from src.backend.tests.benchmarks.scenarios import (
    langflow_run as _scen_langflow_run,
)
from src.backend.tests.benchmarks.scenarios import (
    langflow_run_no_change_restart as _scen_langflow_run_no_change_restart,
)
from src.backend.tests.benchmarks.scenarios import (
    lfx_bare as _scen_lfx_bare,
)
from src.backend.tests.benchmarks.scenarios import (
    lfx_reference_image as _scen_lfx_reference_image,
)
from src.backend.tests.benchmarks.scenarios import (
    lfx_with_flow as _scen_lfx_with_flow,
)

# Measurement-mode tag. The value is fixed for this driver version; Phase 6 diffs
# can read it from baseline JSON and thresholds.json to detect a mode change.
MEASUREMENT_MODE = "bytecode_compile_delta"

# Image tags produced/used by the driver.
IMG_BASE_LEAN = "benchmarks-lean"  # landed image, bytecode present (UV_COMPILE_BYTECODE=1).
IMG_UNCOMPILED = "benchmarks-lean-uncompiled"  # derived, .pyc stripped.
IMG_LFX_REFERENCE = "lfx-reference"  # lfx reference image built from src/lfx/docker/Dockerfile (CNT-01 / D-13).

REPO_ROOT = Path(__file__).resolve().parents[4]
BENCHMARKS_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BENCHMARKS_DIR / "reports"
DEFAULT_BASELINE_DIR = REPO_ROOT / ".planning" / "benchmarks"
DEFAULT_THRESHOLDS_PATH = BENCHMARKS_DIR / "thresholds.json"

# Exit code for verify-mode regression detected. Distinct from 1 (generic failure) so the
# CI workflow can distinguish "driver crashed" from "gate tripped".
EXIT_VERIFY_REGRESSION = 3


# ---------------------------------------------------------------------------
# Container runtime auto-detection.
# ---------------------------------------------------------------------------


def detect_container_cmd() -> str:
    """Return the container engine executable to use.

    Order of resolution:
      1. $CONTAINER_CMD if set (explicit override).
      2. shutil.which("podman") (local dev on this machine uses podman).
      3. shutil.which("docker") (CI runners use docker).
      4. Fall back to "docker" as a literal (will fail with a clear error at runtime).
    """
    explicit = os.environ.get("CONTAINER_CMD")
    if explicit:
        return explicit
    for candidate in ("podman", "docker"):
        found = shutil.which(candidate)
        if found:
            return found
    return "docker"


CONTAINER_CMD = detect_container_cmd()


# ---------------------------------------------------------------------------
# Scenario registry.
# ---------------------------------------------------------------------------


def all_scenarios() -> list[Scenario]:
    """Return the full set of scenarios the driver knows about.

    Order matters for the baseline doc: lfx_bare (floor), lfx_with_flow (primary MEAS-07
    lean variant), lfx_with_flow_prebaked (prebaked compiled variant for the delta),
    langflow_run_http_ready (terminal / integration scenario), and
    langflow_run_no_change_restart (Phase 4 SVC-01 two-boot restart scenario).
    """
    return [
        _scen_lfx_bare.SCENARIO,
        _scen_lfx_with_flow.SCENARIO_LEAN,
        _scen_lfx_with_flow.SCENARIO_PREBAKED,
        _scen_langflow_run.SCENARIO,
        _scen_langflow_run_no_change_restart.SCENARIO,
        _scen_lfx_reference_image.SCENARIO,
    ]


def select_scenarios(names: Iterable[str] | None) -> list[Scenario]:
    """Return the subset of scenarios whose name appears in `names` (or all if names is None)."""
    pool = all_scenarios()
    if names is None:
        return pool
    wanted = set(names)
    missing = wanted - {s.name for s in pool}
    if missing:
        msg = f"unknown scenarios: {sorted(missing)}"
        raise SystemExit(msg)
    return [s for s in pool if s.name in wanted]


# ---------------------------------------------------------------------------
# Image tag mapping. Option A1 /D-12a.
# ---------------------------------------------------------------------------


def _image_tag(variant: str) -> str:
    """Map a scenario variant string to an actual image tag.

    - variant="lean"     -> benchmarks-lean-uncompiled (pyc stripped; produced on-the-fly).
    - variant="prebaked" -> benchmarks-lean (landed image, bytecode present from uv sync).

    The landed `benchmarks-prebaked` image is NOT referenced here (wrong differentiator per
    D-12a; its uv pip install of openai etc. measures dep-install cost, which is superseded
    by the bytecode-compile framing).
    """
    if variant == "lean":
        return IMG_UNCOMPILED
    if variant == "prebaked":
        return IMG_BASE_LEAN
    if variant == "lfx_reference":
        return IMG_LFX_REFERENCE
    msg = f"unknown scenario variant: {variant!r}"
    raise ValueError(msg)


def _uncompiled_dockerfile_body() -> str:
    """Generated wrapper Dockerfile content. Static (no user-controlled interpolation)."""
    return (
        "# Generated by driver.py. Do not edit.\n"
        "# Purpose: strip bytecode from landed benchmarks-lean image to produce the D-11a uncompiled variant.\n"
        f"FROM {IMG_BASE_LEAN}\n"
        "RUN find /app/.venv -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true \\\n"
        "    && find /app/.venv -name '*.pyc' -delete \\\n"
        "    && find /app/.venv -name '*.pyo' -delete\n"
    )


def build_uncompiled_image(*, skip_build: bool, verbose: bool = False) -> None:
    """Produce the `benchmarks-lean-uncompiled` image.

    If `skip_build=True`, just confirms the image already exists and returns.
    Otherwise writes the wrapper Dockerfile to a tmp path and runs `<container> build`.
    """
    if skip_build:
        rc = subprocess.run(  # noqa: S603
            [CONTAINER_CMD, "image", "inspect", IMG_UNCOMPILED],
            check=False,
            capture_output=True,
        )
        if rc.returncode != 0:
            msg = (
                f"--skip-build was passed but image {IMG_UNCOMPILED!r} does not exist. "
                f"Run the driver without --skip-build first so it can build the wrapper image."
            )
            raise SystemExit(msg)
        if verbose:
            sys.stderr.write(f"skip-build: {IMG_UNCOMPILED} already present\n")
        return

    # Confirm the base image exists before attempting the wrapper build.
    base_check = subprocess.run(  # noqa: S603
        [CONTAINER_CMD, "image", "inspect", IMG_BASE_LEAN],
        check=False,
        capture_output=True,
    )
    if base_check.returncode != 0:
        msg = (
            f"base image {IMG_BASE_LEAN!r} not found. Build it with:\n"
            f"  {CONTAINER_CMD} build --build-arg BENCH_VARIANT=lean "
            f"-t {IMG_BASE_LEAN} -f src/backend/tests/benchmarks/Dockerfile ."
        )
        raise SystemExit(msg)

    with tempfile.TemporaryDirectory() as tmpdir:
        dockerfile = Path(tmpdir) / "Dockerfile.uncompiled"
        dockerfile.write_text(_uncompiled_dockerfile_body(), encoding="utf-8")
        cmd = [
            CONTAINER_CMD,
            "build",
            "-f",
            str(dockerfile),
            "-t",
            IMG_UNCOMPILED,
            str(REPO_ROOT),
        ]
        if verbose:
            sys.stderr.write(f"+ {' '.join(cmd)}\n")
        rc = subprocess.run(cmd, check=False)  # noqa: S603
        if rc.returncode != 0:
            msg = f"failed to build {IMG_UNCOMPILED!r} (exit {rc.returncode})"
            raise SystemExit(msg)


# ---------------------------------------------------------------------------
# hyperfine wrapper.
# ---------------------------------------------------------------------------


def _env_args(env: dict[str, str]) -> list[str]:
    """Translate a scenario env dict into `-e KEY=VAL` args for `docker run`."""
    out: list[str] = []
    for key, value in env.items():
        out.extend(["-e", f"{key}={value}"])
    return out


def _docker_run_cmd(
    *,
    scenario: Scenario,
    image: str,
    output_dir: Path,
    command: list[str] | None = None,
    state_dir: Path | None = None,
    container_name: str = "lfx-bench",
) -> list[str]:
    """Build the `docker run` argv for hyperfine to invoke.

    When the scenario captures checkpoints we wrap the command in `sh -c "... && cp ..."`
    so the checkpoint JSON file (written by lfx._bench.dump inside the container) is copied
    out to the bind-mounted /out path before container exit.

    ``command`` defaults to ``scenario.command``; callers may override (e.g. for a
    ``prewarm_command`` invocation) without touching the frozen Scenario object.

    ``state_dir`` opts into a second bind mount at ``/bench-state`` and exports
    ``BENCH_STATE_DIR=/bench-state`` into the container. Scenarios that declare a
    ``prewarm_command`` use this so the pre-warm step and the measured step share a
    persistent working directory across ``docker run --rm`` boundaries.

    Note: subprocess is always invoked with an argv list (never a shell). The `sh -c`
    invocation is a child of the container, not of the host; the host-side subprocess.run
    call uses the explicit argv form with no shell wrapping.
    """
    effective_command = command or scenario.command
    env = dict(scenario.env)
    extra_mounts: list[str] = []
    if state_dir is not None:
        state_dir.mkdir(parents=True, exist_ok=True)
        extra_mounts.extend(["-v", f"{state_dir}:/bench-state"])
        env.setdefault("BENCH_STATE_DIR", "/bench-state")
    # The lfx-reference image is the production image: no uv, no baked-in /fixtures.
    # Bind-mount the benchmarks fixtures directory so `lfx run /fixtures/<flow>.json`
    # works identically to the benchmarks-lean variants (which have /fixtures as a
    # symlink built into the image).
    if scenario.variant == "lfx_reference":
        fixtures_dir = BENCHMARKS_DIR / "fixtures"
        extra_mounts.extend(["-v", f"{fixtures_dir}:/fixtures:ro"])
    base = [
        CONTAINER_CMD,
        "run",
        "--rm",
        "--name",
        container_name,
        "-v",
        f"{output_dir}:/out",
        *extra_mounts,
        *_env_args(env),
        image,
    ]
    if scenario.captures_checkpoints:
        inner = " ".join(_quote(tok) for tok in effective_command)
        cp = f"&& cp /tmp/checkpoints.json /out/{scenario.name}_checkpoints.json 2>/dev/null || true"
        sh_cmd = f"{inner} {cp}"
        return [*base, "sh", "-c", sh_cmd]
    return [*base, *effective_command]


def _quote(token: str) -> str:
    """Shell-quote a token for use inside a `sh -c` argument."""
    if not token or any(c.isspace() or c in "\"'\\$`;&|><" for c in token):
        escaped = token.replace("'", "'\"'\"'")
        return f"'{escaped}'"
    return token


def _run_self_measuring(scenario: Scenario, *, output_dir: Path) -> dict:
    """Run a self-measuring scenario inside one docker container; no hyperfine wrapping.

    Self-measuring scenarios execute their own pre-warm + measurement loop inside
    the container and write a hyperfine-compatible JSON report to
    ``$BENCH_OUTPUT_JSON`` (bind-mounted to the host reports dir). This keeps
    iteration output visible in CI logs, which hyperfine's stdout capture does
    not allow.
    """
    image = _image_tag(scenario.variant)
    # State directory is hidden so `actions/upload-artifact` (configured with
    # include-hidden-files: false) skips it. This matters because the container
    # writes files as root; uploading them would trip EACCES in the zip step.
    state_dir = output_dir / f".{scenario.name}.state"
    export_path = output_dir / f"{scenario.name}.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    # Clear any stale export from a prior run so we can detect non-writes.
    if export_path.exists():
        export_path.unlink()
    # The supervisor resolves the output path from BENCH_OUTPUT_JSON. /out is
    # already bind-mounted to output_dir, so the file will land on the host.
    env_overrides = dict(scenario.env)
    env_overrides["BENCH_OUTPUT_JSON"] = f"/out/{scenario.name}.json"
    # Build a synthetic Scenario view with the merged env for _docker_run_cmd.
    scenario_with_env = replace(scenario, env=env_overrides)
    docker_cmd = _docker_run_cmd(
        scenario=scenario_with_env,
        image=image,
        output_dir=output_dir,
        state_dir=state_dir,
    )
    rc = subprocess.run(docker_cmd, check=False)  # noqa: S603
    if rc.returncode != 0:
        sys.stderr.write(
            f"self-measuring scenario {scenario.name!r} failed (exit {rc.returncode})\n",
        )
        return {"error": f"self-measuring exit {rc.returncode}", "scenario": scenario.name}
    if not export_path.exists():
        sys.stderr.write(
            f"self-measuring scenario {scenario.name!r} produced no report at {export_path}\n",
        )
        return {"error": "self-measuring: report missing", "scenario": scenario.name}
    return json.loads(export_path.read_text(encoding="utf-8"))


def run_hyperfine(scenario: Scenario, *, output_dir: Path, warmup: int, min_runs: int, max_runs: int) -> dict:
    """Run hyperfine for one scenario; return the parsed --export-json payload.

    Pitfall 1 (--warmup 0): the default --warmup 3 would defeat cold-start measurement.
    Pitfall 2 (--timer coarse applies to pyinstrument, not hyperfine): see run_pyinstrument.
    D-07 (--prepare docker rm): forces a fresh container per iteration.

    When ``scenario.self_measuring`` is True, the scenario runs its own measurement
    harness inside one container and we return its hyperfine-format report
    directly, skipping the hyperfine wrapping entirely.

    When the scenario declares ``prewarm_command``, we allocate a host-side state
    directory and:
      * bind-mount it at ``/bench-state`` in every docker run (main + prewarm)
      * invoke the pre-warm container once via hyperfine ``--setup``

    This keeps the measured iteration to a single boot that exercises the
    cache-hit path while the pre-warm cost is paid exactly once per invocation.
    """
    if scenario.self_measuring:
        return _run_self_measuring(scenario, output_dir=output_dir)

    image = _image_tag(scenario.variant)
    state_dir: Path | None = None
    setup_string: str | None = None
    if scenario.prewarm_command:
        # Hidden so upload-artifact's include-hidden-files: false skips root-owned files.
        state_dir = output_dir / f".{scenario.name}.state"
        prewarm_docker = _docker_run_cmd(
            scenario=scenario,
            image=image,
            output_dir=output_dir,
            command=scenario.prewarm_command,
            state_dir=state_dir,
            container_name=f"lfx-bench-prewarm-{scenario.name}",
        )
        setup_string = " ".join(_quote(tok) for tok in prewarm_docker)

    docker_run = _docker_run_cmd(
        scenario=scenario,
        image=image,
        output_dir=output_dir,
        state_dir=state_dir,
    )
    # --prepare must be a single shell command; hyperfine parses it via --shell sh.
    prepare = f"{CONTAINER_CMD} rm -f lfx-bench 2>/dev/null || true"
    # Build the single shell-string form of the docker-run command for hyperfine's arg.
    run_string = " ".join(_quote(tok) for tok in docker_run)

    export_path = output_dir / f"{scenario.name}.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "hyperfine",
        "--warmup",
        str(warmup),
        "--min-runs",
        str(min_runs),
        "--max-runs",
        str(max_runs),
        "--prepare",
        prepare,
        "--export-json",
        str(export_path),
        "--shell",
        "sh",
    ]
    if setup_string is not None:
        cmd.extend(["--setup", setup_string])
    cmd.append(run_string)
    rc = subprocess.run(cmd, check=False)  # noqa: S603
    if rc.returncode != 0:
        sys.stderr.write(f"hyperfine failed for scenario {scenario.name!r} (exit {rc.returncode})\n")
        return {"error": f"hyperfine exit {rc.returncode}", "scenario": scenario.name}
    return json.loads(export_path.read_text(encoding="utf-8"))


def run_hyperfine_local(scenario: Scenario, *, output_dir: Path, warmup: int, min_runs: int, max_runs: int) -> dict:
    """Local-mode variant: no docker wrapper; runs scenario.command directly against the host venv.

    Non-authoritative per the baseline document marks any local-mode results as smoke only.
    """
    export_path = output_dir / f"{scenario.name}.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    # In local mode /fixtures is not bind-mounted and /app is not the repo root.
    # Remap both prefixes so lfx scenarios resolve their fixture and bootstrap paths.
    local_fixtures = str(BENCHMARKS_DIR / "fixtures")
    local_app = str(REPO_ROOT)

    def _remap(s: str) -> str:
        return s.replace("/fixtures/", f"{local_fixtures}/").replace("/app/", f"{local_app}/")

    local_cmd = [_remap(tok) for tok in scenario.command]
    local_env = {k: _remap(v) for k, v in scenario.env.items()}

    # Flatten env into a shell prefix string. --shell sh parses this cleanly.
    env_prefix = " ".join(f"{k}={_quote(v)}" for k, v in local_env.items())
    run_string = f"{env_prefix} {' '.join(_quote(tok) for tok in local_cmd)}"

    cmd = [
        "hyperfine",
        "--warmup",
        str(warmup),
        "--min-runs",
        str(min_runs),
        "--max-runs",
        str(max_runs),
        "--export-json",
        str(export_path),
        "--shell",
        "sh",
        # On macOS, PyTorch background threads crash during Python shutdown (exit 139 = SIGSEGV)
        # after the flow completes correctly. Treat this as success for local smoke benchmarks.
        "--ignore-failure=139",
        run_string,
    ]
    rc = subprocess.run(cmd, check=False)  # noqa: S603
    if rc.returncode != 0:
        sys.stderr.write(f"hyperfine (local) failed for scenario {scenario.name!r} (exit {rc.returncode})\n")
        return {"error": f"hyperfine exit {rc.returncode}", "scenario": scenario.name}
    return json.loads(export_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# pyinstrument + -X importtime.
# ---------------------------------------------------------------------------


def run_pyinstrument(scenario: Scenario, *, output_dir: Path) -> Path | None:
    """Single pyinstrument run per scenario. Pitfall 2: --timer coarse is non-negotiable in docker.

    Returns the HTML path on success, None if pyinstrument was not run.
    """
    if not scenario.captures_pyinstrument:
        return None
    image = _image_tag(scenario.variant)
    html_path = output_dir / f"{scenario.name}.html"

    # Map the scenario's command into a pyinstrument-wrapped invocation. For lfx scenarios the
    # first two tokens are `uv run`, then `lfx run <fixture> --format text`; we replace `lfx run`
    # with `pyinstrument ... -m lfx run` so pyinstrument profiles the Python process.
    #
    # Pitfall 2 (RESEARCH.md) originally called for `--timer coarse`. pyinstrument 5.x does not
    # expose that flag; the equivalent container-slowdown mitigation is `--use-timing-thread`,
    # which decouples the sampler from gettimeofday. See:
    #   https://pyinstrument.readthedocs.io/en/latest/reference.html#command-line-reference
    cmd_argv = scenario.command
    profile_cmd: list[str]
    pyinstrument_prefix = [
        "uv",
        "run",
        "pyinstrument",
        "--use-timing-thread",
        "--renderer",
        "html",
        "--outfile",
        f"/out/{scenario.name}.html",
    ]
    if cmd_argv[:2] == ["uv", "run"] and cmd_argv[2:4] == ["lfx", "run"]:
        profile_cmd = [*pyinstrument_prefix, "-m", "lfx", "run", *cmd_argv[4:]]
    elif cmd_argv[:4] == ["uv", "run", "python", "-m"]:
        # e.g. langflow_run_http_ready: ["uv", "run", "python", "-m", "<module>"]
        # Passing "uv run python -m ..." as-is would make pyinstrument try to exec `uv`
        # directly, which fails because pyinstrument resolves via its own lookup rather
        # than the shell PATH. Translate to `pyinstrument -m <module>` instead.
        profile_cmd = [*pyinstrument_prefix, "-m", *cmd_argv[4:]]
    else:
        profile_cmd = [*pyinstrument_prefix, *cmd_argv]

    cmd = [
        CONTAINER_CMD,
        "run",
        "--rm",
        "-v",
        f"{output_dir}:/out",
        *_env_args(scenario.env),
        image,
        *profile_cmd,
    ]
    rc = subprocess.run(cmd, check=False)  # noqa: S603
    if rc.returncode != 0:
        sys.stderr.write(f"pyinstrument failed for {scenario.name!r} (exit {rc.returncode})\n")
        return None
    return html_path


def run_importtime(scenario: Scenario, *, output_dir: Path) -> Path | None:
    """Capture `python -X importtime` trace + convert to speedscope + top-N JSON.

    Returns the raw log path on success.
    """
    if not scenario.captures_importtime:
        return None
    image = _image_tag(scenario.variant)
    log_path = output_dir / f"{scenario.name}.importtime.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # `python` on PATH in the image is the system python and does NOT have lfx installed;
    # `uv run python` activates the /app/.venv where lfx lives. Use uv run here for both.
    sh_cmd = f"uv run python -X importtime -c 'import lfx' 2> /out/{scenario.name}.importtime.log"
    cmd = [
        CONTAINER_CMD,
        "run",
        "--rm",
        "-v",
        f"{output_dir}:/out",
        *_env_args(scenario.env),
        image,
        "sh",
        "-c",
        sh_cmd,
    ]
    rc = subprocess.run(cmd, check=False)  # noqa: S603
    if rc.returncode != 0:
        sys.stderr.write(f"importtime capture failed for {scenario.name!r} (exit {rc.returncode})\n")
        return None

    # Convert via importtime-convert. Best-effort: if the converter is missing, skip conversion.
    # The binary lives in .venv/bin/, so `uv run importtime-convert` is the resolution path
    # when it isn't on PATH. importtime-convert 1.1.0 only supports --output-format {flamegraph.pl, json};
    # RESEARCH.md called for a "speedscope" format that isn't available in this release. We emit
    # flamegraph.pl (compatible with standard flame-graph tooling) and json.
    converter = shutil.which("importtime-convert")
    converter_cmd: list[str]
    if converter is not None:
        converter_cmd = [converter]
    else:
        uv = shutil.which("uv")
        if uv is None:
            sys.stderr.write("Neither importtime-convert nor uv found on PATH; skipping conversion.\n")
            return log_path
        converter_cmd = [uv, "run", "importtime-convert"]

    for fmt, suffix in (("flamegraph.pl", "flamegraph.txt"), ("json", "importtime.json")):
        out = output_dir / f"{scenario.name}.{suffix}"
        with log_path.open("rb") as inp, out.open("wb") as outp:
            rc2 = subprocess.run(  # noqa: S603
                [*converter_cmd, "--output-format", fmt],
                stdin=inp,
                stdout=outp,
                check=False,
            )
        if rc2.returncode != 0:
            sys.stderr.write(f"importtime-convert --output-format {fmt} failed for {scenario.name!r}\n")
    return log_path


# ---------------------------------------------------------------------------
# Checkpoint parsing.
# ---------------------------------------------------------------------------


def read_checkpoints(path: Path) -> dict[str, float]:
    """Load a checkpoint JSON file and return a {name: relative_seconds} mapping.

    `relative_seconds` is the offset from `process-start`. If `process-start` is absent,
    the earliest observed timestamp is used as the origin.
    """
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data:
        return {}
    # Find origin.
    origin = None
    for name, ts in data:
        if name == "process-start":
            origin = ts
            break
    if origin is None:
        origin = min(ts for _n, ts in data)
    return {name: (ts - origin) for name, ts in data}


# ---------------------------------------------------------------------------
# MEAS-07 delta (bytecode compile cost; D-11a/D-12a).
# ---------------------------------------------------------------------------


def compute_meas_07(results: dict[str, dict]) -> dict[str, Any]:
    """Compute the bytecode-compile-cost delta.

    results[name] expected to carry mean_ms (ms) for at minimum:
      - `lfx_with_flow` (lean, uncompiled).
      - `lfx_with_flow_prebaked` (prebaked, compiled).

    Returns a dict that goes under `meas_07` in the baseline sidecar. If either scenario
    is missing, returns a dict with `status=incomplete` and a reason string so the baseline
    doc can render a sensible message.
    """
    lean = results.get("lfx_with_flow")
    prebaked = results.get("lfx_with_flow_prebaked")
    if not lean or not prebaked or "mean_ms" not in lean or "mean_ms" not in prebaked:
        return {
            "status": "incomplete",
            "reason": "MEAS-07 requires both lfx_with_flow (lean) and lfx_with_flow_prebaked.",
        }
    lean_mean = lean["mean_ms"]
    prebaked_mean = prebaked["mean_ms"]
    delta_ms = lean_mean - prebaked_mean
    # import_time_ms derives from the LEAN scenario's checkpoint deltas when present.
    import_time_ms = 0.0
    ckp = lean.get("checkpoints") or {}
    if "after-imports" in ckp and "process-start" in ckp:
        import_time_ms = max((ckp["after-imports"] - ckp["process-start"]) * 1000.0, 0.0)
    elif "after-imports" in ckp:
        import_time_ms = max(ckp["after-imports"] * 1000.0, 0.0)

    # Conclusion string (no em-dashes; repo-shipped content).
    if delta_ms > 0 and abs(delta_ms) >= 0.02 * lean_mean:
        conclusion = (
            f"Bytecode compile adds {delta_ms:.0f}ms "
            f"(~{100 * delta_ms / lean_mean:.1f}% of cold start); "
            f"import time remains dominant at {import_time_ms:.0f}ms."
        )
    else:
        conclusion = (
            f"Bytecode compile cost is negligible ({delta_ms:+.0f}ms, <2% of {lean_mean:.0f}ms cold start). "
            f"Import time dominates at {import_time_ms:.0f}ms."
        )
    return {
        "status": "ok",
        "lean_uncompiled_mean_ms": lean_mean,
        "prebaked_compiled_mean_ms": prebaked_mean,
        "bytecode_compile_delta_ms": delta_ms,
        "import_time_ms": import_time_ms,
        "conclusion": conclusion,
    }


# ---------------------------------------------------------------------------
# Baseline writers.
# ---------------------------------------------------------------------------


def _git_rev() -> str:
    git = shutil.which("git")
    if not git:
        return "unknown"
    try:
        out = subprocess.run(  # noqa: S603
            [git, "rev-parse", "HEAD"], check=False, capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        return out.stdout.strip() or "unknown"
    except FileNotFoundError:
        return "unknown"


def _hyperfine_version() -> str:
    hf = shutil.which("hyperfine")
    if not hf:
        return "unknown"
    try:
        out = subprocess.run(  # noqa: S603
            [hf, "--version"], check=False, capture_output=True, text=True
        )
        return out.stdout.strip() or "unknown"
    except FileNotFoundError:
        return "unknown"


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def write_baseline_json(
    *,
    results: dict[str, dict],
    meas_07: dict,
    path: Path,
    captured_on: str,
) -> None:
    """Write the machine-readable baseline sidecar (D-13; includes measurement_mode)."""
    payload: dict[str, Any] = {
        "schema_version": 1,
        "measurement_mode": MEASUREMENT_MODE,
        "captured_on": captured_on,
        "captured_ref": _git_rev(),
        "captured_runner": platform.platform(),
        "python_version": _python_version(),
        "image_tags": {
            "lean_uncompiled": IMG_UNCOMPILED,
            "prebaked_compiled": IMG_BASE_LEAN,
        },
        "hyperfine_version": _hyperfine_version(),
        "scenarios": results,
        "meas_07": meas_07,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_baseline_md(
    *,
    results: dict[str, dict],
    meas_07: dict,
    path: Path,
    captured_on: str,
) -> None:
    """Write the human-readable baseline narrative."""
    lines: list[str] = []
    lines.append(f"# Cold Start Baseline: {captured_on}")
    lines.append("")
    lines.append(f"- captured_on: {captured_on}")
    lines.append(f"- captured_ref: `{_git_rev()}`")
    lines.append(f"- python_version: {_python_version()}")
    lines.append(f"- hyperfine_version: {_hyperfine_version()}")
    lines.append(f"- image_tags: `{IMG_BASE_LEAN}` (prebaked/compiled), `{IMG_UNCOMPILED}` (lean/uncompiled)")
    lines.append(f"- Measurement mode: `{MEASUREMENT_MODE}`")
    lines.append("")
    lines.append("## Wall-clock summary")
    lines.append("")
    lines.append("| scenario | mean ms | stddev | min | max | runs |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for name, data in results.items():
        lines.append(
            f"| {name} | {data.get('mean_ms', 'N/A')} | {data.get('stddev_ms', 'N/A')} | "
            f"{data.get('min_ms', 'N/A')} | {data.get('max_ms', 'N/A')} | {data.get('runs', 'N/A')} |"
        )
    lines.append("")
    lines.append("## Phase breakdown (6-checkpoint)")
    lines.append("")
    lines.append(
        "| scenario | process-start -> after-imports | -> after-initialize-services | -> after-component-index "
        "| -> before-run-flow | -> after-run-flow |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")

    def _ms(ckp_map: dict[str, float], key: str) -> str:
        """Return cumulative-ms-from-start for a named checkpoint, or 'N/A'."""
        if key not in ckp_map:
            return "N/A"
        return f"{ckp_map[key] * 1000.0:.0f}"

    for name, data in results.items():
        ckp = data.get("checkpoints") or {}
        lines.append(
            f"| {name} | {_ms(ckp, 'after-imports')} | {_ms(ckp, 'after-initialize-services')} "
            f"| {_ms(ckp, 'after-component-index')} | {_ms(ckp, 'before-run-flow')} "
            f"| {_ms(ckp, 'after-run-flow')} |"
        )
    lines.append("")
    lines.append("## Import-time hotspots (top N)")
    lines.append("")
    lines.append("See `reports/<scenario>.importtime.json` sidecars for the full table.")
    lines.append("")
    lines.append("## MEAS-07 delta (bytecode compile cost)")
    lines.append("")
    if meas_07.get("status") == "ok":
        lines.append(f"- lean_uncompiled_mean_ms: {meas_07['lean_uncompiled_mean_ms']}")
        lines.append(f"- prebaked_compiled_mean_ms: {meas_07['prebaked_compiled_mean_ms']}")
        lines.append(f"- bytecode_compile_delta_ms: {meas_07['bytecode_compile_delta_ms']}")
        lines.append(f"- import_time_ms: {meas_07['import_time_ms']}")
        lines.append("")
        lines.append(f"**Conclusion:** {meas_07['conclusion']}")
    else:
        lines.append(f"MEAS-07 status: {meas_07.get('status')} ({meas_07.get('reason', 'no details')}).")
    lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    for name in results:
        lines.append(f"- `reports/{name}.json`")
        lines.append(f"- `reports/{name}.html` (pyinstrument)")
        lines.append(f"- `reports/{name}.importtime.log`")
        lines.append(f"- `reports/{name}.speedscope.json`")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    lines.append("- IDX-01 reproduction: TBD (see Pitfall 8 / Open Question 1).")
    lines.append("- Observed hotspots vs CONCERNS.md prediction: TBD.")
    lines.append("- Anomalies: TBD.")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# --verify mode: compare against thresholds.json.
# ---------------------------------------------------------------------------


@dataclass
class _VerifyRow:
    scenario: str
    baseline_ms: float
    current_ms: float
    delta_pct: float
    allowed_pct: float
    status: str


def compare_against_thresholds(
    current_results: dict[str, dict],
    thresholds_path: Path,
    output_dir: Path,
) -> int:
    """Compare current_results means to thresholds.json; return exit code.

    Behavior:
      - measurement_mode mismatch -> stderr WARNING only (not a failure; see D-11a note).
      - any scenario delta_pct > allowed_regression_pct/100 -> exit code EXIT_VERIFY_REGRESSION.
      - baseline runs == 0 AND mean_ms <= 0 -> UNANCHORED (scenario exists in
        thresholds.json as a placeholder but has never been snapshotted); the
        row is recorded with status SKIP and does not trip the gate. A new
        scenario can land in thresholds.json alongside its code change without
        failing its first real measurement.
      - baseline mean_ms <= 0 (with runs > 0) -> FAIL on any finite current
        mean (Path-B sentinel trip: intentionally-zeroed baseline).
      - on any FAIL, write reports/regression_comment.md.
      - on all PASS/SKIP, no regression_comment.md file is written.
    """
    if not thresholds_path.exists():
        sys.stderr.write(
            f"thresholds.json not found at {thresholds_path}. "
            f"Run `uv run python -m src.backend.tests.benchmarks.snapshot` first to produce it.\n"
        )
        return EXIT_VERIFY_REGRESSION

    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
    allowed_pct = thresholds.get("allowed_regression_pct", 15) / 100.0
    mode = thresholds.get("measurement_mode")
    if mode and mode != MEASUREMENT_MODE:
        sys.stderr.write(
            f"WARNING: thresholds.json measurement_mode={mode!r} differs from driver "
            f"measurement_mode={MEASUREMENT_MODE!r}. Comparison is informational; not failing on mismatch.\n"
        )

    rows: list[_VerifyRow] = []
    any_fail = False
    for name, t_entry in (thresholds.get("scenarios") or {}).items():
        current = current_results.get(name)
        if not current:
            continue
        baseline_ms = float(t_entry.get("mean_ms", 0.0))
        baseline_runs = int(t_entry.get("runs", 0) or 0)
        # A scenario whose driver call errored (e.g. hyperfine non-zero exit,
        # docker pull failure, missing report) returns an error-dict with no
        # ``mean_ms`` key. Treat as FAIL — without this guard, ``current.get(
        # "mean_ms", 0.0)`` returns 0.0 → delta_pct = -1.0 → status = PASS, so
        # an infrastructural failure silently passes the regression gate.
        if "error" in current and "mean_ms" not in current:
            rows.append(
                _VerifyRow(
                    scenario=name,
                    baseline_ms=baseline_ms,
                    current_ms=0.0,
                    delta_pct=float("inf"),
                    allowed_pct=allowed_pct,
                    status="FAIL",
                )
            )
            any_fail = True
            continue
        current_ms = float(current.get("mean_ms", 0.0))
        if baseline_ms <= 0.0 and baseline_runs <= 0:
            # Unanchored baseline: scenario is a placeholder that has never been
            # snapshotted. Record the current number for visibility but do not
            # trip the gate — the next snapshot run will anchor it.
            status = "SKIP"
            delta_pct = 0.0
        elif baseline_ms <= 0.0:
            # Sentinel baseline with prior runs: any finite current trips the
            # gate (intentionally-zeroed baseline, Path-B sentinel trip).
            status = "FAIL"
            delta_pct = float("inf") if current_ms > 0 else 0.0
        else:
            delta_pct = (current_ms / baseline_ms) - 1.0
            status = "FAIL" if delta_pct > allowed_pct else "PASS"
        if status == "FAIL":
            any_fail = True
        rows.append(
            _VerifyRow(
                scenario=name,
                baseline_ms=baseline_ms,
                current_ms=current_ms,
                delta_pct=delta_pct,
                allowed_pct=allowed_pct,
                status=status,
            )
        )

    if any_fail:
        _write_regression_comment(
            rows=rows,
            thresholds=thresholds,
            output_path=output_dir / "regression_comment.md",
        )
        return EXIT_VERIFY_REGRESSION
    return 0


def _write_regression_comment(*, rows: list[_VerifyRow], thresholds: dict, output_path: Path) -> None:
    """Emit the GitHub-markdown body consumed by plan 06's `gh pr comment --body-file` step."""
    failed = [r for r in rows if r.status == "FAIL"]
    header = f"## Cold Start Benchmark: regression detected ({len(failed)} scenario(s) failed)"
    lines: list[str] = [header, ""]
    lines.append(
        f"Baseline ref: `{thresholds.get('captured_ref', 'unknown')}` captured "
        f"{thresholds.get('captured_on', 'unknown')} on {thresholds.get('captured_runner', 'unknown')}. "
        f"Allowed regression: {thresholds.get('allowed_regression_pct', 15)}%. "
        f"Measurement mode: `{thresholds.get('measurement_mode', MEASUREMENT_MODE)}`."
    )
    lines.append("")
    lines.append("| scenario | baseline_ms | current_ms | delta_pct | allowed_pct | status |")
    lines.append("|---|---:|---:|---:|---:|:-:|")
    for row in rows:
        dp = "inf" if row.delta_pct == float("inf") else f"{row.delta_pct:+.1%}"
        lines.append(
            f"| {row.scenario} | {row.baseline_ms:.1f} | {row.current_ms:.1f} | "
            f"{dp} | {row.allowed_pct:.0%} | {row.status} |"
        )
    lines.append("")
    lines.append(
        "Hyperfine JSON artifacts: see the `cold-start-benchmark-reports` workflow artifact. "
        "Local paths: `reports/<scenario>.json`."
    )
    lines.append("")
    lines.append(
        "Per to merge anyway, apply the `benchmarks:override` label AND document the "
        "justification in the PR description."
    )
    lines.append("")
    lines.append(f"Measurement mode: {thresholds.get('measurement_mode', MEASUREMENT_MODE)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Orchestrator.
# ---------------------------------------------------------------------------


def _scenario_results(
    scenarios: list[Scenario],
    *,
    mode: str,
    output_dir: Path,
    warmup: int,
    min_runs: int,
    max_runs: int,
) -> dict[str, dict]:
    """Run hyperfine + sidecar captures for every scenario; return a name-keyed dict."""
    results: dict[str, dict] = {}
    for scenario in scenarios:
        runs = max(min_runs, scenario.runs) if scenario.runs >= min_runs else min_runs
        max_r = max(runs, max_runs)
        if mode == "docker":
            hf = run_hyperfine(
                scenario,
                output_dir=output_dir,
                warmup=warmup,
                min_runs=runs,
                max_runs=max_r,
            )
        else:
            hf = run_hyperfine_local(
                scenario,
                output_dir=output_dir,
                warmup=warmup,
                min_runs=runs,
                max_runs=max_r,
            )
        entry: dict[str, Any] = {}
        res_list = hf.get("results") if isinstance(hf, dict) else None
        if res_list:
            first = res_list[0]
            entry["mean_ms"] = first.get("mean", 0.0) * 1000.0
            entry["stddev_ms"] = first.get("stddev", 0.0) * 1000.0
            times = first.get("times") or []
            entry["min_ms"] = (min(times) * 1000.0) if times else 0.0
            entry["max_ms"] = (max(times) * 1000.0) if times else 0.0
            entry["runs"] = len(times)
            if times:
                entry["median_ms"] = statistics.median(times) * 1000.0
        else:
            entry["error"] = hf.get("error") if isinstance(hf, dict) else "unknown failure"

        # Sidecar captures (docker mode only; local mode skips these).
        if mode == "docker":
            run_pyinstrument(scenario, output_dir=output_dir)
            run_importtime(scenario, output_dir=output_dir)

        if scenario.captures_checkpoints:
            ckp_path = output_dir / f"{scenario.name}_checkpoints.json"
            entry["checkpoints"] = read_checkpoints(ckp_path)
        results[scenario.name] = entry
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entry. argv is parsed against the argparse schema below. Returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="driver",
        description="Cold-start benchmark driver (all scenarios). Produces baseline-YYYY-MM-DD artifacts.",
    )
    parser.add_argument("--mode", choices=["docker", "local"], required=True)
    parser.add_argument(
        "--scenarios",
        default=None,
        help=(
            "Comma-separated scenario names (default: all: "
            "lfx_bare,lfx_with_flow,lfx_with_flow_prebaked,langflow_run_http_ready)."
        ),
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--baseline-dir", default=str(DEFAULT_BASELINE_DIR))
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--warmup", type=int, default=0)  # Pitfall 1: default 0.
    parser.add_argument("--min-runs", type=int, default=5)
    parser.add_argument("--max-runs", type=int, default=10)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--thresholds-path", default=str(DEFAULT_THRESHOLDS_PATH))
    args = parser.parse_args(argv)

    # Container bind mounts (`-v <path>:/out`) require absolute paths; relative paths
    # like `reports/` get interpreted as named volumes by podman and fail with a name-
    # validation error. Resolve here so every downstream consumer sees an absolute path.
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir = Path(args.baseline_dir).resolve()

    names = None
    if args.scenarios:
        names = [n.strip() for n in args.scenarios.split(",") if n.strip()]
    scenarios = select_scenarios(names)

    if args.mode == "docker":
        build_uncompiled_image(skip_build=args.skip_build)

    results = _scenario_results(
        scenarios,
        mode=args.mode,
        output_dir=output_dir,
        warmup=args.warmup,
        min_runs=args.min_runs,
        max_runs=args.max_runs,
    )

    meas_07 = compute_meas_07(results)
    # Use timezone-aware now() for DTZ compliance; we only keep the date portion for the filename.
    captured_on = _dt.datetime.now(tz=_dt.timezone.utc).date().isoformat()
    write_baseline_md(
        results=results, meas_07=meas_07, path=baseline_dir / f"baseline-{captured_on}.md", captured_on=captured_on
    )
    write_baseline_json(
        results=results, meas_07=meas_07, path=baseline_dir / f"baseline-{captured_on}.json", captured_on=captured_on
    )

    if args.verify:
        return compare_against_thresholds(
            current_results=results,
            thresholds_path=Path(args.thresholds_path),
            output_dir=output_dir,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

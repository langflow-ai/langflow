"""Run release.yml's RC-numbering steps against fixture PyPI data.

``test_release_workflow.py`` pins the workflow's text; these tests execute the
real ``run:`` scripts, with ``curl`` and ``uv`` stubbed, so a regression in what
the steps compute fails here.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"
TAG_SCRIPT = Path(__file__).resolve().parent / "langflow_pre_release_tag.py"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="the release workflow steps need bash and jq",
)

PROJECT_DIRS = {
    "langflow": ".",
    "langflow-base": "src/backend/base",
    "lfx": "src/lfx",
    "langflow-sdk": "src/sdk",
    "lfx-google": "src/bundles/lfx-google",
}

# PyPI as it stood when release-1.12.2 was cut: the SDK and the bundle rode
# through the 1.12.0 RC cycle and shipped finals that 1.12.2 reuses unchanged.
PYPI_AFTER_1_12_1 = {
    "langflow": [*(f"1.12.0rc{n}" for n in range(5)), "1.12.0", "1.12.1"],
    "langflow-base": [*(f"1.12.0rc{n}" for n in range(5)), "1.12.0", "1.12.1"],
    "lfx": [*(f"1.12.0rc{n}" for n in range(5)), "1.12.0", "1.12.1"],
    "langflow-sdk": [*(f"0.4.0rc{n}" for n in range(5)), "0.4.0"],
    "lfx-google": [*(f"0.1.1rc{n}" for n in range(4)), "0.1.1"],
}
VERSIONS_1_12_2 = {
    "langflow": "1.12.2",
    "langflow-base": "1.12.2",
    "lfx": "1.12.2",
    "langflow-sdk": "0.4.0",
    "lfx-google": "0.1.1",
}
FULL_PRERELEASE_INPUTS = {
    "inputs.release_package_main": "true",
    "inputs.release_package_base": "true",
    "inputs.release_lfx": "true",
    "inputs.release_sdk || inputs.release_lfx": "true",
    "inputs.release_bundles": "true",
    "inputs.build_docker_main": "false",
    "inputs.build_docker_base": "false",
}

# Serves $PYPI_FIXTURES/<package>.json (404 when absent), honouring -o and -w.
# From call number $PYPI_DOWN_FROM_CALL onwards it fails like an unreachable PyPI.
CURL_STUB = """\
#!/usr/bin/env python3
import os, sys
from pathlib import Path

fixtures = Path(os.environ["PYPI_FIXTURES"])
calls = fixtures / ".calls"
call = int(calls.read_text()) + 1 if calls.exists() else 1
calls.write_text(str(call))
down_from = int(os.environ.get("PYPI_DOWN_FROM_CALL", "0"))
if down_from and call >= down_from:
    sys.exit("curl: (7) Failed to connect to pypi.org port 443")

args = sys.argv[1:]
url = next(arg for arg in args if arg.startswith("https://pypi.org/pypi/"))
fixture = fixtures / (url.split("/")[-2] + ".json")
status, body = ("200", fixture.read_text()) if fixture.exists() else ("404", "{}")
if "-o" in args:
    Path(args[args.index("-o") + 1]).write_text(body)
else:
    sys.stdout.write(body)
if "-w" in args:
    sys.stdout.write(status)
"""
UV_STUB = """\
#!/usr/bin/env bash
[ "$1" = run ] || { echo "unexpected uv invocation: $*" >&2; exit 1; }
shift
exec python3 "$@"
"""


def _step_script(job: str, step: str) -> str:
    lines = WORKFLOW_PATH.read_text(encoding="utf-8").splitlines()
    job_at = lines.index(f"  {job}:")
    step_at = next(i for i in range(job_at, len(lines)) if lines[i].strip() == f"- name: {step}")
    run_at = next(i for i in range(step_at, len(lines)) if lines[i].strip() == "run: |")
    run_indent = len(lines[run_at]) - len(lines[run_at].lstrip())
    body = []
    for line in lines[run_at + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= run_indent:
            break
        body.append(line)
    return textwrap.dedent("\n".join(body))


def _render(script: str, expressions: dict[str, str]) -> str:
    def substitute(match: re.Match[str]) -> str:
        expression = match.group(1)
        if expression not in expressions:
            msg = f"unmapped workflow expression: {expression}"
            raise KeyError(msg)
        return expressions[expression]

    return re.sub(r"\$\{\{\s*(.*?)\s*\}\}", substitute, script)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_step(
    tmp_path: Path,
    *,
    job: str,
    step: str,
    expressions: dict[str, str],
    versions: dict[str, str],
    releases: dict[str, list[str]],
    pypi_down_from_call: int = 0,
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    workspace = tmp_path / "repo"
    for package, version in versions.items():
        project = workspace / PROJECT_DIRS[package] / "pyproject.toml"
        project.parent.mkdir(parents=True, exist_ok=True)
        project.write_text(f'[project]\nname = "{package}"\nversion = "{version}"\n', encoding="utf-8")
    (workspace / "scripts" / "ci").mkdir(parents=True)
    shutil.copy(TAG_SCRIPT, workspace / "scripts" / "ci" / TAG_SCRIPT.name)

    fixtures = tmp_path / "pypi"
    fixtures.mkdir()
    for package, released in releases.items():
        (fixtures / f"{package}.json").write_text(json.dumps({"releases": {version: [] for version in released}}))

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "python3", f'#!/usr/bin/env bash\nexec {shlex.quote(sys.executable)} "$@"\n')
    _write_executable(bin_dir / "curl", CURL_STUB)
    _write_executable(bin_dir / "uv", UV_STUB)

    github_output = tmp_path / "github_output"
    github_output.touch()
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(github_output),
        "PYPI_FIXTURES": str(fixtures),
        "PYPI_DOWN_FROM_CALL": str(pypi_down_from_call),
    }
    script = _render(_step_script(job, step), expressions)
    # GitHub runs a step without an explicit `shell:` as `bash -e {0}`.
    result = subprocess.run(  # noqa: S603
        ["bash", "-e", "-c", script],  # noqa: S607
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    outputs = dict(line.split("=", 1) for line in github_output.read_text().splitlines())
    return result, outputs


def _shared_rc_number(tmp_path: Path, versions: dict[str, str], releases: dict[str, list[str]]) -> str:
    result, outputs = _run_step(
        tmp_path,
        job="determine-rc-number",
        step="Determine shared pre-release RC number",
        expressions=FULL_PRERELEASE_INPUTS,
        versions=versions,
        releases=releases,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return outputs["rc_number"]


def _run_sdk_version_step(
    tmp_path: Path,
    versions: dict[str, str],
    releases: dict[str, list[str]],
    rc_number: str,
    pypi_down_from_call: int = 0,
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    return _run_step(
        tmp_path,
        job="determine-sdk-version",
        step="Determine version",
        expressions={"inputs.pre_release": "true", "needs.determine-rc-number.outputs.rc_number": rc_number},
        versions=versions,
        releases=releases,
        pypi_down_from_call=pypi_down_from_call,
    )


def _sdk_version(
    tmp_path: Path, versions: dict[str, str], releases: dict[str, list[str]], rc_number: str
) -> tuple[str, str]:
    result, outputs = _run_sdk_version_step(tmp_path, versions, releases, rc_number)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return outputs["version"], outputs["skipped"]


def test_first_rc_of_a_patch_release_starts_at_rc0(tmp_path: Path) -> None:
    assert _shared_rc_number(tmp_path, VERSIONS_1_12_2, PYPI_AFTER_1_12_1) == "0"


def test_langflow_rc_history_for_the_same_version_raises_the_shared_number(tmp_path: Path) -> None:
    releases = {**PYPI_AFTER_1_12_1, "langflow": [*PYPI_AFTER_1_12_1["langflow"], "1.12.2rc0", "1.12.2rc1"]}

    assert _shared_rc_number(tmp_path, VERSIONS_1_12_2, releases) == "2"


def test_rc_history_of_an_sdk_being_released_still_raises_the_shared_number(tmp_path: Path) -> None:
    versions = {**VERSIONS_1_12_2, "langflow-sdk": "0.4.1"}
    releases = {**PYPI_AFTER_1_12_1, "langflow-sdk": [*PYPI_AFTER_1_12_1["langflow-sdk"], "0.4.1rc0", "0.4.1rc1"]}

    assert _shared_rc_number(tmp_path, versions, releases) == "2"


def test_prerelease_reuses_an_already_published_sdk_final(tmp_path: Path) -> None:
    assert _sdk_version(tmp_path, VERSIONS_1_12_2, PYPI_AFTER_1_12_1, rc_number="0") == ("0.4.0", "true")


def test_prerelease_builds_an_rc_for_an_unreleased_sdk_version(tmp_path: Path) -> None:
    versions = {**VERSIONS_1_12_2, "langflow-sdk": "0.4.1"}

    assert _sdk_version(tmp_path, versions, PYPI_AFTER_1_12_1, rc_number="2") == ("0.4.1rc2", "false")


def test_prerelease_fails_instead_of_minting_an_sdk_rc_when_pypi_is_unreachable(tmp_path: Path) -> None:
    # PyPI answers the step's first probe, then drops out before the "already published?" check.
    result, outputs = _run_sdk_version_step(
        tmp_path, VERSIONS_1_12_2, PYPI_AFTER_1_12_1, rc_number="0", pypi_down_from_call=2
    )

    assert result.returncode != 0
    assert "Failed to connect to pypi.org" in result.stderr
    assert outputs == {}

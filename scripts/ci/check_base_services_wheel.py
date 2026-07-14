#!/usr/bin/env python3
"""Prove ``langflow-base[services]`` installs every concrete service backend.

Builds the ``langflow-base`` (and prerequisite ``lfx`` / ``langflow-sdk``) wheels,
installs ``langflow-base[services]`` into a temporary venv, recursively imports
``langflow.services.*``, and probes the third-party packages that ``[services]``
must provide (PostgreSQL drivers, Redis, Chroma, S3, Celery, Kubernetes,
tracing providers, Watsonx SDKs, plus anyio/tenacity/dill).

A second bare-wheel install confirms ``[services]`` remains opt-in: those
backend packages must be absent without the extra.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import textwrap
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Distributions that ``langflow-base[services]`` must install on every Python.
# Prefer metadata checks over imports for packages that need native libs
# (psycopg needs libpq / psycopg-binary at import time).
REQUIRED_DISTRIBUTIONS = (
    "anyio",
    "tenacity",
    "dill",
    "psycopg",
    "psycopg2-binary",
    "redis",
    "chromadb",
    "langchain-chroma",
    "aioboto3",
    "celery",
    "asgiref",
    "kubernetes",
    "langfuse",
    "langsmith",
    "openinference-instrumentation-langchain",
    # Always-on tracing / deployment providers declared by [services].
    "arize-phoenix-otel",
    "traceloop-sdk",
    "openlayer",
    "ibm-cloud-sdk-core",
)

# Distributions gated by environment markers on the matching base extras.
# Each entry is (distribution_name, min_inclusive, max_exclusive) where None
# means unbounded. Compared against sys.version_info[:2].
MARKER_REQUIRED_DISTRIBUTIONS = (
    ("langwatch", None, (3, 14)),
    ("opik", None, (3, 14)),
    ("ibm-watsonx-orchestrate-core", (3, 11), None),
    ("ibm-watsonx-orchestrate-clients", (3, 11), None),
)

# Pure-Python (or self-contained) modules that must import cleanly when present.
REQUIRED_IMPORTS = (
    "anyio",
    "tenacity",
    "dill",
    "redis",
    "chromadb",
    "langchain_chroma",
    "aioboto3",
    "celery",
    "asgiref",
    "kubernetes",
    "langfuse",
    "langsmith",
    "openinference",
    "traceloop",
    "openlayer",
    "ibm_cloud_sdk_core",
)

# Import names gated like MARKER_REQUIRED_DISTRIBUTIONS.
MARKER_REQUIRED_IMPORTS = (
    ("langwatch", None, (3, 14)),
    ("opik", None, (3, 14)),
    ("phoenix", None, None),  # pulled by arize-phoenix-otel
    ("ibm_watsonx_orchestrate_core", (3, 11), None),
    ("ibm_watsonx_orchestrate_clients", (3, 11), None),
)

# Host-only extras that live in ``[complete]`` but not ``[services]``.
# They may be absent from a services-only install; treat as optional failures
# during recursive ``langflow.services.*`` import.
HOST_ONLY_OPTIONAL_MODULE_PREFIXES = (
    "litellm",
    "cassio",
    "cassandra",
    "toolguard",
    "mcp",
)


def _services_probe_source() -> str:
    return textwrap.dedent(
        f"""\
        import importlib
        import importlib.metadata
        import pkgutil
        import sys

        REQUIRED_DISTRIBUTIONS = {REQUIRED_DISTRIBUTIONS!r}
        MARKER_REQUIRED_DISTRIBUTIONS = {MARKER_REQUIRED_DISTRIBUTIONS!r}
        REQUIRED_IMPORTS = {REQUIRED_IMPORTS!r}
        MARKER_REQUIRED_IMPORTS = {MARKER_REQUIRED_IMPORTS!r}
        HOST_ONLY_OPTIONAL_MODULE_PREFIXES = {HOST_ONLY_OPTIONAL_MODULE_PREFIXES!r}

        def _marker_matches(version_info, min_inclusive, max_exclusive):
            if min_inclusive is not None and version_info < min_inclusive:
                return False
            if max_exclusive is not None and version_info >= max_exclusive:
                return False
            return True

        version_info = sys.version_info[:2]
        required_dists = list(REQUIRED_DISTRIBUTIONS)
        for name, min_inclusive, max_exclusive in MARKER_REQUIRED_DISTRIBUTIONS:
            if _marker_matches(version_info, min_inclusive, max_exclusive):
                required_dists.append(name)

        missing_dists = []
        for name in required_dists:
            try:
                importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                missing_dists.append(name)
        if missing_dists:
            raise SystemExit(
                "langflow-base[services] missing required distributions: "
                + ", ".join(missing_dists)
            )

        required_imports = list(REQUIRED_IMPORTS)
        for name, min_inclusive, max_exclusive in MARKER_REQUIRED_IMPORTS:
            if _marker_matches(version_info, min_inclusive, max_exclusive):
                required_imports.append(name)

        missing_imports = []
        for name in required_imports:
            try:
                importlib.import_module(name)
            except ModuleNotFoundError as exc:
                missing_imports.append(f"{{name}}: {{exc}}")
        if missing_imports:
            raise SystemExit(
                "langflow-base[services] missing required imports:\\n  "
                + "\\n  ".join(missing_imports)
            )

        # psycopg is installed but may need system libpq; confirm the package
        # is present and that ImportError is only the native-driver gap.
        try:
            importlib.import_module("psycopg")
        except ModuleNotFoundError as exc:
            raise SystemExit(f"psycopg module missing: {{exc}}") from exc
        except ImportError as exc:
            if "pq wrapper" not in str(exc) and "libpq" not in str(exc):
                raise SystemExit(f"unexpected psycopg ImportError: {{exc}}") from exc

        # Provider modules gated off this interpreter may be absent; allow only those.
        allowed_optional = list(HOST_ONLY_OPTIONAL_MODULE_PREFIXES)
        for name, min_inclusive, max_exclusive in MARKER_REQUIRED_IMPORTS:
            if not _marker_matches(version_info, min_inclusive, max_exclusive):
                allowed_optional.append(name)
        # ibm_watsonx umbrella prefix covers related SDK imports when gated off.
        if version_info < (3, 11):
            allowed_optional.extend(
                (
                    "ibm_cloud_sdk_core",
                    "ibm_watsonx",
                    "ibm_watsonx_orchestrate",
                    "ibm_watsonx_orchestrate_clients",
                    "ibm_watsonx_orchestrate_core",
                )
            )
        if version_info >= (3, 14):
            allowed_optional.extend(("langwatch", "opik"))

        import langflow.services as services_pkg

        pkg_paths = list(services_pkg.__path__)
        unexpected = []
        optional_failures = []
        for module in pkgutil.walk_packages(pkg_paths, prefix="langflow.services."):
            try:
                importlib.import_module(module.name)
            except ModuleNotFoundError as exc:
                missing = getattr(exc, "name", None) or str(exc)
                if any(
                    missing == prefix or missing.startswith(prefix + ".")
                    for prefix in allowed_optional
                ):
                    optional_failures.append((module.name, str(exc)))
                else:
                    unexpected.append((module.name, type(exc).__name__, str(exc)))
            except Exception as exc:  # noqa: BLE001 - surface unexpected import regressions
                unexpected.append((module.name, type(exc).__name__, str(exc)))

        if unexpected:
            details = "\\n".join(
                f"  {{name}}: {{exc_name}}: {{message}}"
                for name, exc_name, message in unexpected
            )
            raise SystemExit(f"Unexpected import failures:\\n{{details}}")
        print(
            f"services-wheel-ok dists={{len(required_dists)}} "
            f"imports={{len(required_imports)}} "
            f"optional_failures={{len(optional_failures)}}"
        )
        for name, message in optional_failures[:20]:
            print(f"  optional-fail {{name}}: {{message}}")
        """
    )


def _bare_probe_source() -> str:
    return textwrap.dedent(
        """\
        import importlib.metadata

        # These must remain opt-in via [services] / their own extras.
        MUST_BE_ABSENT = ("celery", "psycopg", "psycopg2-binary")
        present = []
        for name in MUST_BE_ABSENT:
            try:
                importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                continue
            present.append(name)
        if present:
            raise SystemExit(
                f"Bare langflow-base unexpectedly provides: {present}. "
                "These belong in [services] / [postgresql] / [celery]."
            )
        import langflow  # noqa: F401
        print("bare-wheel-ok services-extras-absent")
        """
    )


def _run(cmd: list[str], **kwargs) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)  # noqa: S603 - argv list from trusted CI callers only


def _install_wheels(pip: Path, wheels: list[Path], extra: str | None = None) -> None:
    specs = [str(wheel) for wheel in wheels]
    # Apply the extra only to the langflow-base wheel.
    if extra:
        specs = [
            f"{wheel}[{extra}]" if "langflow_base-" in wheel.name or "langflow-base-" in wheel.name else str(wheel)
            for wheel in wheels
        ]
    _run([str(pip), "install", *specs])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Directory for built wheels (default: temporary directory)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse wheels already present in --outdir",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="langflow-base-services-") as tmp:
        outdir = args.outdir or Path(tmp) / "wheels"
        outdir.mkdir(parents=True, exist_ok=True)

        if not args.skip_build:
            for package in ("langflow-sdk", "lfx", "langflow-base"):
                _run(["uv", "build", "--package", package, "-o", str(outdir)], cwd=REPO_ROOT)

        wheels = sorted(outdir.glob("*.whl"))
        if not wheels:
            print("No wheels found", file=sys.stderr)
            return 1
        if not any("langflow_base" in w.name or "langflow-base" in w.name for w in wheels):
            print("langflow-base wheel missing", file=sys.stderr)
            return 1

        # --- [services] install ---
        services_venv = Path(tmp) / "services-venv"
        venv.create(services_venv, with_pip=True)
        services_pip = services_venv / "bin" / "pip"
        services_python = services_venv / "bin" / "python"
        _run([str(services_pip), "install", "--upgrade", "pip"])
        _install_wheels(services_pip, wheels, extra="services")
        _run([str(services_python), "-c", _services_probe_source()])

        # --- bare install (opt-in guard) ---
        bare_venv = Path(tmp) / "bare-venv"
        venv.create(bare_venv, with_pip=True)
        bare_pip = bare_venv / "bin" / "pip"
        bare_python = bare_venv / "bin" / "python"
        _run([str(bare_pip), "install", "--upgrade", "pip"])
        _install_wheels(bare_pip, wheels, extra=None)
        _run([str(bare_python), "-c", _bare_probe_source()])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prove ``langflow-services`` installs and imports without ``langflow-base``.

Builds wheels for ``lfx``, ``langflow-sdk``, and ``langflow-services``, installs
them into a temporary venv, recursively imports ``services.*``, and asserts
``langflow`` never appears in ``sys.modules``.

Only expected optional third-party ``ModuleNotFoundError``s are allowed.
Any other exception fails the gate.
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

# Optional backends that may be absent from the isolated services wheel.
# Keep this list tight: unexpected AttributeError/TypeError must still fail.
ALLOWED_OPTIONAL_MODULE_PREFIXES = (
    "chromadb",
    "langchain_chroma",
    "langchain_community",
    "langchain_core",
    "langchain_openai",
    "langfuse",
    "langsmith",
    "langwatch",
    "openinference",
    "openlayer",
    "opik",
    "opentelemetry",
    "traceloop",
    "ibm_cloud_sdk_core",
    "ibm_watsonx",
    "ibm_watsonx_orchestrate",
    "ibm_watsonx_orchestrate_clients",
    "watsonx",
    "kubernetes",
    "celery",
    "aioboto3",
    "boto3",
    "botocore",
    "redis",
    "aiosqlite",
    "psycopg",
    "psycopg2",
    "arize",
    "phoenix",
    "cassandra",
    "cassio",
)


def _probe_source() -> str:
    return textwrap.dedent(
        f"""\
        import importlib
        import pkgutil
        import sys
        from pathlib import Path

        import services

        ALLOWED_OPTIONAL_MODULE_PREFIXES = {ALLOWED_OPTIONAL_MODULE_PREFIXES!r}

        pkg_root = Path(services.__file__).resolve().parent
        failed = []
        unexpected = []
        for module in pkgutil.walk_packages([str(pkg_root)], prefix="services."):
            try:
                importlib.import_module(module.name)
            except ModuleNotFoundError as exc:
                missing = getattr(exc, "name", None) or str(exc)
                if any(
                    missing == prefix or missing.startswith(prefix + ".")
                    for prefix in ALLOWED_OPTIONAL_MODULE_PREFIXES
                ):
                    failed.append((module.name, type(exc).__name__, str(exc)))
                else:
                    unexpected.append((module.name, type(exc).__name__, str(exc)))
            except Exception as exc:  # noqa: BLE001 - surface unexpected import regressions
                unexpected.append((module.name, type(exc).__name__, str(exc)))

        leaks = sorted(
            name for name in sys.modules if name == "langflow" or name.startswith("langflow.")
        )
        if leaks:
            raise SystemExit(f"langflow leaked into sys.modules: {{leaks}}")
        if unexpected:
            details = "\\n".join(
                f"  {{name}}: {{exc_name}}: {{message}}" for name, exc_name, message in unexpected
            )
            raise SystemExit(f"Unexpected import failures:\\n{{details}}")
        print(f"isolated-wheel-ok imported_with_optional_failures={{len(failed)}}")
        for name, exc_name, message in failed[:20]:
            print(f"  optional-fail {{name}}: {{exc_name}}: {{message}}")
        """
    )


def _run(cmd: list[str], **kwargs) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Directory for built wheels (default: temporary directory)",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="langflow-services-iso-") as tmp:
        outdir = args.outdir or Path(tmp) / "wheels"
        outdir.mkdir(parents=True, exist_ok=True)
        venv_dir = Path(tmp) / "venv"

        for package in ("langflow-sdk", "lfx", "langflow-services"):
            _run(["uv", "build", "--package", package, "-o", str(outdir)], cwd=REPO_ROOT)

        venv.create(venv_dir, with_pip=True)
        pip = venv_dir / "bin" / "pip"
        python = venv_dir / "bin" / "python"
        _run([str(pip), "install", "--upgrade", "pip"])

        wheels = sorted(outdir.glob("*.whl"))
        if not wheels:
            print("No wheels built", file=sys.stderr)
            return 1
        _run([str(pip), "install", *[str(wheel) for wheel in wheels]])

        # Guard: langflow-base must not be installed.
        probe_pkgs = subprocess.check_output(
            [str(pip), "list", "--format=freeze"],
            text=True,
        )
        if any(line.startswith("langflow-base==") for line in probe_pkgs.splitlines()):
            print("langflow-base unexpectedly installed", file=sys.stderr)
            return 1

        _run([str(python), "-c", _probe_source()])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

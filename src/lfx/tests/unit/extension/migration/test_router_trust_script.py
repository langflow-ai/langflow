"""Smoke tests for scripts/migrate/check_router_trust.py.

Exercises the script as a black-box subprocess so the test catches
SystemExit / argparse drift the same way CI would.

The router-trust invariant per the Bundle Separation Developer Guide
(section 4): install / uninstall / registry mutation routes must not
appear under ``/api/v1/extensions/**``; the trust boundary is pip
install, not a runtime endpoint.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

REPO_ROOT = Path(__file__).resolve().parents[6]
SCRIPT = REPO_ROOT / "scripts" / "migrate" / "check_router_trust.py"


def _run(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - test harness invoking our own script
        [sys.executable, str(SCRIPT), "--paths", *map(str, paths)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_clean_extensions_module_passes(tmp_path: Path) -> None:
    """A module with only the reload route must pass."""
    src = tmp_path / "extensions.py"
    src.write_text(
        dedent(
            """
            from fastapi import APIRouter
            router = APIRouter(prefix="/extensions")

            @router.post("/{extension_id}/bundles/{bundle_name}/reload")
            async def reload_extension_bundle(extension_id: str, bundle_name: str) -> dict:
                return {}
            """,
        ).strip(),
        encoding="utf-8",
    )

    result = _run(src)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("path", "func", "expected_token"),
    [
        ("/install", "install_extension", "install"),
        ("/uninstall", "uninstall_extension", "uninstall"),
        ("/registry/add", "registry_add", "registry_add"),
        ("/registry/remove", "registry_remove", "registry_remove"),
    ],
)
def test_forbidden_route_fails(tmp_path: Path, path: str, func: str, expected_token: str) -> None:
    """Each forbidden verb is caught."""
    src = tmp_path / "extensions.py"
    src.write_text(
        dedent(
            f"""
            from fastapi import APIRouter
            router = APIRouter(prefix="/extensions")

            @router.post("{{extension_id}}{path}")
            async def {func}(extension_id: str) -> dict:
                return {{}}
            """,
        ).strip(),
        encoding="utf-8",
    )

    result = _run(src)
    assert result.returncode == 1, result.stdout
    assert expected_token in result.stderr


def test_typed_error_code_namespace_is_allowlisted(tmp_path: Path) -> None:
    """``installed-extension-immutable`` is a typed error code, not a route.

    Strings containing the allowlisted substring must not trip the guard.
    """
    src = tmp_path / "extensions.py"
    src.write_text(
        dedent(
            """
            from fastapi import APIRouter
            router = APIRouter(prefix="/extensions")

            @router.post("/{extension_id}/bundles/{bundle_name}/reload")
            async def reload_extension_bundle(extension_id: str, bundle_name: str) -> dict:
                # This handler raises 'installed-extension-immutable' when the
                # caller tries to mutate an installed Bundle.
                return {"code": "installed-extension-immutable"}
            """,
        ).strip(),
        encoding="utf-8",
    )

    result = _run(src)
    assert result.returncode == 0, result.stderr


def test_real_extensions_module_passes() -> None:
    """The shipped src/backend/.../v1/extensions.py must pass the guard."""
    real_module = REPO_ROOT / "src" / "backend" / "base" / "langflow" / "api" / "v1" / "extensions.py"
    if not real_module.exists():
        pytest.skip("real extensions.py not present in this checkout")

    result = _run(real_module)
    assert result.returncode == 0, result.stderr

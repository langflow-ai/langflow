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


# ---------------------------------------------------------------------------
# Cross-file resolution
# ---------------------------------------------------------------------------


def test_split_router_pattern_is_caught(tmp_path: Path, monkeypatch) -> None:
    """A forbidden handler in module A must be caught when module B mounts it under /extensions.

    This is the reviewer's reproducer: the child file declares a router
    with no /extensions prefix; a separate parent file calls
    ``include_router(child, prefix="/extensions")``.  A purely
    file-scoped scan would let the forbidden ``/install`` handler in the
    child module slip through; the cross-file resolver must catch it.
    """
    # Build a synthetic project with two package roots so the script can
    # resolve ``from child.api import router`` to a real file on disk.
    pkg = tmp_path / "src"
    pkg.mkdir()
    (pkg / "child").mkdir()
    (pkg / "child" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "child" / "api.py").write_text(
        dedent(
            """
            from fastapi import APIRouter

            router = APIRouter()

            @router.post("/install")
            async def install_extension():
                pass
            """,
        ).strip(),
        encoding="utf-8",
    )
    (pkg / "parent").mkdir()
    (pkg / "parent" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "parent" / "main.py").write_text(
        dedent(
            """
            from fastapi import APIRouter
            from child.api import router as child_router

            app_router = APIRouter(prefix="/v1")
            app_router.include_router(child_router, prefix="/extensions")
            """,
        ).strip(),
        encoding="utf-8",
    )

    # Run the script in a subprocess with PYTHONPATH pointing at our pkg
    # so its module resolution finds the synthetic project.
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(pkg)
    # Patch MODULE_ROOTS via an env-var hook in the script?  Instead, since
    # the script reads MODULE_ROOTS from a module constant, we exercise the
    # API directly here rather than spawning a subprocess.
    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts" / "migrate"))
    import importlib

    guard = importlib.import_module("check_router_trust")
    monkeypatch.setattr(guard, "MODULE_ROOTS", (pkg,))

    file_info_map = {
        pkg / "child" / "api.py": guard.parse_file(pkg / "child" / "api.py"),
        pkg / "parent" / "main.py": guard.parse_file(pkg / "parent" / "main.py"),
    }
    in_scope = guard.compute_in_scope(file_info_map)
    violations = guard.scan_in_scope(file_info_map, in_scope)

    assert any("install" in v for v in violations), (
        f"split-router pattern was not caught.  in_scope={in_scope!r}, violations={violations!r}"
    )


def test_transitive_include_router_chain_is_caught(tmp_path: Path, monkeypatch) -> None:
    """Three-hop chain: leaf has the forbidden route; root mounts under /extensions.

    Topology:
        leaf.py      defines ``leaf_router`` (no prefix) with @leaf_router.post("/uninstall")
        middle.py    defines ``mid_router`` (no prefix) and does
                     ``mid_router.include_router(leaf_router)``
        root.py      defines ``app`` (or any router) and does
                     ``app.include_router(mid_router, prefix="/extensions")``

    The resolver must chase the chain in both directions: ``mid_router``
    becomes in-scope because root mounts it under /extensions, and
    ``leaf_router`` becomes in-scope because mid_router (now in scope)
    mounts it (no /extensions prefix on the inner mount).
    """
    pkg = tmp_path / "src"
    pkg.mkdir()
    (pkg / "leaf.py").write_text(
        dedent(
            """
            from fastapi import APIRouter

            leaf_router = APIRouter()

            @leaf_router.post("/uninstall")
            async def uninstall_handler():
                pass
            """,
        ).strip(),
        encoding="utf-8",
    )
    (pkg / "middle.py").write_text(
        dedent(
            """
            from fastapi import APIRouter
            from leaf import leaf_router

            mid_router = APIRouter()
            mid_router.include_router(leaf_router)
            """,
        ).strip(),
        encoding="utf-8",
    )
    (pkg / "root.py").write_text(
        dedent(
            """
            from fastapi import APIRouter
            from middle import mid_router

            app_router = APIRouter(prefix="/v1")
            app_router.include_router(mid_router, prefix="/extensions")
            """,
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts" / "migrate"))
    import importlib

    guard = importlib.import_module("check_router_trust")
    monkeypatch.setattr(guard, "MODULE_ROOTS", (pkg,))

    paths = [pkg / "leaf.py", pkg / "middle.py", pkg / "root.py"]
    file_info_map = {p: guard.parse_file(p) for p in paths}

    in_scope = guard.compute_in_scope(file_info_map)
    violations = guard.scan_in_scope(file_info_map, in_scope)

    # Both mid_router and leaf_router should be in scope after iteration.
    in_scope_var_names = {v for _, v in in_scope}
    assert "mid_router" in in_scope_var_names
    assert "leaf_router" in in_scope_var_names
    assert any("uninstall" in v for v in violations), f"transitive chain not caught.  violations={violations!r}"


def test_module_attribute_import_is_caught(tmp_path: Path, monkeypatch) -> None:
    """``import child.api`` then ``include_router(child.api.router, prefix="/extensions")``.

    The earlier resolver only recognised ``ast.Name`` arguments to
    ``include_router``; a dotted attribute reference was a bypass.  The
    parser now flattens any ``Name``/``Attribute`` chain and the
    resolver follows ``import x.y`` bindings back to the source file.
    """
    pkg = tmp_path / "src"
    pkg.mkdir()
    (pkg / "child").mkdir()
    (pkg / "child" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "child" / "api.py").write_text(
        dedent(
            """
            from fastapi import APIRouter

            router = APIRouter()

            @router.post("/install")
            async def install_extension():
                pass
            """,
        ).strip(),
        encoding="utf-8",
    )
    (pkg / "main.py").write_text(
        dedent(
            """
            from fastapi import APIRouter
            import child.api

            app_router = APIRouter(prefix="/v1")
            app_router.include_router(child.api.router, prefix="/extensions")
            """,
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts" / "migrate"))
    import importlib

    guard = importlib.import_module("check_router_trust")
    monkeypatch.setattr(guard, "MODULE_ROOTS", (pkg,))

    file_info_map = {
        pkg / "child" / "api.py": guard.parse_file(pkg / "child" / "api.py"),
        pkg / "main.py": guard.parse_file(pkg / "main.py"),
    }
    in_scope = guard.compute_in_scope(file_info_map)
    violations = guard.scan_in_scope(file_info_map, in_scope)

    assert any("install" in v for v in violations), (
        f"module-attribute include target not caught.  in_scope={in_scope!r}, violations={violations!r}"
    )


def test_module_asname_import_is_caught(tmp_path: Path, monkeypatch) -> None:
    """``import child.api as child_api`` then ``include_router(child_api.router, ...)``.

    Distinct case from plain ``import child.api`` because Python binds
    ``child_api`` as the alias instead of ``child``; the resolver has to
    treat the alias as the entry point and walk the imported module
    path from there.
    """
    pkg = tmp_path / "src"
    pkg.mkdir()
    (pkg / "child").mkdir()
    (pkg / "child" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "child" / "api.py").write_text(
        dedent(
            """
            from fastapi import APIRouter

            router = APIRouter()

            @router.post("/uninstall")
            async def uninstall_handler():
                pass
            """,
        ).strip(),
        encoding="utf-8",
    )
    (pkg / "main.py").write_text(
        dedent(
            """
            from fastapi import APIRouter
            import child.api as child_api

            app_router = APIRouter(prefix="/v1")
            app_router.include_router(child_api.router, prefix="/extensions")
            """,
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts" / "migrate"))
    import importlib

    guard = importlib.import_module("check_router_trust")
    monkeypatch.setattr(guard, "MODULE_ROOTS", (pkg,))

    file_info_map = {
        pkg / "child" / "api.py": guard.parse_file(pkg / "child" / "api.py"),
        pkg / "main.py": guard.parse_file(pkg / "main.py"),
    }
    in_scope = guard.compute_in_scope(file_info_map)
    violations = guard.scan_in_scope(file_info_map, in_scope)

    assert any("uninstall" in v for v in violations), (
        f"asname include target not caught.  in_scope={in_scope!r}, violations={violations!r}"
    )


def test_relative_import_inside_package_init_is_caught(tmp_path: Path, monkeypatch) -> None:
    """``from .child import router`` in ``pkg/__init__.py`` resolves to ``pkg.child``.

    The earlier resolver computed the relative-import anchor by stripping
    a "file" segment from the dotted path; for ``__init__.py`` files
    there is no file segment and Python's ``level=1`` already anchors at
    the package itself, so the resolver walked one segment too far and
    produced an unresolvable bare module name.

    Regression for [reviewer's reproducer]:
        pkg/__init__.py: from .child import router; include_router(..., prefix="/extensions")
        pkg/child.py:    @router.post("/install")
    """
    pkg_root = tmp_path / "src"
    pkg_root.mkdir()
    pkg = pkg_root / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        dedent(
            """
            from fastapi import APIRouter
            from .child import router as child_router

            app_router = APIRouter(prefix="/v1")
            app_router.include_router(child_router, prefix="/extensions")
            """,
        ).strip(),
        encoding="utf-8",
    )
    (pkg / "child.py").write_text(
        dedent(
            """
            from fastapi import APIRouter

            router = APIRouter()

            @router.post("/install")
            async def install_extension():
                pass
            """,
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts" / "migrate"))
    import importlib

    guard = importlib.import_module("check_router_trust")
    monkeypatch.setattr(guard, "MODULE_ROOTS", (pkg_root,))

    file_info_map = {
        pkg / "__init__.py": guard.parse_file(pkg / "__init__.py"),
        pkg / "child.py": guard.parse_file(pkg / "child.py"),
    }
    init_imports = file_info_map[pkg / "__init__.py"].imports
    assert init_imports["child_router"].module == "pkg.child", (
        f"relative import in __init__.py resolved incorrectly: {init_imports!r}"
    )

    in_scope = guard.compute_in_scope(file_info_map)
    violations = guard.scan_in_scope(file_info_map, in_scope)

    assert any("install" in v for v in violations), (
        f"relative-from-init bypass not caught.  in_scope={in_scope!r}, violations={violations!r}"
    )


def test_unrelated_install_route_not_flagged(tmp_path: Path, monkeypatch) -> None:
    """A handler named ``install`` on a router never mounted under /extensions is fine.

    The guard must not be a generic ban on the word "install" -- only routes
    reachable from /api/v1/extensions/** are forbidden.
    """
    pkg = tmp_path / "src"
    pkg.mkdir()
    (pkg / "elsewhere.py").write_text(
        dedent(
            """
            from fastapi import APIRouter

            elsewhere_router = APIRouter(prefix="/marketplace")

            @elsewhere_router.post("/install")
            async def marketplace_install():
                pass
            """,
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts" / "migrate"))
    import importlib

    guard = importlib.import_module("check_router_trust")
    monkeypatch.setattr(guard, "MODULE_ROOTS", (pkg,))

    file_info_map = {pkg / "elsewhere.py": guard.parse_file(pkg / "elsewhere.py")}
    in_scope = guard.compute_in_scope(file_info_map)
    violations = guard.scan_in_scope(file_info_map, in_scope)

    assert in_scope == set()
    assert violations == []

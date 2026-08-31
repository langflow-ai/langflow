"""Bundle-free SSRF wiring conformance for ``lfx-bundles`` provider components.

The behavioural SSRF tests for these components must instantiate the component, which needs
``lfx-bundles`` installed -- and since #13869 made that metapackage opt-in, they skip in every
default install. Security regressions that cannot fail are not coverage, so the wiring invariant
is asserted here instead, statically: the provider sources live in the repo even when the
distribution is not installed, so this module reads and parses them rather than importing them.

Precedent for static analysis of ``lfx_bundles`` sources: ``test_bundle_shims.py`` and
``lfx/tests/unit/extension/migration/test_migration_table_completeness.py``.

What this pins, per guarded module:

* the SSRF guard is imported from ``lfx.utils.ssrf_httpx`` / ``lfx.utils.ssrf_protection``;
* every imported guard is actually *called*, not merely imported (an unused import silences
  linters while leaving the request unguarded);
* no raw network sink (``httpx.get`` / ``httpx.Client`` / ...) appears in the module, which is
  how an unguarded request would have to be issued.

What it deliberately does not pin: ordering (guard strictly before the request) and the runtime
block itself. Those need a live component, and are covered by the behavioural tests that ship
with the bundle in ``src/bundles/lfx-bundles/tests/``. The two layers are complementary -- this
one runs on every PR, that one runs when the bundle is installed.

Adding a provider component that fetches a tenant-controlled URL means adding it to
``GUARDED_MODULES``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Guard helpers that count as SSRF-protecting a request.
GUARD_MODULES = ("lfx.utils.ssrf_httpx", "lfx.utils.ssrf_protection")

# Raw network sinks. A guarded module routes through the helpers above instead, so any direct
# use here is either an unguarded request or a guard that was refactored away.
RAW_SINKS = frozenset({"get", "post", "put", "patch", "delete", "request", "stream", "Client", "AsyncClient"})

# module path (relative to the lfx_bundles package) -> guards it must import *and* call.
# Mirrors the behavioural coverage that skips without the bundle installed.
GUARDED_MODULES: dict[str, set[str]] = {
    "deepseek/deepseek.py": {"ssrf_safe_httpx_get", "ssrf_protected_openai_clients_for_url"},
    "glean/glean_search_api.py": {"ssrf_safe_httpx_post"},
    "git/git.py": {"validate_git_repository_url"},
    "git/gitextractor.py": {"validate_git_repository_url"},
    "homeassistant/home_assistant_control.py": {"ssrf_safe_httpx_post"},
    "homeassistant/list_home_assistant_states.py": {"ssrf_safe_httpx_get"},
    "huggingface/huggingface_inference_api.py": {"ssrf_safe_httpx_get", "validate_url_for_ssrf_or_raise"},
    "litellm/litellm_proxy.py": {"ssrf_safe_httpx_get", "ssrf_protected_openai_clients_for_url"},
    "lmstudio/lmstudioembeddings.py": {"ssrf_safe_async_get", "validate_url_for_ssrf_or_raise"},
    "lmstudio/lmstudiomodel.py": {"ssrf_safe_async_get", "ssrf_protected_openai_clients_for_url"},
    "xai/xai.py": {"ssrf_safe_httpx_get", "ssrf_protected_openai_clients_for_url"},
}


def _bundles_root() -> Path:
    """Locate ``src/bundles/lfx-bundles/src/lfx_bundles`` by walking up from this file."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "src" / "bundles" / "lfx-bundles" / "src" / "lfx_bundles"
        if candidate.is_dir():
            return candidate
    msg = "lfx_bundles source root not found -- run from a repo checkout"
    raise AssertionError(msg)


BUNDLES_ROOT = _bundles_root()


def _parse(rel_path: str) -> ast.Module:
    path = BUNDLES_ROOT / rel_path
    assert path.is_file(), (
        f"{rel_path} not found under {BUNDLES_ROOT}. If the component moved or was renamed, "
        "update GUARDED_MODULES -- do not delete the entry, or the SSRF guard loses its regression net."
    )
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_guards(tree: ast.Module) -> set[str]:
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module in GUARD_MODULES
        for alias in node.names
    }


def _called_names(tree: ast.Module) -> set[str]:
    """Bare names invoked as calls, e.g. ``ssrf_safe_httpx_get(...)``."""
    return {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


def _raw_sink_calls(tree: ast.Module) -> list[str]:
    """``httpx.<sink>(...)`` style calls -- the shape an unguarded request would take."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in RAW_SINKS
            and isinstance(func.value, ast.Name)
            and func.value.id == "httpx"
        ):
            found.append(f"httpx.{func.attr} (line {node.lineno})")
    return found


@pytest.mark.parametrize("rel_path", sorted(GUARDED_MODULES))
def test_guard_is_imported(rel_path: str) -> None:
    """The module imports the SSRF guard its requests are supposed to route through."""
    imported = _imported_guards(_parse(rel_path))
    missing = GUARDED_MODULES[rel_path] - imported
    assert not missing, (
        f"{rel_path} no longer imports {sorted(missing)} from {GUARD_MODULES}. "
        "A tenant-controlled URL reaching the network without this guard is an SSRF regression."
    )


@pytest.mark.parametrize("rel_path", sorted(GUARDED_MODULES))
def test_guard_is_called(rel_path: str) -> None:
    """Importing the guard is not enough -- it has to be invoked."""
    tree = _parse(rel_path)
    called = _called_names(tree)
    expected = GUARDED_MODULES[rel_path] & _imported_guards(tree)
    never_called = expected - called
    assert not never_called, (
        f"{rel_path} imports {sorted(never_called)} but never calls it. "
        "An unused guard import passes linting while leaving the request unprotected."
    )


@pytest.mark.parametrize("rel_path", sorted(GUARDED_MODULES))
def test_no_raw_network_sink(rel_path: str) -> None:
    """No direct ``httpx.*`` call -- guarded modules go through the ssrf_* helpers."""
    sinks = _raw_sink_calls(_parse(rel_path))
    assert not sinks, (
        f"{rel_path} calls {sinks} directly instead of the SSRF-safe helper. "
        "Route it through lfx.utils.ssrf_httpx so a tenant-supplied host is validated first."
    )


def test_registry_covers_every_declared_guard_user() -> None:
    """Any bundle module importing a ``ssrf_safe_*`` helper must be in GUARDED_MODULES.

    Without this, a new provider can fetch a tenant-controlled URL and silently sit outside the
    conformance net -- the registry would still be green because it never heard of the module.
    """
    users = {
        str(path.relative_to(BUNDLES_ROOT))
        for path in BUNDLES_ROOT.rglob("*.py")
        if "ssrf_safe_" in path.read_text(encoding="utf-8")
    }
    unregistered = users - set(GUARDED_MODULES)
    assert not unregistered, (
        f"these bundle modules use an SSRF-safe helper but are not in GUARDED_MODULES: {sorted(unregistered)}. "
        "Add them so the guard cannot be removed unnoticed."
    )

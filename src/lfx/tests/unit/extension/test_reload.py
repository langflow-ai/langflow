"""Unit tests for the LE-1018 atomic-swap reload pipeline.

Covers the AC items from the ticket:

* rename a component, reload, old name gone, new name present;
* broken bundle (import error in staging) leaves the live registry
  byte-identical and emits ``bundle_reload_failed``;
* concurrent /all readers during a reload see either fully pre- or
  fully post-reload state, never a mix;
* flow-start-during-reload observes the old class set until Stage 3
  publishes the new record;
* a second reload within 100ms returns ``reload-in-progress``;
* in-flight flows that captured a class reference keep operating
  against the pre-swap class even after Stage 3 swaps.

The tests build synthetic extensions on disk with the same helpers the
loader-test suite uses, then drive :func:`reload_bundle` directly so the
HTTP / CLI layers stay out of scope.
"""

from __future__ import annotations

import contextlib
import json
import sys
import threading
import time
from typing import TYPE_CHECKING

import pytest
from lfx.extension import errors as errors_mod
from lfx.extension import reload as reload_mod
from lfx.extension.bundle_registry import BundleRegistry
from lfx.extension.errors import ExtensionError
from lfx.extension.reload import ReloadInProgressError, ReloadResult, reload_bundle

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


# ---------------------------------------------------------------------------
# Synthetic extension helpers (parallel to loader/conftest.py)
# ---------------------------------------------------------------------------


_BASE_MANIFEST: dict = {
    "id": "lfx-pilot",
    "version": "1.2.3",
    "name": "Pilot Bundle",
    "lfx": {"compat": ["1"]},
    "bundles": [{"name": "pilot", "path": "components"}],
}


def _component_source(class_name: str) -> str:
    body = "    def build(self):\n        return None\n"
    return f"class Component:\n    pass\n\nclass {class_name}(Component):\n    display_name = 'X'\n{body}"


def _write_extension(root: Path, *, files: dict[str, str], manifest: dict | None = None) -> Path:
    """Lay out an extension at ``root`` with given bundle files.  Returns ``root``."""
    manifest = manifest or _BASE_MANIFEST
    (root / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    bundle_dir = root / manifest["bundles"][0]["path"]
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        target = bundle_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return root


@pytest.fixture(autouse=True)
def _scrub_synthetic_modules() -> Iterable[None]:
    """Strip loader-installed and staging modules between tests."""
    yield
    for name in [m for m in sys.modules if m.startswith(("_lfx_ext.", "__reload_staging__."))]:
        sys.modules.pop(name, None)


def _initial_install(registry: BundleRegistry, root: Path) -> ReloadResult:
    """Install a Bundle into ``registry`` for the first time via reload_bundle."""
    return reload_bundle(registry, "pilot", source_path=root)


# ---------------------------------------------------------------------------
# Stage 1+2+3 happy path: rename a component, reload, old gone, new present
# ---------------------------------------------------------------------------


def test_reload_replaces_component_set(tmp_path: Path) -> None:
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    initial = _initial_install(registry, root)
    assert initial.ok
    assert registry.get_bundle("pilot").class_names == frozenset({"PilotThing"})

    # Rename the component on disk and reload.
    (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")
    result = reload_bundle(registry, "pilot")

    assert result.ok, result.errors
    assert result.components_added == ("RenamedThing",)
    assert result.components_removed == ("PilotThing",)

    record = registry.get_bundle("pilot")
    assert record.class_names == frozenset({"RenamedThing"})
    assert "PilotThing" not in record.by_class_name()


def test_reload_publishes_namespaced_module_in_sys_modules(tmp_path: Path) -> None:
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    record = registry.get_bundle("pilot")
    component = record.by_class_name()["PilotThing"]
    assert component.module_name.startswith("_lfx_ext.")
    assert component.module_name in sys.modules
    # No staging module entries should remain after a successful reload.
    staging = [n for n in sys.modules if n.startswith("__reload_staging__.")]
    assert staging == []


# ---------------------------------------------------------------------------
# Failure path: broken bundle leaves live untouched
# ---------------------------------------------------------------------------


def test_broken_reload_leaves_live_untouched_and_emits_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)
    pre_record = registry.get_bundle("pilot")

    captured: list[ReloadResult] = []
    monkeypatch.setattr(reload_mod, "_emit_bundle_reload_event", captured.append)

    # Break the bundle so Stage 1 produces an import error.
    (root / "components" / "thing.py").write_text("raise RuntimeError('boom at import')\n", encoding="utf-8")
    result = reload_bundle(registry, "pilot")

    assert not result.ok
    assert any(e.code == "module-import-failed" for e in result.errors)

    # The live record is identical -- not just equal, the *same* object.
    assert registry.get_bundle("pilot") is pre_record
    # And bundle_reload_failed went to the events sink.
    assert len(captured) == 1
    assert captured[0].ok is False


def test_reload_unknown_bundle_returns_typed_error() -> None:
    registry = BundleRegistry()
    result = reload_bundle(registry, "nonexistent")
    assert not result.ok
    assert any(e.code == "reload-bundle-not-installed" for e in result.errors)


def test_reload_missing_source_returns_typed_error(tmp_path: Path) -> None:
    registry = BundleRegistry()
    result = reload_bundle(registry, "ghost", source_path=tmp_path / "does-not-exist")
    assert not result.ok
    assert any(e.code == "reload-source-missing" for e in result.errors)


def test_reload_bundle_name_mismatch(tmp_path: Path) -> None:
    """Manifest at source declares a different bundle name than the one being reloaded."""
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    # Reload "wrong_name" pointing at the pilot manifest -> mismatch error.
    result = reload_bundle(registry, "wrong_name", source_path=root)
    assert not result.ok
    assert any(e.code == "reload-bundle-name-mismatch" for e in result.errors)
    # The pilot record is still installed.
    assert registry.get_bundle("pilot") is not None


# ---------------------------------------------------------------------------
# Concurrent-reload guard
# ---------------------------------------------------------------------------


def test_double_reload_returns_in_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    # Block Stage 1 of the first reload so the second reload races inside the
    # in-progress window.
    proceed = threading.Event()
    started = threading.Event()
    real_load = reload_mod.load_extension

    def slow_load(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        started.set()
        proceed.wait(timeout=5.0)
        return real_load(*args, **kwargs)

    monkeypatch.setattr(reload_mod, "load_extension", slow_load)

    results: dict[str, object] = {}

    def first() -> None:
        results["first"] = reload_bundle(registry, "pilot")

    thread = threading.Thread(target=first, name="reload-first")
    thread.start()
    assert started.wait(timeout=5.0)

    # Second concurrent attempt must raise ReloadInProgressError.
    with pytest.raises(ReloadInProgressError) as exc:
        reload_bundle(registry, "pilot")
    assert exc.value.bundle == "pilot"

    proceed.set()
    thread.join(timeout=5.0)
    assert results["first"].ok  # type: ignore[union-attr]
    # And after the first reload completes, a fresh reload is allowed.
    assert not registry.is_reload_in_progress("pilot")


# ---------------------------------------------------------------------------
# Concurrent readers see consistent snapshot
# ---------------------------------------------------------------------------


def test_concurrent_readers_see_pre_or_post_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)
    (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")

    # Fan out N reader threads while a reload runs.
    proceed = threading.Event()
    started = threading.Event()
    real_load = reload_mod.load_extension

    def slow_load(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        started.set()
        proceed.wait(timeout=5.0)
        return real_load(*args, **kwargs)

    monkeypatch.setattr(reload_mod, "load_extension", slow_load)

    n_readers = 16
    observations: list[frozenset[str]] = []
    obs_lock = threading.Lock()

    def reader() -> None:
        for _ in range(50):
            snap = registry.snapshot()
            rec = snap.get("pilot")
            if rec is not None:
                with obs_lock:
                    observations.append(rec.class_names)

    reload_thread = threading.Thread(target=lambda: reload_bundle(registry, "pilot"))
    reload_thread.start()
    assert started.wait(timeout=5.0)

    readers = [threading.Thread(target=reader) for _ in range(n_readers)]
    for r in readers:
        r.start()

    # Let readers run a moment, then release the reload.
    time.sleep(0.05)
    proceed.set()

    for r in readers:
        r.join(timeout=5.0)
    reload_thread.join(timeout=5.0)

    pre = frozenset({"PilotThing"})
    post = frozenset({"RenamedThing"})
    assert observations, "readers should have captured at least one snapshot"
    for snap in observations:
        assert snap in {pre, post}, f"unexpected mixed state: {snap!r}"


# ---------------------------------------------------------------------------
# In-flight flow: pre-swap class survives reload
# ---------------------------------------------------------------------------


def test_in_flight_class_reference_survives_reload(tmp_path: Path) -> None:
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    # Capture the class object the way an in-flight flow would.
    pre_record = registry.get_bundle("pilot")
    pre_klass = pre_record.by_class_name()["PilotThing"].klass
    pre_instance = pre_klass()  # in-flight instance built from the pre-swap class
    assert pre_instance.build() is None

    # Rename + reload.
    (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")
    result = reload_bundle(registry, "pilot")
    assert result.ok

    # The captured class still works -- the in-flight flow keeps using it.
    assert pre_instance.build() is None
    assert pre_klass.__name__ == "PilotThing"
    # The registry now points at the new class.
    new_record = registry.get_bundle("pilot")
    assert new_record is not pre_record
    assert "RenamedThing" in new_record.by_class_name()


# ---------------------------------------------------------------------------
# Flow-start-during-reload: stages 1-2 do not affect the registry snapshot
# ---------------------------------------------------------------------------


def test_flow_start_during_stages_1_and_2_sees_old_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)
    (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")

    proceed = threading.Event()
    started = threading.Event()
    real_load = reload_mod.load_extension

    def slow_load(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        started.set()
        proceed.wait(timeout=5.0)
        return real_load(*args, **kwargs)

    monkeypatch.setattr(reload_mod, "load_extension", slow_load)

    reload_thread = threading.Thread(target=lambda: reload_bundle(registry, "pilot"))
    reload_thread.start()
    assert started.wait(timeout=5.0)

    # While Stage 1 is blocked, the registry still shows the pre-reload set.
    snap = registry.get_bundle("pilot")
    assert snap.class_names == frozenset({"PilotThing"})

    proceed.set()
    reload_thread.join(timeout=5.0)
    assert registry.get_bundle("pilot").class_names == frozenset({"RenamedThing"})


# ---------------------------------------------------------------------------
# components_index.json (registry side, exercised by reload)
# ---------------------------------------------------------------------------


def test_components_index_json_written_on_reload(tmp_path: Path) -> None:
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    index_path = tmp_path / "index" / "components_index.json"
    registry = BundleRegistry(index_path=index_path)
    _initial_install(registry, root)

    assert index_path.is_file()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    bundles = {b["name"]: b for b in payload["bundles"]}
    assert "pilot" in bundles
    classes = {c["class_name"] for c in bundles["pilot"]["components"]}
    assert classes == {"PilotThing"}


# ---------------------------------------------------------------------------
# Defensive: ReloadInProgressError carries the bundle name for the API layer
# ---------------------------------------------------------------------------


def test_reload_in_progress_error_carries_bundle_name() -> None:
    err = ReloadInProgressError("foo")
    assert err.bundle == "foo"
    assert "foo" in str(err)


# ---------------------------------------------------------------------------
# format_extension_error: the four reload codes render with snapshot shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        "reload-in-progress",
        "reload-bundle-not-installed",
        "reload-bundle-name-mismatch",
        "reload-source-missing",
        "reload-post-swap-hook-failed",
    ],
)
def test_reload_error_codes_have_branch(code: str) -> None:
    err = ExtensionError(code=code, message="m", hint="h", location="loc", content="c")
    rendered = errors_mod.format_extension_error(err)
    assert rendered.startswith(f"error[{code}]:")
    assert "see:" in rendered


# ---------------------------------------------------------------------------
# @extra slot reload: source_path is the bundle directory itself
# ---------------------------------------------------------------------------


def _write_inline_bundle(parent: Path, *, name: str, files: dict[str, str]) -> Path:
    """Lay out an inline @extra bundle (no manifest at root) and return its dir."""
    bundle_dir = parent / name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for filename, source in files.items():
        target = bundle_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return bundle_dir


def test_extra_slot_reload_uses_bundle_directory(tmp_path: Path) -> None:
    """Inline @extra bundles record source_path = bundle dir, no manifest there.

    Reload must walk the bundle directory directly (the same way startup
    discovery does) instead of insisting on a manifest at the source path.
    Regression: before the @extra-aware branch, this returned
    ``manifest-not-found`` even for bundles surfaced from a valid
    LANGFLOW_COMPONENTS_PATH entry.
    """
    bundle_dir = _write_inline_bundle(
        tmp_path,
        name="local_bundle",
        files={"thing.py": _component_source("LocalThing")},
    )

    registry = BundleRegistry()
    initial = reload_bundle(
        registry,
        "local_bundle",
        source_path=bundle_dir,
        slot="extra",
    )
    assert initial.ok, initial.errors
    record = registry.get_bundle("local_bundle")
    assert record.slot == "extra"
    assert record.class_names == frozenset({"LocalThing"})

    # Rename the class on disk and reload using the recorded source_path.
    (bundle_dir / "thing.py").write_text(_component_source("RenamedLocalThing"), encoding="utf-8")
    result = reload_bundle(registry, "local_bundle")
    assert result.ok, result.errors
    assert result.components_added == ("RenamedLocalThing",)
    assert result.components_removed == ("LocalThing",)
    assert registry.get_bundle("local_bundle").class_names == frozenset({"RenamedLocalThing"})


# ---------------------------------------------------------------------------
# klass.__module__ retag after the atomic swap
# ---------------------------------------------------------------------------


def test_swap_retags_class_module_to_prod_namespace(tmp_path: Path) -> None:
    """Stage 3 retags every component class's ``__module__`` to the prod namespace.

    Without this retag, ``cls.__module__`` keeps pointing at the dropped
    ``__reload_staging__.<id>.*`` key it was stamped with at class-definition
    time -- ``inspect.getmodule(cls)`` then returns ``None`` and
    :func:`Component.set_class_code` raises, silently breaking the post-swap
    component-cache rebuild (the empty-palette-after-reload bug).
    """
    import inspect as inspect_mod

    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    initial = _initial_install(registry, root)
    assert initial.ok, initial.errors

    record = registry.get_bundle("pilot")
    component = record.by_class_name()["PilotThing"]

    # The retagged class lives at the production namespace, not at the
    # staging namespace the loader originally imported it under.
    assert component.klass.__module__.startswith("_lfx_ext.")
    assert "__reload_staging__" not in component.klass.__module__
    # And the production name resolves through sys.modules so
    # inspect.getmodule(cls) succeeds.
    assert component.module_name in sys.modules
    assert inspect_mod.getmodule(component.klass) is sys.modules[component.module_name]


def test_swap_retag_survives_subsequent_reload(tmp_path: Path) -> None:
    """A second reload must also leave ``klass.__module__`` at the prod name.

    Regression guard against a regression that only updates ``klass.__module__``
    on the *initial* install path (e.g. if someone moves the retag into
    ``import_extension_components`` instead of ``_swap_sys_modules``).
    """
    import inspect as inspect_mod

    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    # Edit on disk and reload again.
    (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")
    result = reload_bundle(registry, "pilot")
    assert result.ok, result.errors

    record = registry.get_bundle("pilot")
    component = record.by_class_name()["RenamedThing"]
    assert component.klass.__module__.startswith("_lfx_ext.")
    assert "__reload_staging__" not in component.klass.__module__
    assert inspect_mod.getmodule(component.klass) is sys.modules[component.module_name]


# ---------------------------------------------------------------------------
# Post-swap hook failures surface on ReloadResult.warnings
# ---------------------------------------------------------------------------


def test_post_swap_hook_failure_surfaces_as_warning(tmp_path: Path) -> None:
    """A raising post-swap hook surfaces on ``ReloadResult.warnings``.

    The swap must not roll back, but the failure must appear with code
    ``reload-post-swap-hook-failed`` so HTTP callers see "swap committed but
    downstream side-effects broke" instead of silent 200 OK.
    """
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    def _always_raises(_record):
        msg = "synthetic hook failure"
        raise RuntimeError(msg)

    reload_mod.register_post_swap_hook(_always_raises)
    try:
        (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")
        result = reload_bundle(registry, "pilot")
    finally:
        with contextlib.suppress(ValueError):
            reload_mod._POST_SWAP_HOOKS.remove(_always_raises)

    # Swap committed despite the hook failure.
    assert result.ok, result.errors
    assert registry.get_bundle("pilot").class_names == frozenset({"RenamedThing"})

    # The failure is surfaced as a typed warning, not an error.
    hook_warnings = [w for w in result.warnings if w.code == "reload-post-swap-hook-failed"]
    assert len(hook_warnings) == 1, result.warnings
    assert "synthetic hook failure" in hook_warnings[0].message


def test_post_swap_hook_success_adds_no_warnings(tmp_path: Path) -> None:
    """The happy path emits no ``reload-post-swap-hook-failed`` warning.

    Regression guard against accidentally appending an error to the warnings
    list on every reload.
    """
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")
    result = reload_bundle(registry, "pilot")
    assert result.ok, result.errors
    assert not [w for w in result.warnings if w.code == "reload-post-swap-hook-failed"]

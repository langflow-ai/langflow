"""Unit tests for the atomic-swap reload pipeline.

Covers the AC items:

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

import json
import sys
import threading
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


def test_reload_reports_in_class_body_edit_via_components_changed(tmp_path: Path) -> None:
    """Editing the body of an existing class must surface in components_changed.

    Before the source_hash field, the diff compared only class-name sets, so
    a body-only edit yielded ``components_added=()`` / ``components_removed=()``
    and the UI showed ``no component changes`` for a real reload.  The diff
    now compares :attr:`LoadedComponent.source_hash`; body edits change the
    file hash and surface as ``components_changed``.
    """
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    # Rewrite the same class with a different body (different build()).
    edited = (
        "class Component:\n    pass\n\n"
        "class PilotThing(Component):\n"
        "    display_name = 'X'\n"
        "    def build(self):\n"
        "        return 'edited'\n"
    )
    (root / "components" / "thing.py").write_text(edited, encoding="utf-8")

    result = reload_bundle(registry, "pilot")

    assert result.ok, result.errors
    assert result.components_added == ()
    assert result.components_removed == ()
    assert result.components_changed == ("PilotThing",)


def test_reload_reports_no_changes_when_source_is_identical(tmp_path: Path) -> None:
    """An unchanged file produces empty added/removed/changed lists."""
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    result = reload_bundle(registry, "pilot")

    assert result.ok, result.errors
    assert result.components_added == ()
    assert result.components_removed == ()
    assert result.components_changed == ()


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

    def _capture(result: ReloadResult, **_kwargs: object) -> None:
        captured.append(result)

    monkeypatch.setattr(reload_mod, "_emit_bundle_reload_event", _capture)

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


def test_emit_uses_user_keyspace_and_full_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``reload_bundle(user_id=...)`` emits to ``user:<id>`` with ReloadResult.to_dict().

    Guards both fixes:
    * P1 -- per-user keyspace prevents leakage on /extensions/events polls.
    * P2 -- payload is the full ReloadResult envelope so the frontend can read
      ``components_changed`` and ``errors[0].message`` instead of falling back
      to the generic "check server logs" copy.
    """
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    captured: list[tuple[str, dict, str]] = []

    class _FakeSvc:
        def emit(self, event_type: str, payload: dict, keyspace: str = "global") -> None:
            captured.append((event_type, payload, keyspace))

    monkeypatch.setattr(
        "lfx.services.deps.get_extension_events_service",
        lambda: _FakeSvc(),
    )

    # Body-only edit -> components_changed set, components_added/removed empty.
    (root / "components" / "thing.py").write_text(
        _component_source("PilotThing").replace("return None", "return 42"),
        encoding="utf-8",
    )
    result = reload_bundle(registry, "pilot", user_id="alice-id")
    assert result.ok

    assert len(captured) == 1
    event_type, payload, keyspace = captured[0]
    assert event_type == "bundle_reloaded"
    assert keyspace == "user:alice-id"
    # Full ReloadResult envelope -- not a hand-rolled subset.
    assert payload == result.to_dict()
    assert payload["ok"] is True
    assert "components_changed" in payload
    assert payload["components_changed"] == ["PilotThing"]
    assert payload["components_added"] == []
    assert payload["components_removed"] == []


def test_emit_falls_back_to_global_when_user_id_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``user_id`` (CLI / single-user dev) events still emit, to ``global``."""
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    captured: list[tuple[str, dict, str]] = []

    class _FakeSvc:
        def emit(self, event_type: str, payload: dict, keyspace: str = "global") -> None:
            captured.append((event_type, payload, keyspace))

    monkeypatch.setattr(
        "lfx.services.deps.get_extension_events_service",
        lambda: _FakeSvc(),
    )

    (root / "components" / "thing.py").write_text(_component_source("Renamed"), encoding="utf-8")
    reload_bundle(registry, "pilot")

    assert len(captured) == 1
    _, _, keyspace = captured[0]
    assert keyspace == "global"


def test_emit_failure_payload_carries_errors_with_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed reload payload contains ``errors[0].message`` for the toast.

    Regression: previously the event only carried ``{bundle, reload_id, errors}``
    but the frontend read ``payload.message`` -- it never matched, so every
    failure surfaced as the generic "check server logs" toast.
    """
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    captured: list[tuple[str, dict, str]] = []

    class _FakeSvc:
        def emit(self, event_type: str, payload: dict, keyspace: str = "global") -> None:
            captured.append((event_type, payload, keyspace))

    monkeypatch.setattr(
        "lfx.services.deps.get_extension_events_service",
        lambda: _FakeSvc(),
    )

    (root / "components" / "thing.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    result = reload_bundle(registry, "pilot", user_id="bob-id")
    assert not result.ok

    assert len(captured) == 1
    event_type, payload, keyspace = captured[0]
    assert event_type == "bundle_reload_failed"
    assert keyspace == "user:bob-id"
    assert payload["ok"] is False
    assert isinstance(payload["errors"], list)
    assert payload["errors"]
    assert payload["errors"][0]["message"]


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


def test_reload_traversal_source_path_does_not_escape(tmp_path: Path) -> None:
    """A ``../``-laden source_path must surface a typed error, not touch /etc.

    The reload entry point accepts a source_path; the worst-case failure mode
    is a coordinate that lands in a filesystem path and is allowed to mutate
    state outside the intended root.  ``reload_bundle`` should treat a
    non-directory traversal source as a typed ``reload-source-missing``
    error before touching the registry's reload-in-progress guard.
    """
    registry = BundleRegistry()
    result = reload_bundle(
        registry,
        "any_name",
        source_path=tmp_path / ".." / ".." / "etc" / "passwd",
    )
    assert not result.ok
    assert any(e.code == "reload-source-missing" for e in result.errors)
    # And the registry is untouched.
    assert registry.get_bundle("any_name") is None
    assert not registry.is_reload_in_progress("any_name")


def test_reload_absolute_path_outside_does_not_load(tmp_path: Path) -> None:
    """Absolute path to non-bundle directory fails cleanly without registering.

    An absolute source_path pointing at something that exists but is not a
    valid bundle must fail cleanly without registering anything.
    """
    registry = BundleRegistry()
    # /tmp/something-that-isnt-an-extension exists but isn't a bundle root.
    bogus = tmp_path / "definitely_not_a_bundle"
    bogus.mkdir()
    result = reload_bundle(registry, "any_name", source_path=bogus)
    assert not result.ok
    # Should fail at manifest discovery or downstream typed error; never
    # silently produce ok=True.
    assert registry.get_bundle("any_name") is None


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
    """Concurrent readers observe pre- or post-swap state, never a mix.

    Race-window deterministic: a Barrier guarantees readers are running while
    the reload is paused mid-stage.  The previous version used ``time.sleep(0.05)``
    which could pass under CI load without actually exercising the race window
    (the readers finished before the reload paused).
    """
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)
    (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")

    # Fan out N reader threads while a reload runs.
    proceed = threading.Event()
    started = threading.Event()
    real_load = reload_mod.load_extension
    n_readers = 16
    # Barrier of (n_readers + 1): each reader rendezvouses once before
    # starting the snapshot loop; the test thread is the +1 that signals
    # the reload to proceed only after every reader has hit the barrier.
    readers_ready = threading.Barrier(n_readers + 1, timeout=5.0)

    def slow_load(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        started.set()
        proceed.wait(timeout=5.0)
        return real_load(*args, **kwargs)

    monkeypatch.setattr(reload_mod, "load_extension", slow_load)

    observations: list[frozenset[str]] = []
    obs_lock = threading.Lock()

    def reader() -> None:
        readers_ready.wait()
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

    # Wait until every reader thread has hit the barrier (they are all
    # running their snapshot loop) BEFORE releasing the reload.  This is
    # deterministic where the previous sleep was load-sensitive.
    readers_ready.wait()
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


@pytest.fixture
def _isolated_post_swap_hooks() -> Iterable[None]:
    """Snapshot and restore the post-swap hook list.

    When the full lfx test suite runs, langflow startup may have already
    registered ``_post_reload_refresh_cache`` -- which then raises on these
    synthetic Component stubs (they don't inherit from the real lfx
    ``Component``) and contaminates ``ReloadResult.warnings``.  Tests that
    assert on warnings need a clean hook list.
    """
    snapshot = list(reload_mod._POST_SWAP_HOOKS)
    reload_mod._POST_SWAP_HOOKS.clear()
    try:
        yield
    finally:
        reload_mod._POST_SWAP_HOOKS.clear()
        reload_mod._POST_SWAP_HOOKS.extend(snapshot)


@pytest.mark.usefixtures("_isolated_post_swap_hooks")
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
    (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")
    result = reload_bundle(registry, "pilot")

    # Swap committed despite the hook failure.
    assert result.ok, result.errors
    assert registry.get_bundle("pilot").class_names == frozenset({"RenamedThing"})

    # The failure is surfaced as a typed warning, not an error.
    hook_warnings = [w for w in result.warnings if w.code == "reload-post-swap-hook-failed"]
    assert len(hook_warnings) == 1, result.warnings
    assert "synthetic hook failure" in hook_warnings[0].message


@pytest.mark.usefixtures("_isolated_post_swap_hooks")
def test_post_swap_hook_success_adds_no_warnings(tmp_path: Path) -> None:
    """The happy path emits no ``reload-post-swap-hook-failed`` warning.

    Regression guard against accidentally appending an error to the warnings
    list on every reload when no hook raised.
    """
    root = _write_extension(tmp_path, files={"thing.py": _component_source("PilotThing")})
    registry = BundleRegistry()
    _initial_install(registry, root)

    (root / "components" / "thing.py").write_text(_component_source("RenamedThing"), encoding="utf-8")
    result = reload_bundle(registry, "pilot")
    assert result.ok, result.errors
    assert not [w for w in result.warnings if w.code == "reload-post-swap-hook-failed"]


# ---------------------------------------------------------------------------
# Mid-rename rollback: BaseException leaves sys.modules byte-identical
# ---------------------------------------------------------------------------


def test_swap_rollback_on_mid_rename_baseexception_restores_sys_modules() -> None:
    """A ``BaseException`` raised mid-rename leaves ``sys.modules`` byte-identical.

    Regression guard for the partial-rename rollback window.  If an
    interrupt (``KeyboardInterrupt`` / ``SystemExit`` / ``MemoryError``)
    fires after one iteration of the rename loop has committed but
    before later iterations process, the ``except BaseException`` clause
    in :func:`lfx.extension.reload_swap.swap_sys_modules` must fully
    restore the pre-call state:

    * the just-renamed staging module must not be left bound at the
      prod name (the half-swap state);
    * the old prod module must be restored at its prod name;
    * the staging modules must be restored at their staging names;
    * ``module.__name__`` mutations that landed in earlier iterations
      must be reverted.

    The previous implementation used ``sys.modules.setdefault`` for the
    restore, which is a no-op on prod names the rename loop had already
    overwritten -- exactly the half-swap state the rollback is meant to
    prevent.  This test fails on that implementation and passes on the
    fix.
    """
    import types
    from pathlib import Path as _Path

    from lfx.extension import reload_swap
    from lfx.extension.bundle_registry import BundleRecord
    from lfx.extension.loader import SLOT_OFFICIAL, LoadedComponent

    target_ns = "_lfx_ext.rollback_pilot"
    staging_ns = "__reload_staging__.rollback_pilot"

    class _InterruptOnNameSet(types.ModuleType):
        """ModuleType whose ``__name__`` setter raises ``KeyboardInterrupt``.

        Simulates a ``BaseException`` firing partway through the rename
        loop's ``module.__name__ = prod_name`` assignment.
        """

        def __setattr__(self, key: str, value: object) -> None:
            if key == "__name__":
                raise KeyboardInterrupt
            object.__setattr__(self, key, value)

    # Pre-call sys.modules state: two old prod modules, two staging modules.
    # The first staging module renames cleanly; the second raises mid-rename.
    old_a = types.ModuleType(f"{target_ns}.a")
    old_b = types.ModuleType(f"{target_ns}.b")
    new_a = types.ModuleType(f"{staging_ns}.a")
    new_b = _InterruptOnNameSet(f"{staging_ns}.b")
    sys.modules[f"{target_ns}.a"] = old_a
    sys.modules[f"{target_ns}.b"] = old_b
    sys.modules[f"{staging_ns}.a"] = new_a
    sys.modules[f"{staging_ns}.b"] = new_b

    keys_in_scope = (
        f"{target_ns}.a",
        f"{target_ns}.b",
        f"{staging_ns}.a",
        f"{staging_ns}.b",
    )
    pre_state = {key: sys.modules.get(key) for key in keys_in_scope}
    pre_name_new_a = new_a.__name__
    pre_name_new_b = new_b.__name__

    def _lc(module_name: str, class_name: str) -> LoadedComponent:
        return LoadedComponent(
            extension_id="rollback-pilot",
            extension_version="0.0.0",
            bundle="rollback_pilot",
            class_name=class_name,
            slot=SLOT_OFFICIAL,
            klass=type(class_name, (), {}),
            module_name=module_name,
            file_path=_Path("/tmp/__rollback_pilot_synthetic__.py"),
        )

    previous = BundleRecord(
        bundle="rollback_pilot",
        extension_id="rollback-pilot",
        extension_version="0.0.0",
        slot=SLOT_OFFICIAL,
        components=(
            _lc(f"{target_ns}.a", "A"),
            _lc(f"{target_ns}.b", "B"),
        ),
    )

    with pytest.raises(KeyboardInterrupt):
        reload_swap.swap_sys_modules(
            previous=previous,
            new_components=[_lc(f"{target_ns}.a", "A"), _lc(f"{target_ns}.b", "B")],
            staging_components=[_lc(f"{staging_ns}.a", "A"), _lc(f"{staging_ns}.b", "B")],
        )

    # sys.modules is byte-identical for every key the swap could touch.
    # The critical assertion is that ``{target_ns}.a`` is *old_a* again,
    # not ``new_a`` (the half-swap state).
    post_state = {key: sys.modules.get(key) for key in keys_in_scope}
    assert post_state == pre_state, (
        f"sys.modules not byte-restored after mid-rename interrupt; "
        f"diff: {[(k, pre_state[k], post_state[k]) for k in keys_in_scope if pre_state[k] is not post_state[k]]}"
    )

    # ``module.__name__`` mutations have been reverted.
    assert new_a.__name__ == pre_name_new_a, "first-iteration __name__ mutation was not reverted on rollback"
    assert new_b.__name__ == pre_name_new_b, "second-iteration __name__ should have been left at the original value"

    # Cleanup (the autouse fixture handles ``_lfx_ext.*`` and
    # ``__reload_staging__.*`` regardless, but be explicit here).
    for key in keys_in_scope:
        sys.modules.pop(key, None)

"""Tests for the opt-in component class cache (``lfx.custom.class_cache``)."""

import inspect
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from lfx.custom import class_cache, validate
from lfx.custom.eval import eval_custom_component_code
from lfx.services.settings.base import Settings

import lfx

HEADER = """
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
"""


def make_source(name: str = "CacheProbeA", body: str = "return self.text", extra: str = "") -> str:
    return (
        HEADER
        + extra
        + f"""

class {name}(Component):
    display_name = "{name}"
    inputs = [MessageTextInput(name="text", display_name="Text", value="hello")]
    outputs = [Output(name="out", display_name="Out", method="run")]

    def run(self):
        {body}
"""
    )


def build(source: str, name: str | None = None):
    return eval_custom_component_code(source, class_name=name, reuse_class=True)


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LANGFLOW_COMPONENT_CLASS_CACHE_ENABLED", raising=False)
    settings = Settings()
    assert settings.component_class_cache_enabled is False
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: SimpleNamespace(settings=settings))
    monkeypatch.setattr(class_cache, "_is_reviewed", lambda _digest, _name: True)
    monkeypatch.setattr(class_cache, "_is_trusted_source", lambda _code: True)
    class_cache.clear_component_class_cache()
    class_cache.reset_component_class_cache_stats()
    source = make_source("DisabledProbe")
    first, second = build(source), build(source)
    assert first is not second
    assert class_cache.component_class_cache_stats()["hits"] == 0
    assert class_cache.component_class_cache_stats()["size"] == 0


@pytest.mark.usefixtures("cache_on")
def test_disabled_matches_plain_path_when_reuse_not_requested():
    source = make_source("PlainProbe")
    a = eval_custom_component_code(source)
    b = eval_custom_component_code(source)
    assert a is not b
    assert class_cache.component_class_cache_stats()["size"] == 0


@pytest.mark.usefixtures("cache_on")
def test_hit_returns_same_class_and_fresh_instances():
    source = make_source("HitProbe")
    first, second = build(source), build(source)
    assert first is second
    stats = class_cache.component_class_cache_stats()
    assert (stats["hits"], stats["misses"]) == (1, 1)
    one, two = first(), second()
    assert one is not two
    assert one.inputs is not two.inputs
    assert one.outputs is not two.outputs
    assert first.__name__ == "HitProbe"


@pytest.mark.usefixtures("cache_on")
def test_instance_mutation_does_not_leak_between_instances():
    cls = build(make_source("MutationProbe"))
    one, two = cls(), cls()
    one.inputs.append("junk")
    one.outputs.clear()
    one.inputs[0].value = "changed"
    one.set_attributes({"text": "changed"})
    one.custom_marker = 1
    three = build(make_source("MutationProbe"))()
    assert [i.name for i in three.inputs] == ["text"]
    assert three.inputs[0].value == "hello"
    assert [o.name for o in three.outputs] == ["out"]
    assert len(two.inputs) == 1
    assert not hasattr(three, "custom_marker")
    assert [i.name for i in cls.inputs] == ["text"]
    assert cls.inputs[0].value == "hello"


@pytest.mark.parametrize(
    ("other", "other_name"),
    [
        (make_source("MissProbe", body="return 'x'"), None),  # same class name, different body
        (make_source("MissProbe") + "\n", None),  # whitespace change
        (make_source("MissProbeB"), None),  # different class name
    ],
)
@pytest.mark.usefixtures("cache_on")
def test_different_source_misses(other, other_name):
    base = build(make_source("MissProbe"))
    assert build(other, other_name) is not base
    assert class_cache.component_class_cache_stats()["hits"] == 0


@pytest.mark.usefixtures("cache_on")
def test_same_source_different_resolved_class_name_misses():
    source = make_source("MultiOne") + "\n" + make_source("MultiTwo").split("lfx.io import MessageTextInput, Output")[1]
    one = build(source, "MultiOne")
    two = build(source, "MultiTwo")
    assert one is not two
    assert (one.__name__, two.__name__) == ("MultiOne", "MultiTwo")
    assert build(source, "MultiOne") is one


@pytest.mark.usefixtures("cache_on")
def test_hash_collision_still_compares_full_source(monkeypatch):
    monkeypatch.setattr(class_cache, "source_digest", lambda _s: "constant")
    a_src = make_source("CollideProbe", body="return 'a'")
    b_src = make_source("CollideProbe", body="return 'b'")
    a = build(a_src)
    b = build(b_src)
    assert a is not b
    assert b().run() == "b"
    assert build(a_src) is a
    assert build(b_src) is not a  # the colliding newcomer is never served the incumbent
    assert a().run() == "a"


@pytest.mark.usefixtures("cache_on")
def test_non_component_class_declined():
    source = (
        "from lfx.custom.custom_component.custom_component import CustomComponent\n\n"
        "class LegacyProbe(CustomComponent):\n    display_name = 'x'\n\n    def build(self):\n        return 1\n"
    )
    first, second = build(source), build(source)
    assert first is not second
    assert class_cache.component_class_cache_stats()["decline_reasons"].get("not_component_subclass", 0) >= 1


@pytest.mark.usefixtures("cache_on")
def test_exceptions_propagate_and_are_not_cached():
    bad = make_source("BadProbe", extra="import definitely_not_a_real_module_xyz\n")
    for _ in range(2):
        with pytest.raises((ValueError, ModuleNotFoundError), match="definitely_not_a_real_module_xyz"):
            build(bad)
    assert class_cache.component_class_cache_stats()["size"] == 0
    with pytest.raises(ValueError, match="Invalid Python code"):
        build(HEADER + "class SynProbe(Component):\n    x = (\n")


@pytest.mark.usefixtures("cache_on")
def test_exception_matches_uncached_path():
    bad = make_source("ErrParity", extra="import definitely_not_a_real_module_xyz\n")
    with pytest.raises(Exception) as plain:  # noqa: PT011
        eval_custom_component_code(bad)
    with pytest.raises(type(plain.value)) as cached:
        build(bad)
    assert str(cached.value) == str(plain.value)


@pytest.mark.usefixtures("cache_on")
def test_clear_invalidates():
    source = make_source("ClearProbe")
    first = build(source)
    class_cache.clear_component_class_cache()
    assert class_cache.component_class_cache_stats()["size"] == 0
    assert build(source) is not first


@pytest.mark.usefixtures("cache_on")
def test_extension_reload_hook_bumps_generation(monkeypatch):
    from lfx.interface import components as components_module

    monkeypatch.setattr(components_module, "refresh_bundle_cache_from_record", lambda _record: None)
    source = make_source("ReloadProbe")
    first = build(source)
    generation = class_cache.component_class_cache_stats()["generation"]
    components_module._post_reload_refresh_cache(SimpleNamespace(bundle="stub"))
    assert class_cache.component_class_cache_stats()["generation"] > generation
    assert build(source) is not first


@pytest.mark.usefixtures("cache_on")
def test_initial_registry_publish_clears_cache(monkeypatch):
    import asyncio

    from lfx.interface import components as components_module

    async def empty(*_a, **_k):
        return {}

    async def langflow(*_a, **_k):
        return {"components": {}}

    monkeypatch.setattr(components_module, "import_langflow_components", langflow)
    monkeypatch.setattr(components_module, "_determine_loading_strategy", empty)
    monkeypatch.setattr(components_module, "import_extension_components", empty)
    cache = components_module.ComponentCache()
    first = build(make_source("InitPublishProbe"))
    generation = class_cache.component_class_cache_stats()["generation"]

    async def run():
        await components_module._initialize_component_cache(cache, None, None, components_module.Future())

    asyncio.run(run())
    assert class_cache.component_class_cache_stats()["generation"] > generation
    assert build(make_source("InitPublishProbe")) is not first


@pytest.mark.usefixtures("cache_on")
def test_inflight_build_during_invalidation_is_not_stored():
    source = make_source("RaceProbe")
    name = validate.extract_class_name(source, None)

    def slow_build():
        cls = validate.create_class(source, name)
        class_cache.clear_component_class_cache()  # registry reloaded while building
        return cls

    class_cache.get_or_build_component_class(source, name, slow_build)
    assert class_cache.component_class_cache_stats()["size"] == 0


@pytest.mark.usefixtures("cache_on")
def test_concurrent_lookups_converge():
    source = make_source("ConcurrentProbe")
    barrier = threading.Barrier(20)

    def worker(_):
        barrier.wait()
        return build(source)

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(worker, range(20)))
    assert all(cls is results[0] for cls in results)
    stats = class_cache.component_class_cache_stats()
    assert stats["hits"] + stats["misses"] == 20
    assert stats["size"] == 1
    instances = [cls() for cls in results]  # keep alive so ids are unique
    assert len({id(instance) for instance in instances}) == 20


@pytest.mark.usefixtures("cache_on")
def test_stats_never_contain_source():
    marker = "TOTALLY_SECRET_MARKER_12345"
    build(make_source("StatsProbe", body=f"return '{marker}'"))
    declined = make_source("StatsProbe2", body=f"return '{marker}'")
    class_cache.get_or_build_component_class(declined, "StatsProbe2", object)  # builds a non-class: declined
    stats = repr(class_cache.component_class_cache_stats())
    assert marker not in stats
    assert class_cache.source_digest(declined) not in stats
    assert class_cache.component_class_cache_stats()["decline_reasons"] == {"not_component_subclass": 1}


def test_settings_service_toggle_enables_cache(monkeypatch):
    class _Settings:
        component_class_cache_enabled = True

    class _Service:
        settings = _Settings()

    monkeypatch.setattr("lfx.services.deps.get_settings_service", _Service)
    assert class_cache._cache_enabled() is True
    _Settings.component_class_cache_enabled = "true"  # only a real bool enables it
    assert class_cache._cache_enabled() is False
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
    assert class_cache._cache_enabled() is False


def test_registry_gate_requires_exact_source(monkeypatch):
    source = make_source("GateProbe")
    monkeypatch.setattr("lfx.utils.flow_validation.get_trusted_code_for_validation", lambda _code: source)
    assert class_cache._is_trusted_source(source) is True
    # A hash-colliding but different source must not pass: the full string is compared.
    assert class_cache._is_trusted_source(source + "\n# edited") is False
    monkeypatch.setattr("lfx.utils.flow_validation.get_trusted_code_for_validation", lambda _code: None)
    assert class_cache._is_trusted_source(source) is False

    def boom(_code):
        raise RuntimeError

    monkeypatch.setattr("lfx.utils.flow_validation.get_trusted_code_for_validation", boom)
    assert class_cache._is_trusted_source(source) is False


def test_trusted_registry_source_is_reused(monkeypatch):
    source = make_source("TrustedReuseProbe")
    monkeypatch.setattr(class_cache, "_cache_enabled", lambda: True)
    monkeypatch.setattr(class_cache, "_is_reviewed", lambda _digest, _name: True)
    monkeypatch.setattr("lfx.utils.flow_validation.get_trusted_code_for_validation", lambda _code: source)
    class_cache.clear_component_class_cache()
    class_cache.reset_component_class_cache_stats()
    assert build(source) is build(source)
    assert class_cache.component_class_cache_stats()["hits"] == 1


def test_disabled_policy_drops_retained_entries(monkeypatch):
    state = {"enabled": True}
    monkeypatch.setattr(class_cache, "_cache_enabled", lambda: state["enabled"])
    monkeypatch.setattr(class_cache, "_is_reviewed", lambda _digest, _name: True)
    monkeypatch.setattr(class_cache, "_is_trusted_source", lambda _code: True)
    class_cache.clear_component_class_cache()
    build(make_source("RetainProbe"))
    assert class_cache.component_class_cache_stats()["size"] == 1
    state["enabled"] = False
    build(make_source("RetainProbe"))
    assert class_cache.component_class_cache_stats()["size"] == 0


async def test_instantiate_class_end_to_end_with_real_settings(monkeypatch):
    """Real wiring: ``instantiate_class`` with the real settings flag, on a trusted shipped source."""
    from lfx.components.processing import create_list as shipped_module
    from lfx.interface.initialize.loading import instantiate_class

    source = inspect.getsource(shipped_module)
    monkeypatch.setenv("LANGFLOW_COMPONENT_CLASS_CACHE_ENABLED", "true")  # Settings ignores init kwargs
    settings = Settings()
    assert settings.component_class_cache_enabled is True
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: SimpleNamespace(settings=settings))
    # The component registry is not initialized in unit tests; seed its hash-to-source map so the real lookup runs.
    from lfx.interface.components import component_cache
    from lfx.utils.flow_validation import _compute_code_hash

    monkeypatch.setattr(component_cache, "code_by_hash", {_compute_code_hash(source): source})
    class_cache.clear_component_class_cache()
    class_cache.reset_component_class_cache_stats()
    assert class_cache._is_reviewed(class_cache.source_digest(source), "CreateListComponent")
    assert class_cache._is_trusted_source(source)

    def vertex(vertex_id: str):
        return SimpleNamespace(
            vertex_type="CreateListComponent",
            base_type="custom_components",
            params={"code": source},
            data={"type": "CreateListComponent"},
            id=vertex_id,
            outputs=[],
        )

    first, _ = instantiate_class(vertex("v1"))
    second, _ = instantiate_class(vertex("v2"))
    assert type(first) is type(second)
    assert first is not second
    assert first.inputs is not second.inputs
    expected_outputs = [o.name for o in shipped_module.CreateListComponent.outputs]
    assert [o.name for o in first.outputs] == [o.name for o in second.outputs] == expected_outputs
    stats = class_cache.component_class_cache_stats()
    assert (stats["hits"], stats["misses"]) == (1, 1)

    settings.component_class_cache_enabled = False
    third, _ = instantiate_class(vertex("v3"))
    assert type(third) is not type(first)
    assert [o.name for o in third.outputs] == expected_outputs


def _shipped_source(path: str) -> str:
    return (Path(lfx.__file__).parent / "components" / path).read_text(encoding="utf-8")


@pytest.mark.parametrize(("path", "class_name", "digest"), class_cache.REVIEWED_COMPONENTS)
def test_reviewed_pin_matches_shipped_file(path, class_name, digest):
    source = _shipped_source(path)
    assert class_cache.source_digest(source) == digest, (
        f"lfx/components/{path} changed since it was reviewed for class reuse. Check that it still keeps no state on "
        "the class or at module level, then update its sha256 in REVIEWED_COMPONENTS (or remove the entry)."
    )
    assert f"class {class_name}(" in source


def test_every_reviewed_component_is_in_the_shipped_component_index():
    """Otherwise the trusted-source gate would never pass and the reviewed entry would be dead."""
    index_path = Path(lfx.__file__).parent / "_assets" / "component_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    shipped = {
        component["template"]["code"]["value"]
        for _category, components in index["entries"]
        for component in components.values()
        if "code" in component.get("template", {})
    }
    for path, _class_name, _digest in class_cache.REVIEWED_COMPONENTS:
        assert _shipped_source(path) in shipped, path


@pytest.mark.parametrize(("path", "class_name", "digest"), class_cache.REVIEWED_COMPONENTS)
def test_reviewed_component_reuse_behaves_like_fresh_builds(monkeypatch, class_state, path, class_name, digest):
    source = _shipped_source(path)
    monkeypatch.setattr(class_cache, "_cache_enabled", lambda: True)
    monkeypatch.setattr(class_cache, "_is_trusted_source", lambda code: code == source)
    if class_cache.source_digest(source) != digest:
        pytest.skip("pin out of date; see test_reviewed_pin_matches_shipped_file")

    first = build(source, class_name)
    assert build(source, class_name) is first
    assert class_cache.component_class_cache_stats()["hits"] == 1
    before = class_state(first)

    used = first()
    used.to_frontend_node()
    for item in used.inputs:
        item.display_name = "changed"  # per-instance copies: must not reach the class or later instances
    fresh = first()
    assert fresh.inputs is not used.inputs
    uncached = eval_custom_component_code(source, class_name=class_name)()
    assert fresh.to_frontend_node()["data"]["node"] == uncached.to_frontend_node()["data"]["node"]
    assert class_state(first) == before


def test_reviewed_digests_are_unique():
    assert len(class_cache._REVIEWED_CLASS_BY_DIGEST) == len(class_cache.REVIEWED_COMPONENTS)


def test_unreviewed_sources_are_declined():
    path, class_name, digest = class_cache.REVIEWED_COMPONENTS[0]
    assert class_cache._is_reviewed(digest, class_name)
    assert not class_cache._is_reviewed(digest, "SomeOtherClass")  # a different class from the same file
    edited = class_cache.source_digest(_shipped_source(path) + "\n")
    assert not class_cache._is_reviewed(edited, class_name)  # any edit
    assert not class_cache._is_reviewed(class_cache.source_digest(make_source()), "CacheProbeA")


def test_unreviewed_source_takes_the_plain_path(monkeypatch):
    monkeypatch.setattr(class_cache, "_cache_enabled", lambda: True)
    monkeypatch.setattr(class_cache, "_is_trusted_source", lambda _code: True)
    source = make_source("UnreviewedProbe")
    assert build(source) is not build(source)
    stats = class_cache.component_class_cache_stats()
    assert (stats["size"], stats["decline_reasons"]) == (0, {"not_reviewed": 2})


def _run_create_list(component_class, texts):
    return [item.text for item in component_class(texts=texts).create_list()]


def _run_parser(component_class, rows, pattern):
    from lfx.schema.data import Data

    component = component_class(input_data=[Data(data=row) for row in rows], pattern=pattern, sep="|")
    component.update_build_config({"pattern": {}}, "Parser", "mode")
    return component.parse_combined_text().text


@pytest.mark.parametrize(
    ("path", "class_name", "run", "first_args", "second_args"),
    [
        ("processing/create_list.py", "CreateListComponent", _run_create_list, (["A"],), (["B", "C"],)),
        (
            "processing/parser.py",
            "ParserComponent",
            _run_parser,
            ([{"name": "x"}], "N={name}"),
            ([{"name": "y"}, {"name": "z"}], "<{name}>"),
        ),
    ],
)
def test_reviewed_component_outputs_match_uncached_across_runs(
    monkeypatch, class_state, path, class_name, run, first_args, second_args
):
    """A run on the cached class leaves nothing behind: the next run matches a freshly built class."""
    source = _shipped_source(path)
    monkeypatch.setattr(class_cache, "_cache_enabled", lambda: True)
    monkeypatch.setattr(class_cache, "_is_trusted_source", lambda code: code == source)

    cached = build(source, class_name)
    before = class_state(cached)
    run(cached, *first_args)
    assert build(source, class_name) is cached
    second = run(cached, *second_args)

    assert second == run(eval_custom_component_code(source, class_name=class_name), *second_args)
    assert class_state(cached) == before

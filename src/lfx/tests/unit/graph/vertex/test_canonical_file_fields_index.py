"""Tests for source-keyed canonical FileInput metadata indexing (#16263)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any
from unittest.mock import MagicMock

import pytest
from lfx.graph.vertex.param_handler import ParameterHandler
from lfx.interface import components as components_module
from lfx.interface.components import (
    _publish_bundle_cache,
    _scan_canonical_file_fields,
    build_canonical_file_fields_index,
    component_cache,
    get_canonical_file_fields_for_source,
)


def _make_handler(code: str | None, extra_template: dict[str, Any] | None = None) -> ParameterHandler:
    template: dict[str, Any] = {}
    if code is not None:
        template["code"] = {"value": code}
    if extra_template:
        template.update(extra_template)
    vertex = MagicMock()
    vertex.data = {"node": {"template": template}}
    return ParameterHandler(vertex, storage_service=None)


class _ObservableMapping(Mapping[str, Any]):
    """Custom Mapping that records every iteration/lookup to verify compatible scan fallback."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self.iter_count = 0
        self.getitem_count = 0

    def __getitem__(self, key: str) -> Any:
        self.getitem_count += 1
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        self.iter_count += 1
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


@pytest.fixture
def isolated_component_cache():
    """Save and restore global component_cache fields touched by these tests."""
    saved = (
        component_cache.all_types_dict,
        component_cache.all_types_ready,
        component_cache.canonical_file_fields_index,
        component_cache.code_by_hash,
        component_cache.type_to_current_hash,
        component_cache.all_known_hashes,
        component_cache.type_to_code,
        component_cache.component_identity_index,
        component_cache.upgrade_registry,
    )
    try:
        component_cache.all_types_dict = None
        component_cache.all_types_ready = False
        component_cache.canonical_file_fields_index = None
        component_cache.code_by_hash = None
        component_cache.type_to_current_hash = None
        component_cache.all_known_hashes = None
        component_cache.type_to_code = None
        component_cache.component_identity_index = None
        component_cache.upgrade_registry = None
        yield component_cache
    finally:
        (
            component_cache.all_types_dict,
            component_cache.all_types_ready,
            component_cache.canonical_file_fields_index,
            component_cache.code_by_hash,
            component_cache.type_to_current_hash,
            component_cache.all_known_hashes,
            component_cache.type_to_code,
            component_cache.component_identity_index,
            component_cache.upgrade_registry,
        ) = saved


def test_indexed_lookup_matches_scan_for_duplicates_precedence_and_shallow_aliases(isolated_component_cache):
    shared_src = "class Shared:\n    pass\n"
    nested_types = ["pdf", "txt"]
    raw_registry = {
        "cat_a": {
            "First": {
                "template": {
                    "code": {"value": shared_src},
                    "doc": {
                        "type": "file",
                        "_input_type": "FileInput",
                        "list": True,
                        "required": True,
                        "fileTypes": nested_types,
                    },
                }
            }
        },
        "cat_b": {
            "Second": {
                "template": {
                    "code": {"value": shared_src},
                    # Duplicate field name must retain first-field-wins from cat_a.First
                    "doc": {"type": "file", "list": False, "required": False},
                    # Second component contributes additional canonical file field
                    "extra": {"_input_type": "FileInput", "list": False, "required": True},
                }
            }
        },
    }

    isolated_component_cache.publish_all_types_dict(raw_registry)

    expected = _scan_canonical_file_fields(shared_src, raw_registry)
    first_result = _make_handler(shared_src)._canonical_file_fields()
    second_result = _make_handler(shared_src)._canonical_file_fields()

    assert first_result == expected
    assert first_result["doc"]["list"] is True
    assert first_result["doc"]["required"] is True
    assert "extra" in first_result
    # Fresh shallow field dictionaries per handler, preserving nested object aliases.
    assert first_result["doc"] is not second_result["doc"]
    assert first_result["doc"]["fileTypes"] is nested_types
    # Mutating a returned dict must not corrupt the cached index.
    first_result["doc"]["required"] = False
    assert _make_handler(shared_src)._canonical_file_fields()["doc"]["required"] is True


def test_nested_mutations_invalidate_cached_index_automatically(isolated_component_cache):
    src_a = "class CompA:\n    pass\n"
    src_b = "class CompB:\n    pass\n"
    tracked = isolated_component_cache.publish_all_types_dict(
        {
            "files": {
                "CompA": {
                    "template": {
                        "code": {"value": src_a},
                        "path": {"type": "file", "list": False, "required": True},
                    }
                }
            }
        }
    )

    assert set(_make_handler(src_a)._canonical_file_fields()) == {"path"}
    assert isolated_component_cache.canonical_file_fields_index is not None
    v0 = tracked.registry_version.value

    # 1. Nested field addition in place
    tracked["files"]["CompA"]["template"]["attachment"] = {"_input_type": "FileInput", "list": True}
    assert tracked.registry_version.value > v0
    fields_after_add = _make_handler(src_a)._canonical_file_fields()
    assert set(fields_after_add) == {"path", "attachment"}
    assert fields_after_add["attachment"]["list"] is True

    # 2. Nested field attribute mutation in place
    tracked["files"]["CompA"]["template"]["path"]["list"] = True
    assert _make_handler(src_a)._canonical_file_fields()["path"]["list"] is True

    # 3. Nested field removal in place
    del tracked["files"]["CompA"]["template"]["attachment"]
    assert set(_make_handler(src_a)._canonical_file_fields()) == {"path"}

    # 4. Source code edit in place
    tracked["files"]["CompA"]["template"]["code"]["value"] = src_b
    assert _make_handler(src_a)._canonical_file_fields() == {}
    assert set(_make_handler(src_b)._canonical_file_fields()) == {"path"}

    # 5. Component removal & reintroduction
    removed = tracked["files"].pop("CompA")
    assert _make_handler(src_b)._canonical_file_fields() == {}
    tracked["files"]["CompA"] = removed
    assert set(_make_handler(src_b)._canonical_file_fields()) == {"path"}


def test_registry_replacement_and_bundle_reload_invalidate_index(isolated_component_cache):
    src = "class Reloaded:\n    pass\n"
    isolated_component_cache.publish_all_types_dict(
        {
            "bundle_a": {
                "Reloaded": {
                    "template": {
                        "code": {"value": src},
                        "v1_file": {"type": "file", "required": True},
                    }
                }
            }
        }
    )
    assert set(_make_handler(src)._canonical_file_fields()) == {"v1_file"}

    # Bundle hot reload replaces snapshot copy-on-write and clears index.
    assert _publish_bundle_cache(
        "bundle_a",
        {
            "Reloaded": {
                "template": {
                    "code": {"value": src},
                    "v2_file": {"type": "file", "list": True},
                }
            }
        },
    )
    assert isolated_component_cache.canonical_file_fields_index is None
    fields = _make_handler(src)._canonical_file_fields()
    assert set(fields) == {"v2_file"}
    assert fields["v2_file"]["list"] is True

    # Direct replacement with empty / None registry releases stale index.
    isolated_component_cache.publish_all_types_dict({})
    assert _make_handler(src)._canonical_file_fields() == {}


def test_untracked_dict_and_custom_mapping_preserve_scan_and_never_go_stale(isolated_component_cache):
    src = "class Custom:\n    pass\n"
    inner_template = {"code": {"value": src}, "doc": {"type": "file", "required": False}}
    raw_dict = {"cat": {"Custom": {"template": inner_template}}}

    # Untracked plain dict assigned directly (bypassing publish_all_types_dict)
    isolated_component_cache.all_types_dict = raw_dict
    assert set(_make_handler(src)._canonical_file_fields()) == {"doc"}
    assert isolated_component_cache.canonical_file_fields_index is None
    # In-place edit on local alias must be visible immediately.
    inner_template["extra"] = {"_input_type": "FileInput", "list": True}
    assert set(_make_handler(src)._canonical_file_fields()) == {"doc", "extra"}

    # Custom Mapping retains observable lookup behavior (scan path).
    observable = _ObservableMapping(raw_dict)
    isolated_component_cache.all_types_dict = observable  # type: ignore[assignment]
    res1 = _make_handler(src)._canonical_file_fields()
    res2 = _make_handler(src)._canonical_file_fields()
    assert set(res1) == {"doc", "extra"}
    assert set(res2) == {"doc", "extra"}
    assert observable.iter_count >= 2
    assert isolated_component_cache.canonical_file_fields_index is None


def test_warmup_absent_empty_and_ast_fallback_preserve_security_classification(isolated_component_cache):
    ast_src = 'from lfx.io import FileInput\nclass Loader:\n    inputs = [FileInput(name="secret_path")]\n'
    # Registry warming (None) -> AST fallback still classifies FileInput.
    isolated_component_cache.all_types_dict = None
    fields = _make_handler(ast_src)._canonical_file_fields()
    assert "secret_path" in fields
    assert fields["secret_path"]["type"] == "file"

    # Empty/absent source -> empty result.
    assert _make_handler("")._canonical_file_fields() == {}
    assert _make_handler(None)._canonical_file_fields() == {}

    # Request-supplied metadata cannot downgrade canonical FileInput classification.
    server_src = "class InheritedFile:\n    pass\n"
    isolated_component_cache.publish_all_types_dict(
        {
            "files": {
                "InheritedFile": {
                    "template": {
                        "code": {"value": server_src},
                        "path": {"type": "file", "_input_type": "FileInput", "list": False, "required": True},
                    }
                }
            }
        }
    )
    spoofed_handler = _make_handler(
        server_src,
        extra_template={"path": {"type": "str", "_input_type": "StrInput", "value": "/etc/passwd", "list": True}},
    )
    effective = spoofed_handler._effective_file_field("path", spoofed_handler.template_dict["path"])
    assert effective["type"] == "file"
    assert effective["_input_type"] == "FileInput"
    assert effective["list"] is False
    assert effective["required"] is True
    assert effective["_canonical_file_input"] is True


def test_build_index_reused_across_handlers_without_rescanning(isolated_component_cache, monkeypatch):
    src = "class Indexed:\n    pass\n"
    isolated_component_cache.publish_all_types_dict(
        {
            "files": {
                "Indexed": {
                    "template": {
                        "code": {"value": src},
                        "doc": {"type": "file", "required": True},
                    }
                }
            }
        }
    )
    build_calls = 0
    real_build = build_canonical_file_fields_index

    def counting_build(reg):
        nonlocal build_calls
        build_calls += 1
        return real_build(reg)

    monkeypatch.setattr(components_module, "build_canonical_file_fields_index", counting_build)

    for _ in range(10):
        fields = _make_handler(src)._canonical_file_fields()
        assert set(fields) == {"doc"}
    assert build_calls == 1
    assert get_canonical_file_fields_for_source("nonexistent", isolated_component_cache.all_types_dict) == {}
    assert build_calls == 1

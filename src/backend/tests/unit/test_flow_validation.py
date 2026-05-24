"""Tests for flow validation utilities (lfx.utils.flow_validation).

Covers:
- Hash-based validation: blocked (unknown type) and outdated (hash mismatch)
- code_hash_matches_any_template utility
- check_flow_and_raise integration
- Nested/group node recursion
- Security: edited=False with custom code still gets blocked
- Shared alias generation for legacy built-in node types
- Unified flow validator behavior when custom components are disabled
"""

import hashlib
from types import SimpleNamespace

import pytest
from lfx.interface.components import component_cache
from lfx.utils.flow_validation import (
    CustomComponentValidationError,
    _compute_code_hash,
    _get_invalid_components,
    check_flow_and_raise,
    code_hash_matches_any_template,
    collect_component_hash_lookups,
    validate_flow_for_current_settings,
)

# ==================== Helpers ====================


def _hash(code: str) -> str:
    """Compute code hash the same way the component index does."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


def _make_node(
    *,
    node_type: str = "ChatInput",
    node_id: str = "node-1",
    code: str = "current_code",
    edited: bool = False,
    display_name: str | None = None,
    nested_nodes: list | None = None,
) -> dict:
    """Helper to build a flow node dict."""
    node_info = {
        "template": {"code": {"value": code}},
        "edited": edited,
    }
    if display_name:
        node_info["display_name"] = display_name
    if nested_nodes is not None:
        node_info["flow"] = {"data": {"nodes": nested_nodes}}
    return {
        "id": node_id,
        "data": {
            "type": node_type,
            "id": node_id,
            "node": node_info,
        },
    }


def _make_type_hash_dict(
    components: dict[str, str | list[str]] | None = None,
) -> dict[str, set[str]]:
    """Helper to build a type_to_current_hash dict.

    Args:
        components: dict of {component_type: code_string_or_list}
            The code is hashed to produce the expected hash.
            Pass a list of code strings to register multiple valid hashes per type.
    """
    if components is None:
        components = {
            "ChatInput": "chat_input_code",
            "ChatOutput": "chat_output_code",
        }
    result: dict[str, set[str]] = {}
    for comp_type, code in components.items():
        if isinstance(code, list):
            result[comp_type] = {_hash(c) for c in code}
        else:
            result[comp_type] = {_hash(code)}
    return result


# ==================== Tests ====================


class TestComputeCodeHash:
    def test_returns_12_char_hex(self):
        result = _compute_code_hash("some code")
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_consistent(self):
        assert _compute_code_hash("code") == _compute_code_hash("code")

    def test_different_codes_different_hashes(self):
        assert _compute_code_hash("code_a") != _compute_code_hash("code_b")


class TestGetInvalidComponents:
    def test_empty_nodes(self):
        blocked, outdated = _get_invalid_components([], {})
        assert blocked == []
        assert outdated == []

    def test_current_code_passes(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "current_code"})
        nodes = [_make_node(code="current_code", node_type="ChatInput")]
        blocked, outdated = _get_invalid_components(nodes, hash_dict)
        assert blocked == []
        assert outdated == []

    def test_unknown_type_is_blocked(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "code"})
        nodes = [_make_node(code="anything", node_type="TotallyCustom", display_name="Custom", node_id="n1")]
        blocked, outdated = _get_invalid_components(nodes, hash_dict)
        assert len(blocked) == 1
        assert "Custom" in blocked[0]
        assert outdated == []

    def test_hash_mismatch_is_outdated(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "v2_code"})
        nodes = [_make_node(code="v1_code", node_type="ChatInput", display_name="Chat Input")]
        blocked, outdated = _get_invalid_components(nodes, hash_dict)
        assert blocked == []
        assert len(outdated) == 1
        assert "Chat Input" in outdated[0]

    def test_edited_false_with_custom_code_still_blocked(self):
        """Security: edited=False does NOT prevent blocking when code is unknown type."""
        hash_dict = _make_type_hash_dict({"ChatInput": "legitimate_code"})
        nodes = [_make_node(code="evil_code", node_type="UnknownType", edited=False, display_name="Sneaky")]
        blocked, _outdated = _get_invalid_components(nodes, hash_dict)
        assert len(blocked) == 1
        assert "Sneaky" in blocked[0]

    def test_edited_false_with_modified_code_is_outdated(self):
        """Security: edited=False with modified code for a known type is caught as outdated."""
        hash_dict = _make_type_hash_dict({"ChatInput": "legitimate_code"})
        nodes = [_make_node(code="modified_code", node_type="ChatInput", edited=False, display_name="Sneaky")]
        blocked, outdated = _get_invalid_components(nodes, hash_dict)
        assert blocked == []
        assert len(outdated) == 1
        assert "Sneaky" in outdated[0]

    def test_nested_unknown_type_blocked(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "known"})
        inner = _make_node(code="anything", node_type="CustomType", display_name="Nested", node_id="inner")
        outer = _make_node(code="known", node_type="ChatInput", nested_nodes=[inner])
        blocked, _outdated = _get_invalid_components([outer], hash_dict)
        assert len(blocked) == 1
        assert "Nested" in blocked[0]

    def test_nested_outdated_detection(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "v2"})
        inner = _make_node(code="v1", node_type="ChatInput", display_name="Nested Chat")
        outer = _make_node(code="v2", node_type="ChatInput", nested_nodes=[inner])
        blocked, outdated = _get_invalid_components([outer], hash_dict)
        assert blocked == []
        assert len(outdated) == 1
        assert "Nested Chat" in outdated[0]

    def test_node_without_code_skipped(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "code"})
        node = {
            "data": {
                "type": "NoCodeNode",
                "node": {"template": {}},
            }
        }
        blocked, outdated = _get_invalid_components([node], hash_dict)
        assert blocked == []
        assert outdated == []


class TestCodeHashMatchesAnyTemplate:
    def test_matching_code(self):
        known = {_hash("my_code")}
        assert code_hash_matches_any_template("my_code", known) is True

    def test_non_matching_code(self):
        known = {_hash("my_code")}
        assert code_hash_matches_any_template("other_code", known) is False

    def test_empty_set(self):
        assert code_hash_matches_any_template("any", set()) is False


class TestCheckFlowAndRaise:
    def test_allows_when_custom_components_enabled(self):
        """Should not raise when allow_custom_components=True."""
        flow_data = {"nodes": [_make_node(code="custom_evil_code", edited=True)]}
        # Should not raise
        check_flow_and_raise(flow_data, allow_custom_components=True)

    def test_none_flow_data_ok(self):
        check_flow_and_raise(None, allow_custom_components=False)

    def test_empty_nodes_ok(self):
        check_flow_and_raise({"nodes": []}, allow_custom_components=False)

    def test_blocks_unknown_type(self):
        """Primary path: unknown component type is blocked even with edited=False."""
        hash_dict = _make_type_hash_dict({"ChatInput": "known_code"})
        flow_data = {"nodes": [_make_node(code="evil_code", node_type="CustomEvil", edited=False)]}
        with pytest.raises(CustomComponentValidationError, match="custom components are not allowed"):
            check_flow_and_raise(flow_data, allow_custom_components=False, type_to_current_hash=hash_dict)

    def test_blocks_outdated_components(self):
        """Primary path: outdated code (hash mismatch for known type) is blocked."""
        hash_dict = _make_type_hash_dict({"ChatInput": "v2_code"})
        flow_data = {"nodes": [_make_node(code="v1_code", node_type="ChatInput")]}
        with pytest.raises(CustomComponentValidationError, match="outdated components must be updated"):
            check_flow_and_raise(flow_data, allow_custom_components=False, type_to_current_hash=hash_dict)

    def test_allows_current_code(self):
        """Primary path: current code passes."""
        hash_dict = _make_type_hash_dict({"ChatInput": "current_code"})
        flow_data = {"nodes": [_make_node(code="current_code", node_type="ChatInput")]}
        # Should not raise
        check_flow_and_raise(flow_data, allow_custom_components=False, type_to_current_hash=hash_dict)

    def test_fail_closed_when_hash_dict_is_none(self):
        """When type_to_current_hash is None (cache not loaded), all flows are blocked.

        This is the fail-closed behavior: if we can't verify code against templates,
        we block execution rather than falling back to the client-controlled edited flag.
        """
        flow_data = {"nodes": [_make_node(edited=False)]}
        with pytest.raises(CustomComponentValidationError, match="component templates are still initializing"):
            check_flow_and_raise(flow_data, allow_custom_components=False)

    def test_fail_closed_blocks_edited_true_without_cache(self):
        """Fail-closed blocks even edited=True nodes when cache is unavailable."""
        flow_data = {"nodes": [_make_node(edited=True, display_name="Edited")]}
        with pytest.raises(CustomComponentValidationError, match="component templates are still initializing"):
            check_flow_and_raise(flow_data, allow_custom_components=False)

    def test_security_edited_false_custom_code_blocked(self):
        """Security test: a node with edited=False but modified code MUST be caught.

        This is the core security property — the edited flag is client-controlled
        and must not be trusted when type_to_current_hash is available.
        """
        hash_dict = _make_type_hash_dict({"ChatInput": "legitimate_code"})
        flow_data = {
            "nodes": [
                _make_node(
                    code="injected_malicious_code",
                    node_type="ChatInput",
                    edited=False,  # Attacker sets this to bypass checks
                    display_name="Innocent Looking",
                )
            ]
        }
        with pytest.raises(CustomComponentValidationError, match="outdated components must be updated"):
            check_flow_and_raise(flow_data, allow_custom_components=False, type_to_current_hash=hash_dict)


class TestValidateFlowForCurrentSettings:
    def test_validator_blocks_unknown_type(self, monkeypatch):
        settings_service = SimpleNamespace(settings=SimpleNamespace(allow_custom_components=False))
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: settings_service,
        )
        monkeypatch.setattr(
            component_cache,
            "type_to_current_hash",
            _make_type_hash_dict({"ChatInput": "known_code"}),
        )

        flow_data = {
            "nodes": [
                _make_node(
                    code="evil_code",
                    node_type="TotallyCustom",
                    display_name="Blocked Node",
                )
            ]
        }

        with pytest.raises(CustomComponentValidationError, match="custom components are not allowed"):
            validate_flow_for_current_settings(flow_data)

    def test_validator_fail_closed_when_component_hashes_missing(self, monkeypatch):
        settings_service = SimpleNamespace(settings=SimpleNamespace(allow_custom_components=False))
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: settings_service,
        )
        monkeypatch.setattr(component_cache, "type_to_current_hash", None)
        monkeypatch.setattr(component_cache, "all_types_dict", None)

        with pytest.raises(
            ValueError,
            match="component templates are still initializing",
        ):
            validate_flow_for_current_settings({"nodes": [_make_node()]})


class TestBuildCodeHashLookups:
    """Tests for _build_code_hash_lookups in lfx.interface.components."""

    def test_populates_hash_lookups_from_all_types_dict(self):
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        cache = ComponentCache()
        cache.all_types_dict = {
            "models": {
                "ChatInput": {
                    "metadata": {"code_hash": "abc123def456"},
                    "template": {"code": {"value": "code"}},
                },
                "ChatOutput": {
                    "metadata": {"code_hash": "789012ghijkl"},
                    "template": {"code": {"value": "code2"}},
                },
            }
        }
        _build_code_hash_lookups(cache)

        assert cache.type_to_current_hash is not None
        assert cache.type_to_current_hash["ChatInput"] == {"abc123def456"}
        assert cache.type_to_current_hash["ChatOutput"] == {"789012ghijkl"}
        assert cache.all_known_hashes == {"abc123def456", "789012ghijkl"}

    def test_skips_components_without_metadata(self):
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        cache = ComponentCache()
        cache.all_types_dict = {
            "models": {
                "NoMeta": {"template": {"code": {"value": "code"}}},
                "WithMeta": {"metadata": {"code_hash": "hash123hash1"}, "template": {}},
            }
        }
        _build_code_hash_lookups(cache)

        assert cache.type_to_current_hash is not None
        assert "NoMeta" not in cache.type_to_current_hash
        assert cache.type_to_current_hash["WithMeta"] == {"hash123hash1"}

    def test_skips_components_without_code_hash(self):
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        cache = ComponentCache()
        cache.all_types_dict = {
            "models": {
                "NoHash": {"metadata": {}, "template": {}},
            }
        }
        _build_code_hash_lookups(cache)

        assert cache.type_to_current_hash is not None
        assert "NoHash" not in cache.type_to_current_hash

    def test_empty_all_types_dict_is_noop(self):
        """Empty dict is falsy, so _build_code_hash_lookups treats it the same as None."""
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        cache = ComponentCache()
        cache.all_types_dict = {}
        _build_code_hash_lookups(cache)

        # Empty dict is falsy — early return, no change
        assert cache.type_to_current_hash is None
        assert cache.all_known_hashes is None

    def test_dict_with_empty_category_produces_empty_lookups(self):
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        cache = ComponentCache()
        cache.all_types_dict = {"models": {}}
        _build_code_hash_lookups(cache)

        assert cache.type_to_current_hash == {}
        assert cache.all_known_hashes == set()

    def test_none_all_types_dict_is_noop(self):
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        cache = ComponentCache()
        assert cache.type_to_current_hash is None
        _build_code_hash_lookups(cache)
        # Should remain None — no-op when all_types_dict is None
        assert cache.type_to_current_hash is None

    def test_prompt_alias_is_registered_for_legacy_prompt_nodes(self):
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        cache = ComponentCache()
        cache.all_types_dict = {
            "models_and_agents": {
                "Prompt Template": {
                    "metadata": {"code_hash": "prompthash12"},
                    "display_name": "Prompt Template",
                    "template": {"_type": "Component"},
                },
            }
        }
        _build_code_hash_lookups(cache)

        assert cache.type_to_current_hash is not None
        assert cache.type_to_current_hash["Prompt Template"] == {"prompthash12"}
        assert cache.type_to_current_hash["Prompt"] == {"prompthash12"}

    def test_legacy_alias_does_not_overwrite_direct_key(self):
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        cache = ComponentCache()
        cache.all_types_dict = {
            "category": {
                "Prompt": {
                    "metadata": {"code_hash": "directhash12"},
                    "template": {},
                },
                "Prompt Template": {
                    "metadata": {"code_hash": "renamedhash1"},
                    "display_name": "Prompt Template",
                    "template": {"_type": "Component"},
                },
            }
        }
        _build_code_hash_lookups(cache)

        assert cache.type_to_current_hash is not None
        assert cache.type_to_current_hash["Prompt"] == {"directhash12", "renamedhash1"}
        assert cache.type_to_current_hash["Prompt Template"] == {"renamedhash1"}

    def test_url_alias_allows_legacy_builtin_nodes(self):
        current_code = "current_url_code"
        all_types_dict = {
            "tools": {
                "URLComponent": {
                    "metadata": {"code_hash": _hash(current_code)},
                    "template": {
                        "_type": "URLComponent",
                        "code": {"value": current_code},
                    },
                }
            }
        }

        type_to_current_hash, all_known_hashes = collect_component_hash_lookups(all_types_dict)

        assert type_to_current_hash["URLComponent"] == {_hash(current_code)}
        assert type_to_current_hash["URL"] == {_hash(current_code)}
        assert all_known_hashes == {_hash(current_code)}

        flow_data = {
            "nodes": [
                _make_node(
                    code=current_code,
                    node_type="URL",
                    display_name="Legacy URL",
                )
            ]
        }

        check_flow_and_raise(
            flow_data,
            allow_custom_components=False,
            type_to_current_hash=type_to_current_hash,
        )

    def test_parser_alias_allows_legacy_builtin_nodes(self):
        current_code = "current_parser_code"
        all_types_dict = {
            "processing": {
                "ParserComponent": {
                    "metadata": {"code_hash": _hash(current_code)},
                    "display_name": "Parser",
                    "template": {
                        "_type": "Component",
                        "code": {"value": current_code},
                    },
                }
            }
        }

        type_to_current_hash, all_known_hashes = collect_component_hash_lookups(all_types_dict)

        assert type_to_current_hash["ParserComponent"] == {_hash(current_code)}
        assert type_to_current_hash["Parser"] == {_hash(current_code)}
        assert type_to_current_hash["parser"] == {_hash(current_code)}
        assert all_known_hashes == {_hash(current_code)}

        flow_data = {
            "nodes": [
                _make_node(
                    code=current_code,
                    node_type="parser",
                    display_name="Legacy Parser",
                )
            ]
        }

        check_flow_and_raise(
            flow_data,
            allow_custom_components=False,
            type_to_current_hash=type_to_current_hash,
        )

    def test_non_dict_values_in_all_types_dict_skipped(self):
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        cache = ComponentCache()
        cache.all_types_dict = {
            "models": {
                "Good": {"metadata": {"code_hash": "goodhash1234"}, "template": {}},
            },
            "not_a_dict": "some string",
        }
        _build_code_hash_lookups(cache)

        assert cache.type_to_current_hash is not None
        assert cache.type_to_current_hash["Good"] == {"goodhash1234"}


class TestCustomComponentsFromPathPassValidation:
    """Custom components loaded via components_path should be hashed and indexed.

    They pass validation even when allow_custom_components=False.
    This is the intended deployment model: operators set allow_custom_components=False
    to block arbitrary code, but their own approved components (loaded from
    components_path on startup) are still allowed because they're in the hash index.
    """

    def test_custom_component_passes_when_indexed(self):
        """A custom component from components_path should pass validation at startup."""
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        builtin_code = "class ChatInput(Component): ..."
        custom_code = "class MyCustomRAG(Component): ..."

        # Simulate startup: built-in + custom components merged into all_types_dict
        cache = ComponentCache()
        cache.all_types_dict = {
            "inputs": {
                "ChatInput": {
                    "metadata": {"code_hash": _hash(builtin_code)},
                    "template": {"code": {"value": builtin_code}},
                },
            },
            "custom_components": {
                "MyCustomRAG": {
                    "metadata": {"code_hash": _hash(custom_code)},
                    "template": {"code": {"value": custom_code}},
                },
            },
        }
        _build_code_hash_lookups(cache)

        assert cache.type_to_current_hash is not None
        assert "MyCustomRAG" in cache.type_to_current_hash

        # Flow uses the custom component — should pass with allow_custom_components=False
        flow_data = {
            "nodes": [
                _make_node(code=custom_code, node_type="MyCustomRAG", display_name="My RAG"),
            ]
        }
        check_flow_and_raise(
            flow_data,
            allow_custom_components=False,
            type_to_current_hash=cache.type_to_current_hash,
        )

    def test_custom_component_blocked_when_not_indexed(self):
        """A component NOT loaded from components_path should still be blocked."""
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        builtin_code = "class ChatInput(Component): ..."

        cache = ComponentCache()
        cache.all_types_dict = {
            "inputs": {
                "ChatInput": {
                    "metadata": {"code_hash": _hash(builtin_code)},
                    "template": {"code": {"value": builtin_code}},
                },
            },
        }
        _build_code_hash_lookups(cache)

        # Flow uses a component that was never loaded — should be blocked
        flow_data = {
            "nodes": [
                _make_node(
                    code="class Sneaky(Component): ...",
                    node_type="Sneaky",
                    display_name="Sneaky",
                ),
            ]
        }
        with pytest.raises(CustomComponentValidationError, match="custom components are not allowed"):
            check_flow_and_raise(
                flow_data,
                allow_custom_components=False,
                type_to_current_hash=cache.type_to_current_hash,
            )

    def test_modified_custom_component_detected_as_outdated(self):
        """Modified custom component code is detected as outdated."""
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        original_code = "class MyCustomRAG(Component): pass"
        tampered_code = "class MyCustomRAG(Component): import os; os.system('rm -rf /')"

        cache = ComponentCache()
        cache.all_types_dict = {
            "custom_components": {
                "MyCustomRAG": {
                    "metadata": {"code_hash": _hash(original_code)},
                    "template": {"code": {"value": original_code}},
                },
            },
        }
        _build_code_hash_lookups(cache)

        flow_data = {
            "nodes": [
                _make_node(code=tampered_code, node_type="MyCustomRAG", display_name="Tampered RAG"),
            ]
        }
        with pytest.raises(CustomComponentValidationError, match="outdated components must be updated"):
            check_flow_and_raise(
                flow_data,
                allow_custom_components=False,
                type_to_current_hash=cache.type_to_current_hash,
            )

    def test_mixed_builtin_and_custom_flow(self):
        """A flow mixing built-in and custom components should pass when all are indexed."""
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        builtin_code = "class ChatInput(Component): ..."
        custom_code = "class MyCustomRAG(Component): ..."

        cache = ComponentCache()
        cache.all_types_dict = {
            "inputs": {
                "ChatInput": {
                    "metadata": {"code_hash": _hash(builtin_code)},
                    "template": {"code": {"value": builtin_code}},
                },
            },
            "custom_components": {
                "MyCustomRAG": {
                    "metadata": {"code_hash": _hash(custom_code)},
                    "template": {"code": {"value": custom_code}},
                },
            },
        }
        _build_code_hash_lookups(cache)

        flow_data = {
            "nodes": [
                _make_node(code=builtin_code, node_type="ChatInput", node_id="n1"),
                _make_node(code=custom_code, node_type="MyCustomRAG", node_id="n2", display_name="My RAG"),
            ]
        }
        # Should not raise — both components are in the index
        check_flow_and_raise(
            flow_data,
            allow_custom_components=False,
            type_to_current_hash=cache.type_to_current_hash,
        )

    def test_duplicate_name_both_versions_accepted(self):
        """Duplicate component names accept both built-in and custom hashes."""
        from lfx.interface.components import ComponentCache, _build_code_hash_lookups

        builtin_code = "class CustomComponent(Component): pass  # built-in"
        custom_code = "class CustomComponent(Component): pass  # user version"

        cache = ComponentCache()
        cache.all_types_dict = {
            "custom_component": {
                "CustomComponent": {
                    "metadata": {"code_hash": _hash(builtin_code)},
                    "template": {"code": {"value": builtin_code}},
                },
            },
            "custom_comps": {
                "CustomComponent": {
                    "metadata": {"code_hash": _hash(custom_code)},
                    "template": {"code": {"value": custom_code}},
                },
            },
        }
        _build_code_hash_lookups(cache)

        # Both hashes should be registered for the same type
        assert cache.type_to_current_hash is not None
        assert _hash(builtin_code) in cache.type_to_current_hash["CustomComponent"]
        assert _hash(custom_code) in cache.type_to_current_hash["CustomComponent"]

        # Flow using the built-in version should pass
        check_flow_and_raise(
            {"nodes": [_make_node(code=builtin_code, node_type="CustomComponent")]},
            allow_custom_components=False,
            type_to_current_hash=cache.type_to_current_hash,
        )

        # Flow using the custom version should also pass
        check_flow_and_raise(
            {"nodes": [_make_node(code=custom_code, node_type="CustomComponent")]},
            allow_custom_components=False,
            type_to_current_hash=cache.type_to_current_hash,
        )

        # Flow using a tampered version should still be blocked
        with pytest.raises(CustomComponentValidationError, match="outdated"):
            check_flow_and_raise(
                {"nodes": [_make_node(code="tampered code", node_type="CustomComponent")]},
                allow_custom_components=False,
                type_to_current_hash=cache.type_to_current_hash,
            )

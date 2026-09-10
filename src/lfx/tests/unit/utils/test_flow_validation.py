"""Unit tests for LFX flow validation helpers."""

import asyncio
import copy
import hashlib
import json
import re
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.services.catalog_policy import CatalogPolicySnapshot
from lfx.utils.component_aliases import build_component_identity_index
from lfx.utils.flow_validation import (
    CODE_EXECUTION_COMPONENT_TYPES,
    CODE_EXECUTION_FIELD_NAMES,
    FLOW_REFERENCE_COMPONENT_TYPES,
    PROTECTED_TWEAK_FIELDS_BY_COMPONENT,
    CatalogPolicyIdentityUnavailableError,
    CatalogPolicyValidationError,
    CustomComponentValidationError,
    PublicFlowValidationError,
    collect_catalog_component_keys,
    collect_component_code_lookups,
    ensure_component_hash_lookups_loaded,
    prepare_public_flow_build,
    validate_catalog_policy_for_component_code,
    validate_catalog_policy_for_component_type,
    validate_catalog_policy_for_flow,
    validate_flow_for_current_settings,
    validate_public_flow_no_code_execution,
)


def _blocked_raw_graph() -> dict:
    return {
        "nodes": [
            {
                "id": "node-1",
                "data": {
                    "id": "node-1",
                    "type": "TotallyCustom",
                    "node": {
                        "display_name": "Blocked Node",
                        "template": {
                            "code": {"value": "print('blocked')"},
                        },
                    },
                },
            }
        ],
        "edges": [],
    }


@pytest.mark.asyncio
async def test_ensure_component_hash_lookups_loaded_requires_settings_service(monkeypatch):
    """Hash warmup should fail loudly when the settings service is unavailable."""
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)

    with pytest.raises(RuntimeError, match="Settings service must be initialized"):
        await ensure_component_hash_lookups_loaded()


@pytest.mark.asyncio
async def test_ensure_component_hash_lookups_loaded_surfaces_loader_failures(monkeypatch):
    """Loader failures should not be masked as a transient initialization state."""
    from lfx.interface.components import component_cache

    settings_service = SimpleNamespace(
        settings=SimpleNamespace(allow_custom_components=False),
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr(component_cache, "all_types_dict", None)
    monkeypatch.setattr(component_cache, "all_types_ready", False)
    monkeypatch.setattr(component_cache, "type_to_current_hash", None)

    with (
        patch(
            "lfx.interface.components.get_and_cache_all_types_dict",
            new=AsyncMock(side_effect=RuntimeError("component import failed")),
        ),
        pytest.raises(RuntimeError, match="component import failed"),
    ):
        await ensure_component_hash_lookups_loaded()


@pytest.mark.asyncio
async def test_ensure_component_hash_lookups_loaded_force_loads_in_permissive_mode(monkeypatch):
    """Caller-specific policy can require hashes even when custom components are globally enabled."""
    from lfx.interface.components import component_cache
    from lfx.utils import flow_validation as fv

    trusted_code = "# trusted component"
    trusted_hash = fv._compute_code_hash(trusted_code)
    all_types_dict = {
        "inputs": {
            "ChatInput": {
                "metadata": {"code_hash": trusted_hash},
                "template": {"code": {"value": trusted_code}},
            }
        }
    }
    settings_service = SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True))
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr(component_cache, "all_types_dict", None)
    monkeypatch.setattr(component_cache, "all_types_ready", False)
    monkeypatch.setattr(component_cache, "type_to_current_hash", None)
    monkeypatch.setattr(component_cache, "all_known_hashes", None)
    monkeypatch.setattr(component_cache, "code_by_hash", None)

    async def load_components(_settings_service):
        with component_cache.state_lock:
            component_cache.all_types_dict = all_types_dict
            component_cache.all_types_ready = True
        return all_types_dict

    monkeypatch.setattr("lfx.interface.components.get_and_cache_all_types_dict", load_components)

    lookups = await ensure_component_hash_lookups_loaded(force=True)

    assert lookups == {"ChatInput": {trusted_hash}}
    assert component_cache.code_by_hash == {trusted_hash: trusted_code}


@pytest.mark.asyncio
async def test_prepare_admin_only_flow_build_blocks_modified_known_component(monkeypatch):
    """A regular user cannot relabel modified code as a built-in component in admin-only mode."""
    from lfx.utils import flow_validation as fv

    trusted_code = "# trusted ChatInput code"
    trusted_hash = fv._compute_code_hash(trusted_code)
    monkeypatch.setattr(
        fv,
        "ensure_component_hash_lookups_loaded",
        AsyncMock(return_value={"ChatInput": {trusted_hash}}),
    )

    flow = {"nodes": [_node("custom", "ChatInput", "# modified code")], "edges": []}
    with pytest.raises(CustomComponentValidationError, match="outdated components"):
        await fv.prepare_admin_only_flow_build(flow)


@pytest.mark.asyncio
async def test_prepare_admin_only_flow_build_substitutes_server_source(monkeypatch):
    """Even a matching request hash is replaced with the server's source before build."""
    from lfx.utils import flow_validation as fv

    submitted_code = "# request bytes with a matching truncated hash"
    trusted_code = "# server-trusted component source"
    monkeypatch.setattr(fv, "_compute_code_hash", lambda _code: "same-hash")
    monkeypatch.setattr(
        fv,
        "ensure_component_hash_lookups_loaded",
        AsyncMock(return_value={"ChatInput": {"same-hash"}}),
    )
    monkeypatch.setattr(fv, "get_trusted_code_for_validation", lambda _code: trusted_code)

    flow = {"nodes": [_node("known", "ChatInput", submitted_code)], "edges": []}
    sanitized = await fv.prepare_admin_only_flow_build(flow)

    assert sanitized is not None
    assert sanitized["nodes"][0]["data"]["node"]["template"]["code"]["value"] == trusted_code
    assert flow["nodes"][0]["data"]["node"]["template"]["code"]["value"] == submitted_code


@pytest.mark.asyncio
async def test_prepare_admin_only_flow_build_fails_closed_without_trusted_source(monkeypatch):
    """A matching hash is insufficient when the server cannot recover trusted source bytes."""
    from lfx.utils import flow_validation as fv

    code = "# known hash"
    code_hash = fv._compute_code_hash(code)
    monkeypatch.setattr(
        fv,
        "ensure_component_hash_lookups_loaded",
        AsyncMock(return_value={"ChatInput": {code_hash}}),
    )
    monkeypatch.setattr(fv, "get_trusted_code_for_validation", lambda _code: None)

    flow = {"nodes": [_node("known", "ChatInput", code)], "edges": []}
    with pytest.raises(CustomComponentValidationError, match="no trusted server component"):
        await fv.prepare_admin_only_flow_build(flow)


def _configure_admin_only_outdated_substitution(monkeypatch):
    """Configure the cumulative restricted + admin-only policy around one known component."""
    from lfx.utils import flow_validation as fv

    current_code = "# current ChatInput code"
    current_hash = fv._compute_code_hash(current_code)
    type_to_hash = {"ChatInput": {current_hash}}
    type_to_code = {"ChatInput": current_code}
    settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=False,
            substitute_outdated_component_code=True,
            block_code_interpreter_components=False,
            custom_component_admin_only=True,
        )
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr(
        "lfx.services.deps.get_catalog_policy_service",
        lambda: SimpleNamespace(snapshot=CatalogPolicySnapshot()),
    )
    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: type_to_hash)
    monkeypatch.setattr(fv, "get_component_code_lookups_for_validation", lambda: type_to_code)
    monkeypatch.setattr(fv, "get_trusted_code_for_validation", lambda _code: current_code)
    monkeypatch.setattr(fv, "ensure_component_hash_lookups_loaded", AsyncMock(return_value=type_to_hash))
    return current_code


@pytest.mark.asyncio
async def test_prepare_flow_build_for_user_keeps_outdated_substitution_cumulative(monkeypatch):
    """Admin-only mode must preserve restricted mode's trusted drift substitution."""
    from lfx.utils import flow_validation as fv

    current_code = _configure_admin_only_outdated_substitution(monkeypatch)
    stored_code = "# outdated ChatInput code"
    flow = {"nodes": [_node("known", "ChatInput", stored_code)], "edges": []}

    sanitized = await fv.prepare_flow_build_for_user(flow, is_superuser=False)

    assert sanitized is not None
    assert sanitized["nodes"][0]["data"]["node"]["template"]["code"]["value"] == current_code
    assert flow["nodes"][0]["data"]["node"]["template"]["code"]["value"] == stored_code


def test_prepare_flow_build_for_user_from_cache_keeps_outdated_substitution_cumulative(monkeypatch):
    """The V2/AG-UI cache-only gate must apply the same cumulative policy."""
    from lfx.utils import flow_validation as fv

    current_code = _configure_admin_only_outdated_substitution(monkeypatch)
    stored_code = "# outdated ChatInput code"
    flow = {"nodes": [_node("known", "ChatInput", stored_code)], "edges": []}

    sanitized = fv.prepare_flow_build_for_user_from_cache(flow, is_superuser=False)

    assert sanitized is not None
    assert sanitized["nodes"][0]["data"]["node"]["template"]["code"]["value"] == current_code
    assert flow["nodes"][0]["data"]["node"]["template"]["code"]["value"] == stored_code


@pytest.mark.asyncio
async def test_prepare_flow_build_for_user_keeps_code_interpreter_policy_cumulative(monkeypatch):
    """Admin-only sanitization must not disable the separate code-interpreter gate."""
    from lfx.utils import flow_validation as fv

    code = "print('builtin component')"
    code_hash = fv._compute_code_hash(code)
    settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=True,
            block_code_interpreter_components=True,
            custom_component_admin_only=True,
        )
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr(
        fv,
        "ensure_component_hash_lookups_loaded",
        AsyncMock(return_value={"PythonREPLComponent": {code_hash}}),
    )

    with pytest.raises(CustomComponentValidationError, match="code-execution components are not allowed"):
        await fv.prepare_flow_build_for_user(_code_interpreter_raw_graph(), is_superuser=False)


def _malformed_inline_graphs() -> list[dict]:
    return [
        {"nodes": [["not-a-node"]], "edges": []},
        {"nodes": {}, "edges": []},
        {"nodes": None, "edges": []},
        {
            "nodes": [
                {
                    "id": "wrapper",
                    "data": {
                        "type": "GroupNode",
                        "node": {"flow": {"data": "not-flow-data"}},
                    },
                }
            ],
            "edges": [],
        },
        {
            "nodes": [
                {
                    "id": "wrapper",
                    "data": {
                        "type": "GroupNode",
                        "node": {"flow": {"data": {"nodes": {}}}},
                    },
                }
            ],
            "edges": [],
        },
        {
            "nodes": [
                {
                    "id": "bad-template",
                    "data": {
                        "type": "ChatInput",
                        "node": {"template": "not-a-template"},
                    },
                }
            ],
            "edges": [],
        },
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("flow", _malformed_inline_graphs())
async def test_prepare_flow_build_for_user_maps_malformed_shapes_to_policy_error(monkeypatch, flow):
    """The cumulative async gate fails closed for malformed top-level and nested request shapes."""
    from lfx.utils import flow_validation as fv

    settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=True,
            block_code_interpreter_components=True,
            custom_component_admin_only=True,
        )
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr(fv, "ensure_component_hash_lookups_loaded", AsyncMock(return_value={}))

    with pytest.raises(CustomComponentValidationError):
        await fv.prepare_flow_build_for_user(flow, is_superuser=False)


@pytest.mark.parametrize("flow", _malformed_inline_graphs())
def test_prepare_flow_build_for_user_from_cache_maps_malformed_shapes_to_policy_error(monkeypatch, flow):
    """The synchronous V2 gate maps malformed payloads to the normal policy error type."""
    from lfx.utils import flow_validation as fv

    settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=True,
            block_code_interpreter_components=True,
            custom_component_admin_only=True,
        )
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", dict)

    with pytest.raises(CustomComponentValidationError):
        fv.prepare_flow_build_for_user_from_cache(flow, is_superuser=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "nodes",
    [
        [["not-a-node"]],
        [{"id": "bad", "data": "not-node-data"}],
        [
            {
                "id": "wrapper",
                "data": {
                    "id": "wrapper",
                    "type": "GroupNode",
                    "node": {"flow": {"data": {"nodes": [["not-a-nested-node"]]}}},
                },
            }
        ],
    ],
)
async def test_prepare_admin_only_flow_build_maps_malformed_nodes_to_policy_error(monkeypatch, nodes):
    """Malformed top-level and nested shapes fail closed without leaking TypeError/AttributeError."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr(fv, "ensure_component_hash_lookups_loaded", AsyncMock(return_value={}))

    with pytest.raises(CustomComponentValidationError, match="custom components are not allowed"):
        await fv.prepare_admin_only_flow_build({"nodes": nodes, "edges": []})


def test_validate_flow_for_current_settings_requires_settings_service(monkeypatch):
    """Unified validation should also require the settings service."""
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
    graph = SimpleNamespace(raw_graph_data=_blocked_raw_graph())

    with pytest.raises(RuntimeError, match="Settings service must be initialized"):
        validate_flow_for_current_settings(graph)


def _catalog_flow(*component_types: str) -> dict:
    return {
        "nodes": [
            {
                "id": f"{component_type}-1",
                "data": {
                    "id": f"{component_type}-1",
                    "type": component_type,
                    "node": {"template": {}},
                },
            }
            for component_type in component_types
        ],
        "edges": [],
    }


ASTRADB_KEY = "ext:datastax:AstraDBVectorStoreComponent@official"  # pragma: allowlist secret


def _catalog_registry() -> dict:
    return {
        "models_and_agents": {
            "Prompt Template": {
                "name": "Prompt Template",
                "display_name": "Prompt Template",
                "metadata": {"module": "lfx.components.models_and_agents.prompt.PromptComponent"},
                "template": {"_type": "Component"},
            }
        },
        "input_output": {
            "ChatInput": {
                "display_name": "Chat Input",
                "metadata": {"module": "lfx.components.input_output.chat.ChatInput"},
                "template": {"_type": "Component"},
            }
        },
        "datastax": {
            ASTRADB_KEY: {
                "name": "AstraDB",
                "display_name": "Astra DB",
                "metadata": {
                    "module": "lfx_datastax.components.datastax.astradb_vectorstore.AstraDBVectorStoreComponent"
                },
                "template": {"_type": "Component"},
            }
        },
    }


def _catalog_identity_index():
    return build_component_identity_index(_catalog_registry())


@pytest.mark.asyncio
async def test_standalone_warmup_loads_catalog_identities_when_custom_components_are_allowed(monkeypatch):
    """An active catalog rule must warm aliases even in permissive custom-code mode."""
    from lfx.interface.components import component_cache

    snapshot = CatalogPolicySnapshot(blocked_component_keys={"Prompt Template"})
    settings_service = SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True))
    catalog_service = SimpleNamespace(snapshot=snapshot)

    async def populate_component_cache(_settings_service):
        with component_cache.state_lock:
            component_cache.all_types_dict = _catalog_registry()
            component_cache.all_types_ready = True
        return component_cache.all_types_dict

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr("lfx.services.deps.get_catalog_policy_service", lambda: catalog_service)
    monkeypatch.setattr(component_cache, "all_types_dict", None)
    monkeypatch.setattr(component_cache, "all_types_ready", False)
    monkeypatch.setattr(component_cache, "type_to_current_hash", None)
    monkeypatch.setattr(component_cache, "all_known_hashes", None)
    monkeypatch.setattr(component_cache, "code_by_hash", None)
    monkeypatch.setattr(component_cache, "component_identity_index", None)

    with patch(
        "lfx.interface.components.get_and_cache_all_types_dict",
        new=AsyncMock(side_effect=populate_component_cache),
    ) as loader:
        assert await ensure_component_hash_lookups_loaded() == {}

    loader.assert_awaited_once_with(settings_service)
    validate_catalog_policy_for_flow(_catalog_flow("Chat Input"), snapshot=snapshot)
    with pytest.raises(CatalogPolicyValidationError, match="Prompt Template"):
        validate_catalog_policy_for_flow(_catalog_flow("PromptComponent"), snapshot=snapshot)


@pytest.mark.asyncio
async def test_standalone_warmup_fails_closed_when_published_registry_is_empty(monkeypatch):
    """An empty published registry cannot satisfy active alias-aware catalog policy."""
    from lfx.interface.components import component_cache

    snapshot = CatalogPolicySnapshot(blocked_component_keys={"Prompt Template"})
    settings_service = SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True))
    catalog_service = SimpleNamespace(snapshot=snapshot)

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr("lfx.services.deps.get_catalog_policy_service", lambda: catalog_service)
    monkeypatch.setattr(component_cache, "all_types_dict", {})
    monkeypatch.setattr(component_cache, "all_types_ready", True)
    monkeypatch.setattr(component_cache, "type_to_current_hash", {})
    monkeypatch.setattr(component_cache, "all_known_hashes", set())
    monkeypatch.setattr(component_cache, "code_by_hash", {})
    monkeypatch.setattr(component_cache, "component_identity_index", None)

    with (
        patch("lfx.interface.components.get_and_cache_all_types_dict", new=AsyncMock()) as loader,
        pytest.raises(CatalogPolicyIdentityUnavailableError, match="identities are still initializing"),
    ):
        await ensure_component_hash_lookups_loaded()

    loader.assert_not_awaited()


def test_catalog_policy_validation_blocks_top_level_components_deterministically():
    snapshot = CatalogPolicySnapshot(blocked_component_keys=frozenset({"Zed", "Agent"}))

    with pytest.raises(CatalogPolicyValidationError, match=r"Agent, Zed$"):
        validate_catalog_policy_for_flow(_catalog_flow("Zed", "Agent", "Zed"), snapshot=snapshot)


def test_catalog_policy_validation_blocks_nested_components():
    flow = _catalog_flow("Group")
    flow["nodes"][0]["data"]["node"]["flow"] = {"data": _catalog_flow("NestedBlocked")}
    snapshot = CatalogPolicySnapshot(blocked_component_keys=frozenset({"NestedBlocked"}))

    with pytest.raises(CatalogPolicyValidationError, match="NestedBlocked"):
        validate_catalog_policy_for_flow(flow, snapshot=snapshot)


def test_catalog_policy_validation_is_exact_case_sensitive_and_empty_snapshot_allows(monkeypatch):
    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_identity_index_for_validation",
        lambda: _catalog_identity_index(),
    )
    validate_catalog_policy_for_flow(
        _catalog_flow("agent"),
        snapshot=CatalogPolicySnapshot(blocked_component_keys=frozenset({"Agent"})),
    )
    validate_catalog_policy_for_flow(_catalog_flow("Agent"), snapshot=CatalogPolicySnapshot())


@pytest.mark.parametrize(
    ("blocked_identity", "flow_identity", "canonical"),
    [
        ("Prompt Template", "Prompt", "Prompt Template"),
        ("Prompt", "PromptComponent", "Prompt Template"),
        ("PromptComponent", "Prompt Template", "Prompt Template"),
        (ASTRADB_KEY, "AstraDB", ASTRADB_KEY),
        ("AstraDB", ASTRADB_KEY, ASTRADB_KEY),
        ("Chat Input", "ChatInput", "ChatInput"),
    ],
)
def test_catalog_policy_flow_validation_resolves_canonical_and_legacy_identities(
    monkeypatch,
    blocked_identity,
    flow_identity,
    canonical,
):
    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_identity_index_for_validation",
        lambda: _catalog_identity_index(),
    )

    with pytest.raises(CatalogPolicyValidationError, match=canonical):
        validate_catalog_policy_for_flow(
            _catalog_flow(flow_identity),
            snapshot=CatalogPolicySnapshot(blocked_component_keys={blocked_identity}),
        )


def test_catalog_policy_alias_validation_fails_closed_without_component_identity_cache(monkeypatch):
    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_identity_index_for_validation",
        lambda: None,
    )

    # Exact identities remain enforceable without the registry cache.
    with pytest.raises(CatalogPolicyValidationError, match="ExactBlocked"):
        validate_catalog_policy_for_flow(
            _catalog_flow("ExactBlocked"),
            snapshot=CatalogPolicySnapshot(blocked_component_keys={"ExactBlocked"}),
        )

    # A non-exact decision needs the canonical alias index and fails closed
    # under the same initialization contract as component-code validation.
    with pytest.raises(CatalogPolicyIdentityUnavailableError, match="identities are still initializing"):
        validate_catalog_policy_for_flow(
            _catalog_flow("Prompt"),
            snapshot=CatalogPolicySnapshot(blocked_component_keys={"Prompt Template"}),
        )


def test_catalog_policy_alias_validation_fails_closed_with_empty_published_registry(monkeypatch):
    """A ready-but-empty registry cannot satisfy alias-aware catalog policy."""
    from lfx.interface.components import component_cache

    monkeypatch.setattr(component_cache, "all_types_dict", {})
    monkeypatch.setattr(component_cache, "all_types_ready", True)
    monkeypatch.setattr(component_cache, "component_identity_index", None)

    with pytest.raises(CatalogPolicyIdentityUnavailableError, match="identities are still initializing"):
        validate_catalog_policy_for_flow(
            _catalog_flow("Prompt"),
            snapshot=CatalogPolicySnapshot(blocked_component_keys={"Prompt Template"}),
        )


def test_catalog_policy_validation_blocks_nested_legacy_alias(monkeypatch):
    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_identity_index_for_validation",
        lambda: _catalog_identity_index(),
    )
    flow = _catalog_flow("Group")
    flow["nodes"][0]["data"]["node"]["flow"] = {"data": _catalog_flow("PromptComponent")}

    with pytest.raises(CatalogPolicyValidationError, match="Prompt Template"):
        validate_catalog_policy_for_flow(
            flow,
            snapshot=CatalogPolicySnapshot(blocked_component_keys={"Prompt"}),
        )


def test_catalog_policy_component_code_blocks_known_alias_before_execution(monkeypatch):
    code = "# trusted Agent component"
    code_hash = hashlib.sha256(code.encode()).hexdigest()[:12]
    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_hash_lookups_for_validation",
        lambda: {"Agent": {code_hash}, "AgentComponent": {code_hash}},
    )

    with pytest.raises(CatalogPolicyValidationError, match="AgentComponent"):
        validate_catalog_policy_for_component_code(
            code,
            snapshot=CatalogPolicySnapshot(blocked_component_keys={"AgentComponent"}),
        )


def test_catalog_policy_component_code_empty_snapshot_does_not_require_template_identities(monkeypatch):
    def fail_if_called():
        msg = "empty policy should not load component identities"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_hash_lookups_for_validation",
        fail_if_called,
    )

    validate_catalog_policy_for_component_code("arbitrary code", snapshot=CatalogPolicySnapshot())


def test_catalog_policy_component_code_fails_closed_while_identities_initialize(monkeypatch):
    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_hash_lookups_for_validation",
        lambda: None,
    )

    with pytest.raises(CatalogPolicyIdentityUnavailableError, match="identities are still initializing"):
        validate_catalog_policy_for_component_code(
            "arbitrary code",
            snapshot=CatalogPolicySnapshot(blocked_component_keys={"Agent"}),
        )


def test_catalog_policy_component_code_does_not_build_from_transient_component_cache(monkeypatch):
    from lfx.interface.components import component_cache

    monkeypatch.setattr(component_cache, "all_types_dict", {})
    monkeypatch.setattr(component_cache, "all_types_ready", False)
    monkeypatch.setattr(component_cache, "type_to_current_hash", None)
    monkeypatch.setattr(component_cache, "all_known_hashes", None)
    monkeypatch.setattr(component_cache, "code_by_hash", None)

    with pytest.raises(CatalogPolicyIdentityUnavailableError, match="identities are still initializing"):
        validate_catalog_policy_for_component_code(
            "arbitrary code",
            snapshot=CatalogPolicySnapshot(blocked_component_keys={"Agent"}),
        )

    assert component_cache.type_to_current_hash is None
    assert component_cache.all_known_hashes is None
    assert component_cache.code_by_hash is None


def test_catalog_policy_component_type_is_exact_and_empty_snapshot_allows(monkeypatch):
    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_identity_index_for_validation",
        lambda: _catalog_identity_index(),
    )
    snapshot = CatalogPolicySnapshot(blocked_component_keys={"Agent"})

    validate_catalog_policy_for_component_type("agent", snapshot=snapshot)
    validate_catalog_policy_for_component_type("Agent", snapshot=CatalogPolicySnapshot())
    with pytest.raises(CatalogPolicyValidationError, match="Agent"):
        validate_catalog_policy_for_component_type("Agent", snapshot=snapshot)


@pytest.mark.parametrize(
    ("blocked_identity", "runtime_identity", "canonical"),
    [
        ("Prompt Template", "PromptComponent", "Prompt Template"),
        ("PromptComponent", "Prompt Template", "Prompt Template"),
        (ASTRADB_KEY, "AstraDB", ASTRADB_KEY),
        ("AstraDB", "AstraDBVectorStoreComponent", ASTRADB_KEY),
        ("Chat Input", "ChatInput", "ChatInput"),
    ],
)
def test_catalog_policy_materialized_component_resolves_canonical_identity(
    monkeypatch,
    blocked_identity,
    runtime_identity,
    canonical,
):
    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_identity_index_for_validation",
        lambda: _catalog_identity_index(),
    )

    with pytest.raises(CatalogPolicyValidationError, match=canonical):
        validate_catalog_policy_for_component_type(
            runtime_identity,
            snapshot=CatalogPolicySnapshot(blocked_component_keys={blocked_identity}),
        )


def test_validate_flow_for_current_settings_captures_one_catalog_snapshot(monkeypatch):
    class ChangingCatalogPolicyService:
        def __init__(self):
            self.snapshot_calls = 0

        @property
        def snapshot(self):
            self.snapshot_calls += 1
            if self.snapshot_calls == 1:
                return CatalogPolicySnapshot(blocked_component_keys=frozenset({"Agent"}))
            return CatalogPolicySnapshot()

    service = ChangingCatalogPolicyService()
    settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=True,
            block_code_interpreter_components=False,
        )
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr("lfx.services.deps.get_catalog_policy_service", lambda: service)

    with pytest.raises(CatalogPolicyValidationError, match="Agent"):
        validate_flow_for_current_settings(_catalog_flow("Agent"))

    assert service.snapshot_calls == 1


# --- public-flow component sanitization (H1-3754930 follow-up) --------------------


def _server_components() -> dict:
    """Fake all_types_dict with one known component ('ChatInput' / 'Chat Input') and trusted code."""
    return {
        "inputs": {
            "ChatInput": {
                "display_name": "Chat Input",
                "template": {"code": {"value": "# trusted ChatInput code"}},
            }
        }
    }


def _public_settings(*, allow_custom=True, allow_public_custom=False) -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=allow_custom,
            allow_public_custom_components=allow_public_custom,
        )
    )


def _node(node_id: str, component_type: str, code: str | None, *, display_name: str | None = None) -> dict:
    template = {"code": {"value": code}} if code is not None else {}
    node_block: dict = {"template": template}
    if display_name is not None:
        node_block["display_name"] = display_name
    return {"id": node_id, "data": {"id": node_id, "type": component_type, "node": node_block}}


def _public_lookup_snapshot(type_to_code: dict[str, str]) -> tuple[dict[str, str], dict[str, set[str]]]:
    return type_to_code, {
        component_type: {hashlib.sha256(code.encode()).hexdigest()[:12]}
        for component_type, code in type_to_code.items()
    }


def test_collect_component_code_lookups_maps_type_and_aliases():
    """Each component's canonical name and display-name alias map to its trusted code."""
    lookups = collect_component_code_lookups(_server_components())
    assert lookups["ChatInput"] == "# trusted ChatInput code"
    assert lookups["Chat Input"] == "# trusted ChatInput code"


def test_substitute_trusted_node_code_replaces_known_and_blocks_unknown():
    from lfx.utils import flow_validation as fv

    nodes = [
        _node("a", "ChatInput", "malicious()"),
        _node("b", "EvilCustom", "import os", display_name="Evil"),
    ]
    blocked = fv._substitute_trusted_node_code(nodes, {"ChatInput": "# trusted"})

    assert nodes[0]["data"]["node"]["template"]["code"]["value"] == "# trusted"  # known → replaced
    assert blocked == ["Evil (b)"]  # unknown → blocked
    assert nodes[1]["data"]["node"]["template"]["code"]["value"] == "import os"  # unknown not substituted


def test_substitute_trusted_node_code_blocks_non_string_type():
    """A malformed, non-string ``type`` (e.g. a dict) must be blocked, not raise TypeError."""
    from lfx.utils import flow_validation as fv

    # An unhashable ``type`` would raise on ``in type_to_code`` without the isinstance guard.
    node = _node("a", "ChatInput", "import os", display_name="Sneaky")
    node["data"]["type"] = {"not": "a string"}
    blocked = fv._substitute_trusted_node_code([node], {"ChatInput": "# trusted"})

    assert blocked == ["Sneaky (a)"]  # treated as unknown → blocked
    assert node["data"]["node"]["template"]["code"]["value"] == "import os"  # not substituted


def test_substitute_trusted_node_code_recurses_into_inlined_subflows():
    from lfx.utils import flow_validation as fv

    nodes = [
        {
            "id": "group",
            "data": {
                "id": "group",
                "type": "GroupNode",
                "node": {"flow": {"data": {"nodes": [_node("inner", "EvilCustom", "x", display_name="Evil")]}}},
            },
        }
    ]
    assert fv._substitute_trusted_node_code(nodes, {"ChatInput": "# trusted"}) == ["Evil (inner)"]


def test_substitute_trusted_node_code_leaves_codeless_nodes_untouched():
    from lfx.utils import flow_validation as fv

    # An unknown type with no code field carries no execution vector and must not be blocked.
    assert fv._substitute_trusted_node_code([_node("note", "NoteNode", None)], {"ChatInput": "# trusted"}) == []


def test_get_invalid_components_blocks_codebearing_node_with_empty_type():
    """A code-bearing node with an empty/missing type must be blocked, not skipped.

    Regression for GHSA-mfp9-86w4-493f: _get_invalid_components used to
    `continue` on a falsy ``type``, so a crafted node bypassed the
    allow_custom_components gate while its stored code still executed at build.
    """
    from lfx.utils import flow_validation as fv

    type_to_hash = {"ChatInput": {"deadbeef"}}

    # Code present, type empty -> can never match a trusted hash -> blocked.
    sneaky = _node("x", "", "import os; os.system('id')", display_name="Sneaky")
    blocked, outdated = fv._get_invalid_components([sneaky], type_to_hash)
    assert "Sneaky (x)" in blocked
    assert outdated == []

    # Control: an empty-type node with no code carries no execution vector.
    codeless = _node("n", "", None)
    blocked2, outdated2 = fv._get_invalid_components([codeless], type_to_hash)
    assert blocked2 == []
    assert outdated2 == []


@pytest.mark.asyncio
async def test_prepare_public_flow_build_substitutes_trusted_code(monkeypatch):
    """Default mode replaces stored built-in code with the server's trusted copy (no 'outdated' break)."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(
        fv,
        "_ensure_public_component_lookup_snapshot",
        AsyncMock(return_value=_public_lookup_snapshot({"ChatInput": "# trusted"})),
    )

    flow = {"nodes": [_node("a", "ChatInput", "stored old code")], "edges": []}
    sanitized = await fv.prepare_public_flow_build(flow)

    assert sanitized is not None
    assert sanitized["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "# trusted"
    # the caller's original flow data is not mutated
    assert flow["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "stored old code"


@pytest.mark.asyncio
async def test_prepare_public_flow_build_rechecks_code_execution_after_substitution(monkeypatch):
    """A stale namespaced alias cannot become executable server code after the public precheck."""
    from lfx.utils import flow_validation as fv

    extension_type = "ext:langflow:PythonREPLComponent@official"
    trusted_repl_code = "class PythonREPLComponent(Component):\n    pass\n"
    trusted_repl_hash = fv._compute_code_hash(trusted_repl_code)
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(
        fv,
        "_ensure_public_component_lookup_snapshot",
        AsyncMock(
            return_value=(
                {extension_type: trusted_repl_code},
                {
                    extension_type: {trusted_repl_hash},
                    "PythonREPLComponent": {trusted_repl_hash},
                },
            )
        ),
    )
    monkeypatch.setattr(
        fv,
        "get_component_hash_lookups_for_validation",
        lambda: {"PythonREPLComponent": {trusted_repl_hash}},
    )

    flow = {
        "nodes": [_node("repl", extension_type, "# stale harmless bytes", display_name="Harmless Tool")],
        "edges": [],
    }
    # The stale bytes and namespaced type evade the route-level defense-in-depth precheck.
    fv.validate_public_flow_no_code_execution(flow)

    # Trusted substitution resolves that alias to the server's Python REPL source. The helper
    # must re-check the graph it returns so every public caller fails closed.
    with pytest.raises(PublicFlowValidationError, match="code-execution"):
        await fv.prepare_public_flow_build(flow)


def test_public_component_lookup_snapshot_linearizes_reload(monkeypatch):
    """A hot reload cannot pair trusted source from one generation with hashes from another."""
    from lfx.interface.components import component_cache
    from lfx.utils import flow_validation as fv

    old_code = {"ChatInput": "# old trusted"}
    old_hashes = {"ChatInput": {"oldhash00001"}}
    new_code = {"ChatInput": "# new trusted"}
    new_hashes = {"ChatInput": {"newhash00002"}}
    monkeypatch.setattr(component_cache, "all_types_dict", {"inputs": {}})
    monkeypatch.setattr(component_cache, "all_types_ready", True)
    monkeypatch.setattr(component_cache, "type_to_code", old_code)
    monkeypatch.setattr(component_cache, "type_to_current_hash", old_hashes)

    code_read_started = Event()
    release_code_read = Event()
    reload_finished = Event()
    results: list[tuple[dict[str, str], object]] = []

    def read_code():
        code_read_started.set()
        assert release_code_read.wait(timeout=2)
        return component_cache.type_to_code

    monkeypatch.setattr(fv, "get_component_code_lookups_for_validation", read_code)
    monkeypatch.setattr(
        fv,
        "get_component_hash_lookups_for_validation",
        lambda: component_cache.type_to_current_hash,
    )

    def read_snapshot() -> None:
        results.append(asyncio.run(fv._ensure_public_component_lookup_snapshot(SimpleNamespace())))

    def reload_registry() -> None:
        with component_cache.state_lock:
            component_cache.type_to_code = new_code
            component_cache.type_to_current_hash = new_hashes
        reload_finished.set()

    reader = Thread(target=read_snapshot)
    reader.start()
    assert code_read_started.wait(timeout=2)
    reloader = Thread(target=reload_registry)
    reloader.start()
    assert not reload_finished.wait(timeout=0.1), "reload interleaved with a public lookup snapshot"
    release_code_read.set()
    reader.join(timeout=2)
    reloader.join(timeout=2)

    assert not reader.is_alive()
    assert not reloader.is_alive()
    assert results == [(old_code, old_hashes)]
    assert component_cache.type_to_code == new_code
    assert component_cache.type_to_current_hash == new_hashes


@pytest.mark.asyncio
async def test_public_graph_rechecks_code_after_registry_reload(monkeypatch):
    """Graph construction checks the final source if the registry changes after preparation."""
    from lfx.graph.graph.base import Graph
    from lfx.interface.components import component_cache
    from lfx.services.authorization import PUBLIC_ANONYMOUS_ACTOR_ID
    from lfx.utils import flow_validation as fv

    extension_type = "ext:langflow:ReloadableComponent@official"
    safe_code = "class SafeComponent(Component):\n    pass\n"
    blocked_code = "class PythonREPLComponent(Component):\n    pass\n"
    blocked_hash = fv._compute_code_hash(blocked_code)
    settings_service = _public_settings(allow_custom=False)
    monkeypatch.setattr(settings_service.settings, "substitute_outdated_component_code", True, raising=False)
    monkeypatch.setattr(settings_service.settings, "block_code_interpreter_components", False, raising=False)
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr(
        "lfx.services.deps.get_catalog_policy_service",
        lambda: SimpleNamespace(snapshot=CatalogPolicySnapshot()),
    )
    monkeypatch.setattr(
        fv,
        "_ensure_public_component_lookup_snapshot",
        AsyncMock(return_value=_public_lookup_snapshot({extension_type: safe_code})),
    )

    stored = {"nodes": [_node("reloadable", extension_type, "# stale stored bytes")], "edges": []}
    prepared = await fv.prepare_public_flow_build(stored)
    assert prepared is not None
    assert prepared["nodes"][0]["data"]["node"]["template"]["code"]["value"] == safe_code

    # Publish a later generation in which the same declared identity resolves to a blocked
    # component. Graph.from_payload performs the runtime substitution, so its public gate must
    # validate this generation's exact bytes instead of relying on the earlier safe preparation.
    monkeypatch.setattr(component_cache, "all_types_dict", {"test": {}})
    monkeypatch.setattr(component_cache, "all_types_ready", True)
    monkeypatch.setattr(component_cache, "type_to_code", {extension_type: blocked_code})
    monkeypatch.setattr(
        component_cache,
        "type_to_current_hash",
        {
            extension_type: {blocked_hash},
            "PythonREPLComponent": {blocked_hash},
        },
    )
    # This regression targets the validation boundary, so do not require the policy-only test
    # node to carry the complete frontend template shape needed to construct a real Vertex.
    monkeypatch.setattr(Graph, "add_nodes_and_edges", lambda _self, _vertices, _edges: None)

    owner_graph = Graph.from_payload(
        copy.deepcopy(prepared),
        user_id="authenticated-owner",
        instantiate_components=False,
        emit_extension_events=False,
    )
    assert owner_graph is not None

    with pytest.raises(PublicFlowValidationError, match="code-execution"):
        Graph.from_payload(
            copy.deepcopy(prepared),
            user_id=str(PUBLIC_ANONYMOUS_ACTOR_ID),
            instantiate_components=False,
            emit_extension_events=False,
        )

    from lfx.graph.checkpoint.schema import GraphCheckpoint

    checkpoint = GraphCheckpoint(
        run_id="public-run",
        user_id=str(PUBLIC_ANONYMOUS_ACTOR_ID),
        flow_payload=copy.deepcopy(prepared),
    )
    with pytest.raises(PublicFlowValidationError, match="code-execution"):
        Graph.resume_from_checkpoint(checkpoint)


@pytest.mark.asyncio
async def test_prepare_public_flow_build_blocks_unknown_custom_component(monkeypatch):
    """A public flow with an unrecognized custom component is rejected."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(
        fv,
        "_ensure_public_component_lookup_snapshot",
        AsyncMock(return_value=_public_lookup_snapshot({"ChatInput": "# trusted"})),
    )

    flow = {"nodes": [_node("x", "MyCustom", "import os; os.system('x')", display_name="My Custom")], "edges": []}
    with pytest.raises(CustomComponentValidationError) as exc_info:
        await fv.prepare_public_flow_build(flow)
    assert "My Custom (x)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_prepare_public_flow_build_neutralizes_relabelled_code(monkeypatch):
    """Arbitrary code relabelled as a known type is overwritten with the server's trusted code."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(
        fv,
        "_ensure_public_component_lookup_snapshot",
        AsyncMock(return_value=_public_lookup_snapshot({"ChatInput": "# trusted ChatInput"})),
    )

    flow = {"nodes": [_node("a", "ChatInput", "import os; os.system('pwned')")], "edges": []}
    sanitized = await fv.prepare_public_flow_build(flow)
    assert sanitized["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "# trusted ChatInput"


@pytest.mark.asyncio
async def test_prepare_public_flow_build_opt_in_honors_global(monkeypatch):
    """allow_public_custom_components=True returns None (DB-loaded build) and runs standard validation."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: _public_settings(allow_custom=True, allow_public_custom=True),
    )
    seen = {}
    monkeypatch.setattr(fv, "validate_flow_for_current_settings", lambda target: seen.setdefault("target", target))

    flow = {"nodes": [_node("x", "MyCustom", "import os")], "edges": []}
    assert await fv.prepare_public_flow_build(flow) is None
    assert seen.get("target") == flow


@pytest.mark.asyncio
async def test_prepare_public_flow_build_opt_in_still_blocks_code_execution(monkeypatch):
    """Public custom-code opt-in never opts into unauthenticated Python execution."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: _public_settings(allow_custom=True, allow_public_custom=True),
    )
    monkeypatch.setattr(fv, "validate_flow_for_current_settings", lambda _target: None)

    with pytest.raises(PublicFlowValidationError, match="code-execution"):
        await fv.prepare_public_flow_build(_flow_with_component("PythonREPLComponent"))


@pytest.mark.asyncio
async def test_prepare_public_flow_build_restricted_opt_in_checks_effective_substitution(monkeypatch):
    """Global restricted mode returns and checks substituted bytes even with public opt-in."""
    from lfx.utils import flow_validation as fv

    extension_type = "ext:langflow:PythonREPLComponent@official"
    trusted_repl_code = "class PythonREPLComponent(Component):\n    pass\n"
    trusted_repl_hash = fv._compute_code_hash(trusted_repl_code)
    settings_service = _public_settings(allow_custom=False, allow_public_custom=True)
    monkeypatch.setattr(settings_service.settings, "substitute_outdated_component_code", True, raising=False)
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    monkeypatch.setattr(fv, "validate_flow_for_current_settings", lambda _target: None)
    monkeypatch.setattr(
        fv,
        "_ensure_public_component_lookup_snapshot",
        AsyncMock(
            return_value=(
                {extension_type: trusted_repl_code},
                {
                    extension_type: {trusted_repl_hash},
                    "PythonREPLComponent": {trusted_repl_hash},
                },
            )
        ),
    )
    stale = {"nodes": [_node("repl", extension_type, "# harmless stale bytes")], "edges": []}

    with pytest.raises(PublicFlowValidationError, match="code-execution"):
        await fv.prepare_public_flow_build(stale)


@pytest.mark.asyncio
async def test_prepare_public_flow_build_requires_settings_service(monkeypatch):
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
    with pytest.raises(RuntimeError, match="Settings service must be initialized"):
        await prepare_public_flow_build({"nodes": []})


@pytest.mark.asyncio
async def test_prepare_public_flow_build_fails_closed_without_templates(monkeypatch):
    """If the component templates can't be loaded, unverified code must not pass."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(fv, "_ensure_public_component_lookup_snapshot", AsyncMock(return_value=({}, {})))

    flow = {"nodes": [_node("a", "ChatInput", "x")], "edges": []}
    with pytest.raises(CustomComponentValidationError):
        await fv.prepare_public_flow_build(flow)


@pytest.mark.asyncio
@pytest.mark.parametrize("empty", [None, {}, {"nodes": []}, {"nodes": "not-a-list"}])
async def test_prepare_public_flow_build_noop_on_empty(monkeypatch, empty):
    """Missing/empty/malformed node lists fall back to the default build (return None), not an error."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(
        fv,
        "_ensure_public_component_lookup_snapshot",
        AsyncMock(return_value=_public_lookup_snapshot({"ChatInput": "# t"})),
    )
    assert await fv.prepare_public_flow_build(empty) is None


# --- validate_public_flow_no_code_execution (report H1-3754930) -------------------


REPORTED_CODE_EXECUTION_AGENT_TYPES = (
    "CSVAgent",
    "CodeActAgentSmolagents",
    "Cuga",
    "OpenDsStarAgent",
)


def _flow_with_component(component_type: str) -> dict:
    """Build minimal raw graph data containing a single node of ``component_type``."""
    node_id = f"{component_type}-1"
    return {
        "nodes": [
            {
                "id": node_id,
                "data": {
                    "id": node_id,
                    "type": component_type,
                    "node": {"display_name": component_type, "template": {}},
                },
            }
        ],
        "edges": [],
    }


@pytest.mark.parametrize("component_type", REPORTED_CODE_EXECUTION_AGENT_TYPES)
def test_public_flow_blocks_reported_code_execution_agents(component_type):
    """Regression for H1-3813558: shipped code agents must not build anonymously."""
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(_flow_with_component(component_type))
    assert component_type in str(exc_info.value)


def test_public_flow_blocks_structured_data_analysis_starter_template():
    """The bundled data-analysis starter contains OpenDsStarAgent and must be rejected publicly."""
    repo_root = Path(__file__).resolve().parents[5]
    starter_path = (
        repo_root
        / "src/bundles/lfx-bundles/src/lfx_bundles/codeagents/starter_projects/Structured Data Analysis Agent.json"
    )
    starter_flow = json.loads(starter_path.read_text())

    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(starter_flow)
    assert "OpenDsStarAgent" in str(exc_info.value)


@pytest.mark.parametrize("component_type", sorted(CODE_EXECUTION_COMPONENT_TYPES))
def test_public_flow_blocks_code_execution_components(component_type):
    """Every code-execution component must be rejected on the unauthenticated public path."""
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(_flow_with_component(component_type))
    assert component_type in str(exc_info.value)


def test_public_flow_allows_safe_components():
    """A flow without code-execution components must build on the public path."""
    safe = {
        "nodes": [
            {"id": "ChatInput-1", "data": {"id": "ChatInput-1", "type": "ChatInput", "node": {"template": {}}}},
        ],
        "edges": [],
    }
    validate_public_flow_no_code_execution(safe)  # must not raise


def test_public_flow_blocks_nested_code_execution_component():
    """A code-execution component hidden inside a sub-flow must still be caught."""
    nested = {
        "nodes": [
            {
                "id": "group-1",
                "data": {
                    "id": "group-1",
                    "type": "GroupNode",
                    "node": {"flow": {"data": _flow_with_component("PythonREPLComponent")}},
                },
            }
        ],
        "edges": [],
    }
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(nested)


def test_public_flow_unwraps_data_envelope():
    """The {"data": {...}} envelope must be unwrapped before validation."""
    wrapped = {"data": _flow_with_component("PythonREPLTool")}
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(wrapped)


@pytest.mark.parametrize("empty", [None, {}, {"nodes": []}, {"nodes": "not-a-list"}])
def test_public_flow_noop_on_empty(empty):
    """Missing/empty/malformed node lists are a no-op, not an error."""
    validate_public_flow_no_code_execution(empty)  # must not raise


def test_public_flow_validation_error_is_custom_component_error():
    """Subclassing keeps the existing public-build handler (CustomComponentValidationError -> 400)."""
    assert issubclass(PublicFlowValidationError, CustomComponentValidationError)


# --- transitive flow execution (report H1-3754930, transitive case) ---------------


@pytest.mark.parametrize("component_type", sorted(FLOW_REFERENCE_COMPONENT_TYPES))
def test_public_flow_blocks_flow_invoking_components(component_type):
    """Flow-invoking components (Run Flow / Sub Flow / Flow as Tool) must be rejected.

    They load and execute another saved owner flow by id/name at runtime; that
    referenced flow is never re-validated, so a public wrapper flow could use one
    to reach a private flow containing a code-execution component.
    """
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(_flow_with_component(component_type))
    assert component_type in str(exc_info.value)
    assert "execute other flows" in str(exc_info.value)


def test_public_flow_blocks_wrapper_with_runflow_and_safe_nodes():
    """The real attack shape — a wrapper of otherwise-safe nodes plus a Run Flow — is blocked."""
    wrapper = {
        "nodes": [
            {"id": "ChatInput-1", "data": {"id": "ChatInput-1", "type": "ChatInput", "node": {"template": {}}}},
            {
                "id": "RunFlow-1",
                "data": {"id": "RunFlow-1", "type": "RunFlow", "node": {"display_name": "Run Flow", "template": {}}},
            },
            {"id": "ChatOutput-1", "data": {"id": "ChatOutput-1", "type": "ChatOutput", "node": {"template": {}}}},
        ],
        "edges": [],
    }
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(wrapper)
    assert "RunFlow-1" in str(exc_info.value)


def test_public_flow_blocks_nested_flow_invoking_component():
    """A flow-invoking component hidden inside an inlined sub-flow must still be caught."""
    nested = {
        "nodes": [
            {
                "id": "group-1",
                "data": {
                    "id": "group-1",
                    "type": "GroupNode",
                    "node": {"flow": {"data": _flow_with_component("SubFlow")}},
                },
            }
        ],
        "edges": [],
    }
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(nested)


def test_code_execution_and_flow_reference_sets_are_disjoint():
    """The two blocklists describe different failure modes and must not overlap."""
    assert CODE_EXECUTION_COMPONENT_TYPES.isdisjoint(FLOW_REFERENCE_COMPONENT_TYPES)


# --- aliasing bypass: match by code-hash, not just declared type ------------------


def _flow_with_typed_code(component_type: str, code: str) -> dict:
    """Build raw graph data for a single node carrying ``code`` under ``component_type``."""
    return {
        "nodes": [
            {
                "id": "evasive-1",
                "data": {
                    "id": "evasive-1",
                    "type": component_type,
                    "node": {"display_name": component_type, "template": {"code": {"value": code}}},
                },
            }
        ],
        "edges": [],
    }


def test_public_flow_blocks_flow_invoking_component_relabelled_via_code_hash(monkeypatch):
    """A flow-invoking node that relabels its ``type`` to dodge the type block is still caught.

    In the hardened ``allow_custom_components=false`` mode the build runs the node's
    stored ``code`` regardless of its declared ``type``, so the code-hash of a
    blocked component is the authoritative signal.
    """
    from lfx.utils import flow_validation as fv

    run_flow_code = "class RunFlowComponent(Component):\n    name = 'RunFlow'\n"
    code_hash = fv._compute_code_hash(run_flow_code)
    # Pretend the server's known RunFlow template hashes to this code.
    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: {"RunFlow": {code_hash}})

    # Declared type is innocuous and in NEITHER blocklist, but the code is RunFlow's.
    evasive = _flow_with_typed_code("Totally Innocent", run_flow_code)
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(evasive)
    assert "execute other flows" in str(exc_info.value)


def test_public_flow_blocks_code_execution_component_relabelled_via_code_hash(monkeypatch):
    """The same aliasing defense applies to code-execution components."""
    from lfx.utils import flow_validation as fv

    repl_code = "class PythonREPLComponent(Component):\n    pass\n"
    code_hash = fv._compute_code_hash(repl_code)
    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: {"PythonREPLComponent": {code_hash}})

    evasive = _flow_with_typed_code("Harmless Label", repl_code)
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(evasive)
    assert "code-execution" in str(exc_info.value)


def test_public_flow_code_hash_allows_unrelated_code(monkeypatch):
    """A node whose code does not match any blocked template hash must still build."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: {"RunFlow": {"deadbeefcafe"}})
    safe = _flow_with_typed_code("ChatInput", "class ChatInput(Component):\n    pass\n")
    validate_public_flow_no_code_execution(safe)  # must not raise


def test_public_flow_type_block_works_without_hash_lookups(monkeypatch):
    """When the hash lookup is unavailable, canonical type-name matching still blocks."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr(fv, "get_component_hash_lookups_for_validation", lambda: None)
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(_flow_with_component("RunFlow"))


# --- MCP stdio server configuration on the public path ---------------------------
#
# The stdio command lives in the ``mcp_server`` field VALUE, not in ``code``. Trusted-code
# substitution only rewrites ``code``, and MCPTools is not a code-execution component, so
# without an explicit check an anonymous visitor triggers an OS subprocess spawn.


def _mcp_node(config: object, *, field_name: str = "mcp_server", component_type: str = "MCPTools") -> dict:
    """Build a node whose template carries an MCP server selection value."""
    node_id = f"{component_type}-abc12"
    return {
        "id": node_id,
        "data": {
            "id": node_id,
            "type": component_type,
            "node": {
                "display_name": "MCP Tools",
                "template": {
                    "code": {"value": "# stored MCPTools code"},
                    field_name: {"type": "mcp", "name": field_name, "value": config},
                },
            },
        },
    }


def _mcp_flow(config: object, **kwargs) -> dict:
    return {"nodes": [_mcp_node(config, **kwargs)], "edges": []}


STDIO_CONFIG = {"command": "python", "args": ["-m", "some_module"], "env": {}}


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"name": "srv", "config": dict(STDIO_CONFIG)}, id="command-only"),
        pytest.param({"name": "srv", "config": {"mode": "Stdio", "command": "uvx", "args": ["pkg"]}}, id="mode-stdio"),
        pytest.param({"name": "srv", "config": {"mode": "stdio", "command": "npx"}}, id="mode-lowercase"),
        pytest.param(dict(STDIO_CONFIG), id="bare-config"),
        pytest.param({"mcpServers": {"srv": dict(STDIO_CONFIG)}}, id="mcpservers-map"),
    ],
)
def test_public_flow_blocks_mcp_stdio_server_config(config):
    """A public flow that would spawn an OS subprocess through MCP stdio must be refused."""
    with pytest.raises(PublicFlowValidationError) as exc_info:
        validate_public_flow_no_code_execution(_mcp_flow(config))
    assert "MCP" in str(exc_info.value)


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"name": "srv", "config": {"url": "https://mcp.example.com/mcp"}}, id="http"),
        pytest.param(
            {"name": "srv", "config": {"mode": "SSE", "url": "https://mcp.example.com/sse"}},
            id="sse",
        ),
        pytest.param({"name": "srv", "config": {}}, id="empty-config"),
        pytest.param({"name": "srv"}, id="name-only"),
        pytest.param("srv", id="plain-name"),
        pytest.param(None, id="unset"),
    ],
)
def test_public_flow_allows_non_stdio_mcp_server_config(config):
    """Remote MCP transports carry no subprocess spawn and must keep working publicly."""
    validate_public_flow_no_code_execution(_mcp_flow(config))  # must not raise


def test_public_flow_blocks_mcp_stdio_under_relabelled_field_name():
    """The check follows the config shape, not just the canonical ``mcp_server`` field key."""
    flow = _mcp_flow({"name": "srv", "config": dict(STDIO_CONFIG)}, field_name="renamed_field")
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(flow)


def test_public_flow_blocks_nested_mcp_stdio_server_config():
    """An MCP stdio node hidden inside an inlined sub-flow must still be caught."""
    nested = {
        "nodes": [
            {
                "id": "group-1",
                "data": {
                    "id": "group-1",
                    "type": "GroupNode",
                    "node": {"flow": {"data": _mcp_flow({"name": "srv", "config": dict(STDIO_CONFIG)})}},
                },
            }
        ],
        "edges": [],
    }
    with pytest.raises(PublicFlowValidationError):
        validate_public_flow_no_code_execution(nested)


def test_public_flow_blocks_legacy_stdio_component_type():
    """The deprecated MCPStdio component is stdio-only, so its type is refused outright."""
    from lfx.utils.flow_validation import MCP_STDIO_COMPONENT_TYPES

    for component_type in sorted(MCP_STDIO_COMPONENT_TYPES):
        with pytest.raises(PublicFlowValidationError):
            validate_public_flow_no_code_execution(_flow_with_component(component_type))


def test_public_flow_ignores_ordinary_dict_field_with_command_key():
    """A plain dict input that happens to carry a ``command`` key is not an MCP config."""
    flow = {
        "nodes": [
            {
                "id": "APIRequest-1",
                "data": {
                    "id": "APIRequest-1",
                    "type": "APIRequest",
                    "node": {
                        "display_name": "API Request",
                        "template": {"body": {"type": "dict", "name": "body", "value": {"command": "restart"}}},
                    },
                },
            }
        ],
        "edges": [],
    }
    validate_public_flow_no_code_execution(flow)  # must not raise


@pytest.mark.asyncio
async def test_prepare_public_flow_build_blocks_mcp_stdio_after_trusted_substitution(monkeypatch):
    """Trusted-code substitution rewrites ``code`` only; the stdio config must still be refused.

    This is the end-to-end default-mode shape: the server's own MCPTools source is swapped in
    (so the component that spawns the subprocess is trusted code), while the attacker-authored
    ``mcp_server`` value survives sanitization untouched.
    """
    from lfx.utils import flow_validation as fv

    trusted_mcp_code = "class MCPToolsComponent(Component):\n    name = 'MCPTools'\n"
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _public_settings())
    monkeypatch.setattr(
        fv,
        "_ensure_public_component_lookup_snapshot",
        AsyncMock(return_value=_public_lookup_snapshot({"MCPTools": trusted_mcp_code})),
    )

    flow = _mcp_flow({"name": "srv", "config": dict(STDIO_CONFIG)})
    with pytest.raises(PublicFlowValidationError) as exc_info:
        await fv.prepare_public_flow_build(flow)
    assert "MCP" in str(exc_info.value)


@pytest.mark.asyncio
async def test_prepare_public_flow_build_blocks_mcp_stdio_under_custom_component_optin(monkeypatch):
    """The public custom-component opt-in must not reopen the MCP stdio spawn path."""
    from lfx.utils import flow_validation as fv

    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: _public_settings(allow_custom=True, allow_public_custom=True),
    )
    monkeypatch.setattr(fv, "validate_flow_for_current_settings", lambda _target: None)

    flow = _mcp_flow({"name": "srv", "config": dict(STDIO_CONFIG)})
    with pytest.raises(PublicFlowValidationError):
        await fv.prepare_public_flow_build(flow)


# --- block_code_interpreter_components (built-in code-exec component gate) ----------


def _code_interpreter_raw_graph(
    component_type: str = "PythonREPLComponent",
    display_name: str = "Python Interpreter",
) -> dict:
    """A graph whose single node is a built-in code-execution component."""
    return {
        "nodes": [
            {
                "id": "py-1",
                "data": {
                    "id": "py-1",
                    "type": component_type,
                    "node": {
                        "display_name": display_name,
                        "template": {"code": {"value": "print('builtin component')"}},
                    },
                },
            }
        ],
        "edges": [],
    }


@pytest.mark.parametrize(
    ("component_type", "display_name"),
    [
        ("PythonREPLComponent", "Python Interpreter"),
        ("PythonCodeStructuredTool", "Python Code Structured"),
        ("BenignComponent", "Python Code Structured"),  # display_name alias must also be caught
        ("PythonREPLToolComponent", "Python REPL"),
        ("PythonFunction", "Python Function"),  # prototypes/python_function.py - exec of user function_code
        ("BenignComponent", "Python Function"),  # display_name alias
        ("LambdaFilterComponent", "Smart Transform"),
        ("BenignComponent", "Smart Transform"),  # alias must also be caught
        # Code-agent components run LLM-generated Python in-process (smolagents local
        # executor / DS-Star bare exec); they must be covered by the same block list.
        ("CodeActAgentSmolagents", "CodeAct Agent (Smolagents)"),
        ("BenignComponent", "CodeAct Agent (Smolagents)"),  # display-name alias
        ("OpenDsStarAgent", "OpenDsStar Agent"),
        ("BenignComponent", "OpenDsStar Agent"),  # display-name alias
    ],
)
def test_block_code_interpreter_components_blocks_flow(monkeypatch, component_type, display_name):
    """When the flag is on, flows with code-execution components are blocked."""
    settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=True,
            block_code_interpreter_components=True,
        ),
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    graph = SimpleNamespace(raw_graph_data=_code_interpreter_raw_graph(component_type, display_name))

    with pytest.raises(CustomComponentValidationError, match="code-execution components are not allowed"):
        validate_flow_for_current_settings(graph)


def test_block_code_interpreter_components_disabled_allows_flow(monkeypatch):
    """With the flag off (default), code-execution components are permitted."""
    settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=True,
            block_code_interpreter_components=False,
        ),
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    graph = SimpleNamespace(raw_graph_data=_code_interpreter_raw_graph())

    # Should not raise.
    validate_flow_for_current_settings(graph)


def test_block_code_interpreter_components_detects_nested_flow(monkeypatch):
    """A code-execution component hidden inside a nested/sub-flow must still be caught."""
    settings_service = SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=True,
            block_code_interpreter_components=True,
        ),
    )
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)
    nested = _code_interpreter_raw_graph()
    outer = {
        "nodes": [
            {
                "id": "wrapper",
                "data": {
                    "id": "wrapper",
                    "type": "SomeBenignComponent",
                    "node": {"flow": {"data": nested}},
                },
            }
        ],
        "edges": [],
    }
    graph = SimpleNamespace(raw_graph_data=outer)

    with pytest.raises(CustomComponentValidationError, match="code-execution components are not allowed"):
        validate_flow_for_current_settings(graph)


# --- Frontend mirror parity -------------------------------------------------
# The parameters panel must not offer an "API" toggle on a field that
# apply_tweaks would refuse, so the refusal rules are mirrored in
# src/frontend/src/modals/apiModal/utils/api-exposure-rules.ts. The mirror is
# UX only — the backend stays the enforcement point — but a mirror that drifts
# silently brings the bug back, so parity is asserted here.

_FRONTEND_MIRROR = Path(__file__).parents[4] / "frontend/src/modals/apiModal/utils/api-exposure-rules.ts"


def _strip_line_comments(source: str) -> str:
    return "\n".join(line.split("//")[0] for line in source.splitlines())


def _parse_ts_string_set(source: str, const_name: str) -> set[str]:
    """Extract the string literals of `export const <const_name> ... new Set([...])`."""
    marker = f"export const {const_name}"
    start = source.index(marker)
    open_bracket = source.index("[", start)
    close_bracket = source.index("]", open_bracket)
    return set(re.findall(r'"([^"]+)"', source[open_bracket:close_bracket]))


def _parse_ts_protected_fields(source: str) -> dict[str, set[str]]:
    """Extract `{ Component: new Set([...]) }` from the protected-fields record."""
    start = source.index("export const PROTECTED_TWEAK_FIELDS_BY_COMPONENT")
    body = source[source.index("{", source.index("=", start)) : source.index("};", start)]
    return {
        component: set(re.findall(r'"([^"]+)"', fields))
        for component, fields in re.findall(r"(\w+):\s*new Set\(\[([^\]]*)\]\)", body)
    }


@pytest.mark.skipif(not _FRONTEND_MIRROR.exists(), reason="frontend package not present (standalone lfx checkout)")
def test_frontend_mirrors_tweak_refusal_rules():
    """The frontend mirror of the tweak-refusal rules must match this module exactly.

    Failing here means the UI and the backend disagree about which fields can be
    exposed as API inputs: either the UI is about to offer a field apply_tweaks
    refuses, or it hides one that is legitimately tweakable. Update
    api-exposure-rules.ts (and this test's expectations stay automatic).
    """
    source = _strip_line_comments(_FRONTEND_MIRROR.read_text(encoding="utf-8"))

    assert _parse_ts_string_set(source, "CODE_EXECUTION_COMPONENT_TYPES") == set(CODE_EXECUTION_COMPONENT_TYPES)
    assert _parse_ts_string_set(source, "CODE_EXECUTION_FIELD_NAMES") == set(CODE_EXECUTION_FIELD_NAMES)
    assert _parse_ts_protected_fields(source) == {
        component: set(fields) for component, fields in PROTECTED_TWEAK_FIELDS_BY_COMPONENT.items()
    }


def test_collect_catalog_component_keys_includes_nested_flows():
    """The public collector reports exact keys from the graph and inlined sub-flows."""
    graph = {
        "nodes": [
            {"id": "node-1", "data": {"type": "ChatInput", "node": {}}},
            {
                "id": "node-2",
                "data": {
                    "type": "RunFlow",
                    "node": {
                        "flow": {
                            "data": {
                                "nodes": [
                                    {"id": "nested-1", "data": {"type": "NestedComponent", "node": {}}},
                                ],
                            },
                        },
                    },
                },
            },
        ],
        "edges": [],
    }

    assert collect_catalog_component_keys(graph) == frozenset({"ChatInput", "RunFlow", "NestedComponent"})
    # Wrapped flow payloads normalize the same way validation does.
    assert collect_catalog_component_keys({"data": graph}) == frozenset({"ChatInput", "RunFlow", "NestedComponent"})
    # Graph-like objects resolve through their authoritative raw_graph_data payload.
    graph_like = SimpleNamespace(raw_graph_data=graph)
    assert collect_catalog_component_keys(graph_like) == frozenset({"ChatInput", "RunFlow", "NestedComponent"})


@pytest.mark.parametrize(
    "target",
    [
        None,
        {},
        {"nodes": "not-a-list"},
        {"data": {"nodes": []}},
        SimpleNamespace(),
        SimpleNamespace(raw_graph_data="not-a-mapping"),
    ],
)
def test_collect_catalog_component_keys_returns_empty_for_unusable_targets(target):
    assert collect_catalog_component_keys(target) == frozenset()

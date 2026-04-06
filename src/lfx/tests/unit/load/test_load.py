"""Unit tests for JSON flow loading with custom-component validation."""

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.interface.components import component_cache
from lfx.load import aload_flow_from_json
from lfx.utils.flow_validation import collect_component_hash_lookups


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


def _make_flow(node_type: str, code: str, display_name: str) -> dict:
    return {
        "data": {
            "nodes": [
                {
                    "id": "node-1",
                    "data": {
                        "id": "node-1",
                        "type": node_type,
                        "node": {
                            "display_name": display_name,
                            "template": {
                                "code": {"value": code},
                            },
                        },
                    },
                }
            ],
            "edges": [],
        }
    }


def _settings_service(*, allow_custom_components: bool = False):
    return SimpleNamespace(
        settings=SimpleNamespace(
            allow_custom_components=allow_custom_components,
        )
    )


@pytest.mark.asyncio
async def test_aload_flow_from_json_fail_closed_when_hashes_are_unavailable():
    flow = _make_flow("ChatInput", "current_code", "Chat Input")

    with (
        patch("lfx.load.load.update_settings", new=AsyncMock()),
        patch(
            "lfx.services.deps.get_settings_service",
            return_value=_settings_service(allow_custom_components=False),
        ),
        patch(
            "lfx.utils.flow_validation.ensure_component_hash_lookups_loaded",
            new=AsyncMock(return_value=None),
        ),
        patch.object(component_cache, "type_to_current_hash", None),
        patch.object(component_cache, "all_types_dict", None),
        patch("lfx.graph.graph.base.Graph.add_nodes_and_edges") as mock_add_nodes_and_edges,
        pytest.raises(
            ValueError,
            match=r"Failed to load component templates for validation|component templates are still initializing",
        ),
    ):
        await aload_flow_from_json(flow, disable_logs=True)

    mock_add_nodes_and_edges.assert_not_called()


@pytest.mark.asyncio
async def test_aload_flow_from_json_allows_legacy_url_aliases():
    current_code = "current_url_code"
    flow = _make_flow("URL", current_code, "Legacy URL")
    type_to_current_hash, _ = collect_component_hash_lookups(
        {
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
    )

    with (
        patch("lfx.load.load.update_settings", new=AsyncMock()),
        patch(
            "lfx.services.deps.get_settings_service",
            return_value=_settings_service(allow_custom_components=False),
        ),
        patch(
            "lfx.utils.flow_validation.ensure_component_hash_lookups_loaded",
            new=AsyncMock(return_value=type_to_current_hash),
        ),
        patch.object(component_cache, "type_to_current_hash", type_to_current_hash),
        patch.object(component_cache, "all_types_dict", None),
        patch("lfx.graph.graph.base.Graph.add_nodes_and_edges") as mock_add_nodes_and_edges,
    ):
        graph = await aload_flow_from_json(flow, disable_logs=True)

    assert graph is not None
    mock_add_nodes_and_edges.assert_called_once_with(flow["data"]["nodes"], flow["data"]["edges"])

"""The Assistant's shipped flows must build when custom components are disabled.

``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`` only lets component code that matches a
server template run, so every node in a shipped flow has to be a built-in component.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from lfx.interface.components import get_and_cache_all_types_dict
from lfx.services.deps import get_settings_service
from lfx.utils.flow_validation import ensure_component_hash_lookups_loaded, validate_flow_for_current_settings

_FLOWS_DIR = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows"
_SHIPPED_FLOWS = sorted(_FLOWS_DIR.glob("*.json"))


def test_the_shipped_flows_are_found() -> None:
    assert {path.name for path in _SHIPPED_FLOWS} >= {"LangflowAssistant.json", "TranslationFlow.json"}


@pytest.mark.parametrize("flow_path", _SHIPPED_FLOWS, ids=lambda path: path.name)
async def test_a_shipped_flow_passes_the_custom_component_policy_when_custom_code_is_off(flow_path: Path) -> None:
    await get_and_cache_all_types_dict(get_settings_service())
    await ensure_component_hash_lookups_loaded(force=True)
    restricted = SimpleNamespace(allow_custom_components=False, block_code_interpreter_components=False)
    flow_data = json.loads(flow_path.read_text(encoding="utf-8"))["data"]

    validate_flow_for_current_settings(flow_data, settings=restricted)


@pytest.mark.parametrize("flow_path", _SHIPPED_FLOWS, ids=lambda path: path.name)
def test_a_shipped_flow_has_no_edited_nodes(flow_path: Path) -> None:
    flow_data = json.loads(flow_path.read_text(encoding="utf-8"))["data"]
    edited = [node["id"] for node in flow_data["nodes"] if node.get("data", {}).get("node", {}).get("edited")]
    assert edited == []


def test_the_assistant_keyword_search_node_runs_the_built_in_component_code() -> None:
    from lfx.components.processing import dataframe_keyword_search

    flow_data = json.loads((_FLOWS_DIR / "LangflowAssistant.json").read_text(encoding="utf-8"))["data"]
    [node] = [node for node in flow_data["nodes"] if node["data"]["type"] == "DataFrameKeywordSearch"]
    assert node["data"]["node"]["template"]["code"]["value"] == Path(dataframe_keyword_search.__file__).read_text(
        encoding="utf-8"
    )

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[6]
AGENTIC_FLOW_DIR = REPO_ROOT / "src/backend/base/langflow/agentic/flows"
MCP_COMPONENT_SOURCE = REPO_ROOT / "src/lfx/src/lfx/components/models_and_agents/mcp_component.py"
COMPONENT_INDEX = REPO_ROOT / "src/lfx/src/lfx/_assets/component_index.json"


def _indexed_mcp_component() -> dict:
    index = json.loads(COMPONENT_INDEX.read_text(encoding="utf-8"))
    for category, entries in index["entries"]:
        if category == "models_and_agents":
            return entries["MCPTools"]
    msg = "MCPTools is missing from the generated component index"
    raise AssertionError(msg)


def test_bundled_agentic_mcp_snapshots_match_hardened_component() -> None:
    indexed = _indexed_mcp_component()
    expected_code = MCP_COMPONENT_SOURCE.read_text(encoding="utf-8").rstrip()
    expected_hash = indexed["metadata"]["code_hash"]
    snapshots: list[tuple[str, dict]] = []

    for flow_path in (AGENTIC_FLOW_DIR / "TemplateAssistant.json", AGENTIC_FLOW_DIR / "SystemMessageGen.json"):
        flow = json.loads(flow_path.read_text(encoding="utf-8"))
        for node in flow.get("data", {}).get("nodes", []):
            inner = node.get("data", {}).get("node", {})
            if inner.get("display_name") == "MCP Tools":
                snapshots.append((flow_path.name, inner))

    assert len(snapshots) == 4
    for flow_name, snapshot in snapshots:
        code = snapshot["template"]["code"]["value"]
        assert code.rstrip() == expected_code, f"{flow_name} embeds a stale MCP component"
        assert snapshot["metadata"]["code_hash"] == expected_hash
        assert 'cache_data["user_id"] = user_id' in code
        assert "current_user_id=self.user_id" in code

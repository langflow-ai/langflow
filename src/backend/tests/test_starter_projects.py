"""Test suite for starter project JSON files.

Verifies that starter project JSON files are properly structured and that:
- noteNode types have width/height at the root level
- Other node types have width/height removed from root level
- Agent nodes ship with the new structured default system prompt (not the
  legacy one-liner that QA flagged on Simple Agent / SaaS Pricing /
  Market Research).
"""

import json
from pathlib import Path

import pytest
from lfx.base.agents.default_system_prompt import DEFAULT_SYSTEM_PROMPT_TEMPLATE

STARTER_PROJECTS_DIR = Path(__file__).parent.parent / "base" / "langflow" / "initial_setup" / "starter_projects"

# QA observed this exact legacy text in starter project Agents on the cz/default-sys-prompt branch.
LEGACY_AGENT_SYSTEM_PROMPT = "You are a helpful assistant that can use tools to answer questions and perform tasks."
AGENT_NODE_TYPES = ("Agent", "ToolCallingAgent")


def get_starter_project_files() -> list[Path]:
    """Get all starter project JSON files."""
    if not STARTER_PROJECTS_DIR.exists():
        msg = f"Starter projects directory not found: {STARTER_PROJECTS_DIR}"
        raise FileNotFoundError(msg) from None

    json_files = sorted(STARTER_PROJECTS_DIR.glob("*.json"))
    if not json_files:
        msg = f"No JSON files found in {STARTER_PROJECTS_DIR}"
        raise FileNotFoundError(msg) from None

    return json_files


def load_json_file(json_file: Path) -> dict:
    """Load and parse a JSON file."""
    try:
        with json_file.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in {json_file.name}: {e}"
        raise ValueError(msg) from e
    except Exception as e:
        msg = f"Error reading {json_file.name}: {e}"
        raise OSError(msg) from e


@pytest.mark.parametrize("json_file", get_starter_project_files(), ids=lambda f: f.name)
class TestStarterProjects:
    """Test suite for all starter project JSON files."""

    def test_json_validity(self, json_file: Path):
        """Test that JSON file is valid and can be parsed."""
        data = load_json_file(json_file)
        assert isinstance(data, dict), f"{json_file.name} should be a valid JSON object"

    def test_width_height_at_node_level(self, json_file: Path):
        """Test that width/height are removed from node root level for all node types EXCEPT noteNode.

        noteNode type SHOULD have width/height at root level.
        Other node types should NOT have width/height at root level.
        """
        data = load_json_file(json_file)
        nodes = data["data"]["nodes"]

        issues = []

        for node_idx, node in enumerate(nodes):
            node_type = node.get("type", "unknown")
            node_id = node.get("id", "UNKNOWN")

            # noteNode SHOULD have width/height at root level - skip checking these
            if node_type == "noteNode":
                continue

            # For non-noteNode types, width/height should NOT exist at node level
            if "width" in node:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}, type: {node_type}): "
                    f"'width' found at node root level (value: {node['width']}) - "
                    f"should be removed for non-noteNode types"
                )

            if "height" in node:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}, type: {node_type}): "
                    f"'height' found at node root level (value: {node['height']}) - "
                    f"should be removed for non-noteNode types"
                )

        assert not issues, f"{json_file.name}: Width/height issues found:\n" + "\n".join(issues)

    def test_agent_nodes_use_default_system_prompt_template(self, json_file: Path):
        """Agent nodes must ship with the new DEFAULT_SYSTEM_PROMPT_TEMPLATE.

        Bug: QA reported that Simple Agent, SaaS Pricing, and Market Research
        templates load the legacy one-line system prompt instead of the new
        structured 7-section default. This regression occurs because the
        starter project JSON snapshots embed the literal value at authoring
        time, so they don't pick up the new default when the AgentComponent
        input default changes.

        Fix: every Agent / ToolCallingAgent node in every starter project must
        store the new DEFAULT_SYSTEM_PROMPT_TEMPLATE as its system_prompt
        value (or at the very least, must not store the legacy one-liner).
        """
        data = load_json_file(json_file)
        nodes = data.get("data", {}).get("nodes", [])

        legacy_offenders: list[str] = []
        non_template_offenders: list[str] = []

        for node in nodes:
            node_data = node.get("data", {}) or {}
            node_type = node_data.get("type", "")
            if node_type not in AGENT_NODE_TYPES:
                continue

            template = node_data.get("node", {}).get("template", {}) or {}
            system_prompt_field = template.get("system_prompt", {}) or {}
            value = system_prompt_field.get("value", "")
            node_id = node_data.get("id", "<unknown>")

            if value.strip() == LEGACY_AGENT_SYSTEM_PROMPT:
                legacy_offenders.append(f"{node_id} ({node_type})")
            elif value != DEFAULT_SYSTEM_PROMPT_TEMPLATE:
                non_template_offenders.append(f"{node_id} ({node_type})")

        assert not legacy_offenders, (
            f"{json_file.name}: Agent nodes still use the legacy one-line system prompt: "
            f"{legacy_offenders}. They must use DEFAULT_SYSTEM_PROMPT_TEMPLATE."
        )
        assert not non_template_offenders, (
            f"{json_file.name}: Agent nodes do not use DEFAULT_SYSTEM_PROMPT_TEMPLATE: "
            f"{non_template_offenders}. Update the starter project to ship the new default."
        )

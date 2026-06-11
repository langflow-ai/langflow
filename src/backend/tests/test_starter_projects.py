"""Test suite for starter project JSON files.

Verifies that starter project JSON files are properly structured and that:
- noteNode types have width/height at the root level
- Other node types have width/height removed from root level
- Agent nodes never ship with the legacy one-line prompt that QA flagged
  during the structured-default rollout
- Agent nodes that previously had purpose-specific instructions (e.g.
  Market Research, Pokédex) do not regress to the generic default
"""

import json
from pathlib import Path

import pytest
from lfx.base.agents.default_system_prompt import DEFAULT_SYSTEM_PROMPT_TEMPLATE

STARTER_PROJECTS_DIR = Path(__file__).parent.parent / "base" / "langflow" / "initial_setup" / "starter_projects"

# QA observed this exact legacy text in starter project Agents on the cz/default-sys-prompt branch.
LEGACY_AGENT_SYSTEM_PROMPT = "You are a helpful assistant that can use tools to answer questions and perform tasks."
AGENT_NODE_TYPES = ("Agent", "ToolCallingAgent")

# Templates whose Agents must keep purpose-specific Agent Instructions (not the
# generic DEFAULT_SYSTEM_PROMPT_TEMPLATE). Regression guard for #12855: that PR
# replaced every starter Agent's system_prompt.value with the new structured
# default, wiping the role-specific prompts these flows depend on. Each entry
# pairs (starter project filename, agent node id) with a substring that must
# appear in the agent's system_prompt.value.
TEMPLATES_WITH_CUSTOM_AGENT_PROMPTS: dict[tuple[str, str], str] = {
    ("Instagram Copywriter.json", "Agent-DYPjp"): "information from a web search",
    ("Market Research.json", "Agent-Hz2it"): "expert business research agent",
    ("News Aggregator.json", "Agent-ZH2Rd"): "content writer researching news",
    ("Pokédex Agent.json", "Agent-R27kt"): "You are a pokedex",
    ("Research Agent.json", "Agent-mIgZ5"): "research analyst with access to Tavily Search",
    ("SaaS Pricing.json", "Agent-bNGtH"): "Subscription Pricing Calculator",
    ("Travel Planning Agents.json", "Agent-9tDeE"): "knowledgeable Local Expert",
    ("Travel Planning Agents.json", "Agent-C8zRS"): "Amazing Travel Concierge",
    ("Youtube Analysis.json", "Agent-2FN2V"): "comprehensive YouTube video analysis",
}


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

    def test_agent_nodes_do_not_use_legacy_system_prompt(self, json_file: Path):
        """Agent nodes must not ship with the legacy one-line system prompt.

        Background: PR #12855 introduced a structured 7-section
        DEFAULT_SYSTEM_PROMPT_TEMPLATE to replace the old one-line
        "You are a helpful assistant..." default. The original version of
        this test asserted that every Agent in every starter project use
        the new DEFAULT_SYSTEM_PROMPT_TEMPLATE — that assertion caused a
        regression: starter projects with purpose-specific Agent
        Instructions (Market Research, Pokédex, SaaS Pricing, etc.) had
        their custom prompts overwritten by the generic default to keep
        the test green.

        New contract: ship the generic default OR a template-specific
        prompt, but never the legacy one-liner. A separate parametrised
        test (test_agent_keeps_template_specific_prompt) guards the
        specific templates that must keep their custom instructions.
        """
        data = load_json_file(json_file)
        nodes = data.get("data", {}).get("nodes", [])

        legacy_offenders: list[str] = []

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

        assert not legacy_offenders, (
            f"{json_file.name}: Agent nodes still use the legacy one-line system prompt: "
            f"{legacy_offenders}. Use DEFAULT_SYSTEM_PROMPT_TEMPLATE or a template-specific prompt."
        )


@pytest.mark.parametrize(
    ("template_file", "agent_id", "required_substring"),
    [
        (filename, agent_id, substring)
        for (filename, agent_id), substring in TEMPLATES_WITH_CUSTOM_AGENT_PROMPTS.items()
    ],
    ids=lambda v: v if isinstance(v, str) else repr(v),
)
def test_agent_keeps_template_specific_prompt(template_file: str, agent_id: str, required_substring: str):
    """Templates with purpose-specific Agent Instructions must not regress to the generic default.

    Regression guard for #12855: that PR's auto-bake replaced every starter
    Agent's system_prompt.value with DEFAULT_SYSTEM_PROMPT_TEMPLATE,
    silently dropping role-specific prompts (Market Research's business
    researcher, Pokédex's API guidance, etc.). The flows that depend on
    those instructions broke at runtime. If you legitimately need to
    change one of these prompts, update the substring in
    TEMPLATES_WITH_CUSTOM_AGENT_PROMPTS in the same change.
    """
    path = STARTER_PROJECTS_DIR / template_file
    assert path.exists(), f"Starter template not found: {path}"

    data = load_json_file(path)
    for node in data.get("data", {}).get("nodes", []):
        node_data = node.get("data", {}) or {}
        if node_data.get("id") != agent_id:
            continue
        template = node_data.get("node", {}).get("template", {}) or {}
        value = (template.get("system_prompt", {}) or {}).get("value", "")
        assert value != DEFAULT_SYSTEM_PROMPT_TEMPLATE, (
            f"{template_file}: agent {agent_id} regressed to DEFAULT_SYSTEM_PROMPT_TEMPLATE; "
            f"restore the template-specific Agent Instructions containing {required_substring!r}."
        )
        assert required_substring in value, (
            f"{template_file}: agent {agent_id} system_prompt does not contain expected "
            f"substring {required_substring!r}. Got: {value[:120]!r}..."
        )
        return
    pytest.fail(f"{template_file}: agent node {agent_id!r} not found")

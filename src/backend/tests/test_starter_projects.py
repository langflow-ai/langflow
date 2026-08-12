"""Test suite for starter project JSON files.

Verifies that starter project JSON files are properly structured and that:
- noteNode types have width/height at the root level
- Other node types have width/height removed from root level
- Agent nodes never ship with the legacy one-line prompt that QA flagged
  during the structured-default rollout
- Agent nodes that previously had purpose-specific instructions (e.g.
  Market Research, SaaS Pricing) do not regress to the generic default
"""

import json
from pathlib import Path

import pytest
from lfx.base.agents.default_system_prompt import DEFAULT_SYSTEM_PROMPT_TEMPLATE

STARTER_PROJECTS_DIR = Path(__file__).parent.parent / "base" / "langflow" / "initial_setup" / "starter_projects"
LOCALES_EN_FILE = Path(__file__).parent.parent / "base" / "langflow" / "locales" / "en.json"

# QA observed this exact legacy text in starter project Agents on the cz/default-sys-prompt branch.
LEGACY_AGENT_SYSTEM_PROMPT = "You are a helpful assistant that can use tools to answer questions and perform tasks."
AGENT_NODE_TYPES = ("Agent", "ToolCallingAgent")
REMOVED_STARTER_PROJECTS = {
    "Invoice Summarizer.json",
    "Nvidia Remix.json",
    "Pokédex Agent.json",
    "Search agent.json",
}
RENAMED_STARTER_PROJECTS = {
    "Basic Prompt Chaining.json": "Multi Agent Flow.json",
    "News Aggregator.json": "Content Aggregator.json",
    "Research Agent.json": "Deep Research Agent.json",
}
BLOCKED_MODEL_OPTION_NAMES = {"gpt-image-2", "gemini-3.1-flash-lite-preview"}
BLOCKED_MODEL_OPTION_PREFIXES = ("ibm/mock-",)

# Templates whose Agents must keep purpose-specific Agent Instructions (not the
# generic DEFAULT_SYSTEM_PROMPT_TEMPLATE). Regression guard for #12855: that PR
# replaced every starter Agent's system_prompt.value with the new structured
# default, wiping the role-specific prompts these flows depend on. Each entry
# pairs (starter project filename, agent node id) with a substring that must
# appear in the agent's system_prompt.value.
TEMPLATES_WITH_CUSTOM_AGENT_PROMPTS: dict[tuple[str, str], str] = {
    ("Instagram Copywriter.json", "Agent-caption"): "expert Instagram copywriter",
    ("Market Research.json", "Agent-Hz2it"): "expert business research agent",
    ("Content Aggregator.json", "Agent-ZH2Rd"): "content aggregator",
    ("Deep Research Agent.json", "Agent-mIgZ5"): "research analyst with access to Tavily Search",
    ("SaaS Pricing.json", "Agent-Zm0pK"): "calculate the price",
    ("Travel Planning Agents.json", "Agent-v7SnN"): "knowledgeable Local Expert",
    ("Travel Planning Agents.json", "Agent-1ON2c"): "Amazing Travel Concierge",
    ("Youtube Analysis.json", "Agent-s4EYR"): "comprehensive YouTube video analysis",
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


def iter_dicts(value):
    """Yield every dict nested inside a parsed starter JSON structure."""
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from iter_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_dicts(nested)


def model_option_name(option) -> str | None:
    if isinstance(option, str):
        return option
    if isinstance(option, dict) and isinstance(option.get("name"), str):
        return option["name"]
    return None


def is_blocked_model_option(name: str) -> bool:
    return name in BLOCKED_MODEL_OPTION_NAMES or name.startswith(BLOCKED_MODEL_OPTION_PREFIXES)


def test_removed_and_renamed_starter_inventory():
    """Starter inventory should not keep loading removed or renamed templates from disk."""
    shipped = {path.name for path in get_starter_project_files()}

    assert not REMOVED_STARTER_PROJECTS & shipped
    for old_name, new_name in RENAMED_STARTER_PROJECTS.items():
        assert old_name not in shipped
        assert new_name in shipped


@pytest.mark.parametrize("json_file", get_starter_project_files(), ids=lambda f: f.name)
class TestStarterProjects:
    """Test suite for all starter project JSON files."""

    def test_json_validity(self, json_file: Path):
        """Test that JSON file is valid and can be parsed."""
        data = load_json_file(json_file)
        assert isinstance(data, dict), f"{json_file.name} should be a valid JSON object"

    def test_prompt_custom_fields_are_materialized(self, json_file: Path):
        """Prompt variables declared in custom_fields must exist in the serialized template."""
        data = load_json_file(json_file)
        missing_fields: list[str] = []

        for node in data.get("data", {}).get("nodes", []):
            node_data = node.get("data", {}) or {}
            node_config = node_data.get("node", {}) or {}
            template = node_config.get("template", {}) or {}
            custom_fields = node_config.get("custom_fields", {}) or {}

            for field_names in custom_fields.values():
                if not isinstance(field_names, list):
                    continue
                for field_name in field_names:
                    if field_name not in template:
                        node_id = node_data.get("id", node.get("id", "<unknown>"))
                        missing_fields.append(f"{node_id}.{field_name}")

        assert not missing_fields, (
            f"{json_file.name}: custom prompt fields are missing from the serialized node template: {missing_fields}"
        )

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
        Instructions (Market Research, SaaS Pricing, etc.) had
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

    def test_model_options_do_not_ship_removed_or_internal_models(self, json_file: Path):
        """Starter model pickers should not expose non-text or internal mock models."""
        data = load_json_file(json_file)
        offenders: list[str] = []

        for node_dict in iter_dicts(data):
            options = node_dict.get("options")
            if not isinstance(options, list):
                continue

            for option in options:
                name = model_option_name(option)
                if name and is_blocked_model_option(name):
                    offenders.append(name)

        assert not offenders, f"{json_file.name}: blocked model options found: {sorted(set(offenders))}"

    def test_ollama_base_url_uses_current_metadata(self, json_file: Path):
        """Serialized Language Model fields should match the current Ollama URL input shape."""
        data = load_json_file(json_file)
        fields = [field for field in iter_dicts(data) if field.get("name") == "ollama_base_url"]

        for field in fields:
            assert field.get("_input_type") == "StrInput"
            assert field.get("input_types") == []
            assert field.get("type") == "str"
            assert field.get("info") == "Endpoint of the Ollama API (Ollama only)"
            assert field.get("value") == ""

    def test_knowledge_base_selectors_do_not_ship_fixture_defaults(self, json_file: Path):
        """Knowledge selectors should start empty instead of pointing at local test fixture names."""
        data = load_json_file(json_file)
        offenders = [
            field.get("value")
            for field in iter_dicts(data)
            if field.get("name") == "knowledge_base" and field.get("value")
        ]

        assert not offenders, f"{json_file.name}: knowledge_base defaults should be empty, got {offenders}"

    def test_note_i18n_keys_match_embedded_english_text(self, json_file: Path):
        """English note translations must not overwrite refreshed README text with stale copy."""
        data = load_json_file(json_file)
        en_locale = load_json_file(LOCALES_EN_FILE)
        mismatches: list[str] = []

        for node_dict in iter_dicts(data):
            i18n_key = node_dict.get("i18n_key")
            description = node_dict.get("description")
            if not isinstance(i18n_key, str) or not isinstance(description, str) or i18n_key not in en_locale:
                continue
            if en_locale[i18n_key] != description:
                mismatches.append(i18n_key)

        assert not mismatches, f"{json_file.name}: stale English note i18n keys found: {mismatches}"


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
    researcher, SaaS Pricing's calculation guidance, etc.). The flows that depend on
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

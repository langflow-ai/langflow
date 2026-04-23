"""Tests for the default system prompt template and builder."""

from lfx.base.agents.default_system_prompt import (
    DEFAULT_SYSTEM_PROMPT_TEMPLATE,
    build_default_system_prompt,
    substitute_env_placeholders,
)

SECTION_HEADERS_IN_ORDER = [
    "# Identity",
    "# Safety",
    "# Using tools",
    "# Doing tasks",
    "# Action safety",
    "# Tone",
    "# Environment",
]


# Slice A — builder exists and returns a non-empty string
def test_should_return_non_empty_string_when_called_with_minimum_args():
    # Act
    result = build_default_system_prompt(
        current_date="2026-04-22",
        model_name="claude-opus-4-7",
    )

    # Assert
    assert isinstance(result, str)
    assert len(result) > 0


# Slice B — template contains 7 section headers in required order
def test_should_contain_seven_section_headers_in_required_order():
    # Act
    positions = [DEFAULT_SYSTEM_PROMPT_TEMPLATE.find(h) for h in SECTION_HEADERS_IN_ORDER]

    # Assert — every header exists
    for header, pos in zip(SECTION_HEADERS_IN_ORDER, positions, strict=True):
        assert pos != -1, f"missing section header: {header!r}"

    # Assert — headers appear in the required order
    assert positions == sorted(positions), (
        f"section headers are out of order: {list(zip(SECTION_HEADERS_IN_ORDER, positions, strict=True))}"
    )


# Slice C — template line count is within 30-100
def test_should_have_line_count_between_thirty_and_one_hundred():
    # Act
    line_count = len(DEFAULT_SYSTEM_PROMPT_TEMPLATE.splitlines())

    # Assert
    assert 30 <= line_count <= 100, f"template has {line_count} lines; expected 30-100"


# Slice D — builder substitutes {current_date}
def test_should_substitute_current_date_placeholder_when_building_prompt():
    # Act
    result = build_default_system_prompt(
        current_date="2026-04-22",
        model_name="claude-opus-4-7",
    )

    # Assert
    assert "2026-04-22" in result
    assert "{current_date}" not in result


# Slice E — builder substitutes {model_name}
def test_should_substitute_model_name_placeholder_when_building_prompt():
    # Act
    result = build_default_system_prompt(
        current_date="2026-04-22",
        model_name="claude-opus-4-7",
    )

    # Assert
    assert "claude-opus-4-7" in result
    assert "{model_name}" not in result


# Slice F — builder substitutes optional user_context when provided
def test_should_substitute_user_context_when_provided():
    # Act
    result = build_default_system_prompt(
        current_date="2026-04-22",
        model_name="claude-opus-4-7",
        user_context="deploying on Railway, Brazilian Portuguese users",
    )

    # Assert
    assert "deploying on Railway, Brazilian Portuguese users" in result
    assert "{optional_user_context}" not in result


# Slice G — builder removes user_context placeholder when None
def test_should_remove_user_context_placeholder_when_none():
    # Act
    result = build_default_system_prompt(
        current_date="2026-04-22",
        model_name="claude-opus-4-7",
        user_context=None,
    )

    # Assert — no orphan placeholder leaks to the LLM
    assert "{optional_user_context}" not in result


# Slice H — template must not contain a tool list or {tools} placeholder
def test_should_not_contain_tools_placeholder_or_hardcoded_tool_list():
    lower = DEFAULT_SYSTEM_PROMPT_TEMPLATE.lower()

    assert "{tools}" not in DEFAULT_SYSTEM_PROMPT_TEMPLATE, (
        "Template must not embed a tool list; tools are exposed via the API."
    )
    assert "available tools:" not in lower, (
        "Template must not hardcode a 'Available tools:' block."
    )


# Slice I — template contains safety directives (fabrication, prompt injection, destructive)
def test_should_contain_safety_directives_for_fabrication_injection_and_destructive_actions():
    lower = DEFAULT_SYSTEM_PROMPT_TEMPLATE.lower()

    # Fabrication guard
    assert "fabricate" in lower or "fabricat" in lower, "Template must forbid fabrication."
    # Prompt-injection guard (flagging language)
    assert "flag" in lower, "Template must direct the agent to flag suspicious tool output."
    assert "ignore previous" in lower or "ignore" in lower, "Template must name the prompt-injection pattern."
    # Destructive action guard
    assert "confirm" in lower, "Template must require confirmation before destructive actions."


# Slice J — template contains tool-use discipline
def test_should_contain_tool_use_discipline_directives():
    lower = DEFAULT_SYSTEM_PROMPT_TEMPLATE.lower()

    assert "invent" in lower or "only call" in lower or "do not invent" in lower, (
        "Template must forbid inventing tools."
    )
    assert "parallel" in lower, "Template must mention parallel tool calls."
    assert "retry" in lower, "Template must address retry / error-diagnosis discipline."


# Slice K — template contains scope / tone discipline
def test_should_contain_scope_and_tone_discipline():
    lower = DEFAULT_SYSTEM_PROMPT_TEMPLATE.lower()

    assert "concise" in lower, "Template must require concise responses."
    assert "emoji" in lower, "Template must address emoji usage."
    assert "what was asked" in lower or "scope" in lower or "match" in lower, (
        "Template must require matching scope to the request."
    )


# Slice O.1 — substitute_env_placeholders is a no-op for prompts without placeholders
def test_should_return_prompt_unchanged_when_no_known_placeholders_are_present():
    # Arrange
    custom = "You are a pirate. Speak only in sea shanties."

    # Act
    rendered = substitute_env_placeholders(
        custom,
        current_date="2026-04-22",
        model_name="claude-opus-4-7",
        user_context=None,
    )

    # Assert
    assert rendered == custom


# Slice O.2 — substitute_env_placeholders handles known placeholders on an arbitrary prompt
def test_should_substitute_env_placeholders_on_arbitrary_prompt():
    # Arrange
    custom = "Today is {current_date}. You are {model_name}. {optional_user_context}"

    # Act
    rendered = substitute_env_placeholders(
        custom,
        current_date="2026-04-22",
        model_name="claude-opus-4-7",
        user_context="pt-BR users",
    )

    # Assert
    assert "{current_date}" not in rendered
    assert "{model_name}" not in rendered
    assert "{optional_user_context}" not in rendered
    assert "2026-04-22" in rendered
    assert "claude-opus-4-7" in rendered
    assert "pt-BR users" in rendered


# Slice L — static prefix is byte-identical across calls with different env values
def test_should_preserve_static_prefix_across_calls_with_different_env():
    # Act
    a = build_default_system_prompt(current_date="2020-01-01", model_name="m1")
    b = build_default_system_prompt(current_date="2099-12-31", model_name="m2")

    # Find the Environment header in both renders
    idx_a = a.find("# Environment")
    idx_b = b.find("# Environment")

    # Assert — everything before "# Environment" is identical (cache boundary)
    assert idx_a != -1, "first render missing the Environment header"
    assert idx_b != -1, "second render missing the Environment header"
    assert a[:idx_a] == b[:idx_b], "static prefix must be byte-identical across calls"

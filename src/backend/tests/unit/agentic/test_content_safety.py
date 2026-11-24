"""The assistant's deterministic content guardrail.

Until this existed, nothing outside the model stopped the assistant emitting slurs:
`sanitize_input` only knows prompt injection, and the off-topic gate is an LLM call on the
user's own model -- so a local unaligned provider (Ollama, any OpenAI-compatible base_url,
both supported) left no guardrail at all. These tests pin the floor: pure regex, no model,
no network.

They also pin what it must NOT do. Langflow users legitimately build moderation flows, so a
component that classifies hate speech has to stay buildable; blocking on topic words instead
of actual slurs would break that, and a filter with false positives gets turned off.
"""

import pytest
from langflow.agentic.helpers.content_safety import (
    REFUSAL_MESSAGE,
    ContentCategory,
    check_content,
)


class TestBlocksHarmfulContent:
    def test_should_block_a_racial_slur(self):
        result = check_content("you are a nigger")

        assert result.is_safe is False
        assert result.category is ContentCategory.SLUR

    def test_should_block_a_portuguese_slur(self):
        result = check_content("seu viado")

        assert result.is_safe is False
        assert result.category is ContentCategory.SLUR

    def test_should_block_explicit_profanity(self):
        result = check_content("what the fuck is this")

        assert result.is_safe is False
        assert result.category is ContentCategory.PROFANITY

    def test_should_block_portuguese_profanity(self):
        result = check_content("que porra e essa")

        assert result.is_safe is False
        assert result.category is ContentCategory.PROFANITY

    def test_should_block_leetspeak_evasion(self):
        result = check_content("you n1gger")

        assert result.is_safe is False
        assert result.category is ContentCategory.SLUR

    def test_should_report_the_matched_term_for_logging(self):
        result = check_content("what the fuck")

        assert result.matched_term is not None
        assert result.violation is not None
        assert "profanity" in result.violation


class TestDoesNotBreakLegitimateUse:
    """A guardrail that cries wolf gets disabled, so false positives are the real risk."""

    @pytest.mark.parametrize(
        "text",
        [
            "build a component that classifies hate speech",
            "create a toxicity moderation flow for my chatbot",
            "add a profanity filter to this flow",
            "connect ChatInput to ChatOutput",
            "how do I use the Agent component with Ollama?",
            "create a component that detects racism in user messages",
            "",
        ],
    )
    def test_should_allow_legitimate_langflow_requests(self, text):
        assert check_content(text).is_safe is True

    @pytest.mark.parametrize("text", ["I need to classify documents", "scunthorpe united", "the class assignment"])
    def test_should_not_match_substrings_inside_innocent_words(self, text):
        assert check_content(text).is_safe is True


def test_should_need_no_configuration():
    """No settings, no env var: the guardrail is always on and reads nothing at runtime."""
    import inspect

    from langflow.agentic.helpers import content_safety

    assert "get_settings_service" not in inspect.getsource(content_safety)


def test_refusal_message_names_the_assistant_and_offers_a_way_forward():
    assert "Langflow Assistant" in REFUSAL_MESSAGE
    assert "build" in REFUSAL_MESSAGE

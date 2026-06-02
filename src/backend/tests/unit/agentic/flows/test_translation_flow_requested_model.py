"""Prompt-contract for extracting the user's explicitly-named model.

The actual extraction is performed by an LLM at runtime; these tests assert the
prompt is the executable spec — it must declare ``requested_model`` /
``requested_provider`` in the output format and teach (by example) to fill them
ONLY when the user names a model, leaving them empty otherwise.
"""

from __future__ import annotations

import re

from langflow.agentic.flows.translation_flow import TRANSLATION_PROMPT


def test_prompt_should_declare_requested_model_in_output_format():
    assert "requested_model" in TRANSLATION_PROMPT
    assert "requested_provider" in TRANSLATION_PROMPT


def test_prompt_should_include_an_example_that_names_a_model():
    # At least one example Output JSON carries a non-empty requested_model.
    named = re.findall(r'"requested_model":\s*"([^"]+)"', TRANSLATION_PROMPT)
    assert any(v.strip() for v in named), (
        f"Expected at least one example with a populated requested_model, got: {named}"
    )


def test_prompt_should_include_an_example_with_empty_model_when_none_named():
    # And at least one example where no model is named (empty string), so the
    # LLM learns not to hallucinate a model for plain requests.
    assert '"requested_model": ""' in TRANSLATION_PROMPT

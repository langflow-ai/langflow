"""Tests for the TranslationFlow intent coverage.

These tests assert the prompt-level contract: which intents the TranslationFlow
declares, and which user phrasings map to each intent in the examples block.

Why prompt-level (not behavioral): the actual classification is performed by an
LLM at runtime, and behavioral tests would require a live model. The prompt is
the executable specification of the routing rule — if the intent or its
examples are missing here, the LLM has no way to learn the routing.
"""

import re

from langflow.agentic.flows.translation_flow import TRANSLATION_PROMPT


class TestManageFilesIntentDeclared:
    """Slice B1 — manage_files intent is declared in the prompt with disambiguating examples."""

    def test_translation_prompt_should_list_manage_files_intent(self):
        # Arrange / Act
        prompt = TRANSLATION_PROMPT

        # Assert — intent label must be declared in the JSON output format
        assert "manage_files" in prompt, "TRANSLATION_PROMPT must list 'manage_files' as a recognized intent"
        # ... and in the union in the output format line
        output_format_match = re.search(r'"intent":\s*"<([^"]+)>"', prompt)
        assert output_format_match is not None, "Could not locate output format line"
        union = output_format_match.group(1)
        assert "manage_files" in union.split("|"), f"manage_files must appear in the output format union, got: {union}"

    def test_translation_prompt_should_include_manage_files_example_in_english(self):
        prompt = TRANSLATION_PROMPT
        # At least one example whose Output JSON pairs an English file-action input with manage_files intent.
        # Match any line like: Output: {{"translation": "<en>", "intent": "manage_files"}}
        examples = re.findall(
            r'Output:\s*\{\{"translation":\s*"([^"]+)",\s*"intent":\s*"manage_files"\}\}',
            prompt,
        )
        # At least one English example mentioning files / writing / saving.
        english_file_examples = [
            ex for ex in examples if re.search(r"\b(file|markdown|md|write|save|read|document)\b", ex, re.IGNORECASE)
        ]
        assert english_file_examples, (
            f"Expected at least one English manage_files example mentioning file/markdown/document, got: {examples}"
        )

    def test_translation_prompt_should_include_manage_files_example_in_portuguese(self):
        prompt = TRANSLATION_PROMPT
        # Inputs (not translations) in PT — the example block has Input: "<pt>" / Output: ... .
        # We assert at least one Input line that looks Portuguese AND its paired Output is manage_files.
        pt_blocks = re.findall(
            r'Input:\s*"([^"]+)"\s*\nOutput:\s*\{\{"translation":\s*"[^"]+",\s*"intent":\s*"manage_files"\}\}',
            prompt,
        )
        pt_examples = [
            block
            for block in pt_blocks
            if re.search(r"\b(crie|criar|salve|salvar|arquivo|documenta|leia|ler)\b", block, re.IGNORECASE)
        ]
        assert pt_examples, f"Expected at least one Portuguese manage_files example, got blocks: {pt_blocks}"

    def test_translation_prompt_should_not_classify_file_creation_examples_as_build_flow(self):
        """Disambiguation guard: no example pairs file-creation phrasing with build_flow intent."""
        prompt = TRANSLATION_PROMPT
        # Find all Input/Output example blocks.
        blocks = re.findall(
            r'Input:\s*"([^"]+)"\s*\nOutput:\s*\{\{"translation":\s*"([^"]+)",\s*"intent":\s*"([^"]+)"\}\}',
            prompt,
        )
        # Look for file/document phrasing inside any block paired with build_flow.
        file_phrases = re.compile(
            r"\b(file|markdown|\.md|write\s+a\s+file|save\s+(?:as|to)\s+file|crie\s+um\s+arquivo|salve\s+o\s+arquivo)\b",
            re.IGNORECASE,
        )
        offenders = [
            (block[0], block[2]) for block in blocks if block[2] == "build_flow" and file_phrases.search(block[0])
        ]
        assert not offenders, (
            f"File-creation phrasings must not be classified as build_flow. Offending examples: {offenders}"
        )


class TestFollowUpSessionContextRouting:
    """WS-1 / RC-1 — prompt teaches the classifier to use the session-context block for follow-ups."""

    def test_translation_prompt_should_reference_session_context_block(self):
        prompt = TRANSLATION_PROMPT.lower()
        assert "session context" in prompt, (
            "Prompt must tell the classifier a [Session context ...] block may precede the user message"
        )

    def test_translation_prompt_should_route_contextual_followup_to_build_flow(self):
        """With session context present, an imperative follow-up is build_flow, not question/off_topic."""
        prompt = TRANSLATION_PROMPT.lower()
        has_rule = (
            "session context" in prompt
            and "build_flow" in prompt
            and ("follow-up" in prompt or "follow up" in prompt or "followup" in prompt)
        )
        assert has_rule, (
            "Prompt must include a rule: with session context present, a follow-up "
            "edit/build is build_flow (not question/off_topic)"
        )

    def test_translation_prompt_should_translate_only_user_message_not_context(self):
        prompt = TRANSLATION_PROMPT.lower()
        assert "do not translate" in prompt, "Prompt must instruct: do not translate the quoted context"
        assert "session context" in prompt, "Prompt must name the session context block"


class TestFileQuestionDisambiguationStillHolds:
    """Regression guard — the original file-question disambiguation rule must survive the Slice 4 edits."""

    def test_translation_prompt_should_include_disambiguation_rule_for_file_question(self):
        """`how do I save a file?` is a Langflow question, not a file action."""
        prompt = TRANSLATION_PROMPT
        # Either as an explicit rule line OR as a question example.
        rule_or_example = (
            "how do I save" in prompt.lower()
            or "how to save a file" in prompt.lower()
            or "how do i create a file" in prompt.lower()
        )
        assert rule_or_example, (
            "Prompt should disambiguate 'how do I save/create a file?' as question, not manage_files"
        )


class TestRunFlowIntentDeclared:
    """Bugfix — run/execute/test the flow is its own intent (run_flow), not build_flow."""

    def test_prompt_declares_run_flow_intent(self):
        prompt = TRANSLATION_PROMPT
        assert '"run_flow"' in prompt, "TRANSLATION_PROMPT must declare the run_flow intent"
        m = re.search(r'"intent":\s*"<([^"]+)>"', prompt)
        assert m is not None
        assert "run_flow" in m.group(1).split("|"), f"run_flow must be in the output union, got: {m.group(1)}"

    def test_prompt_has_run_flow_examples(self):
        prompt = TRANSLATION_PROMPT
        examples = re.findall(
            r'Output:\s*\{\{"translation":\s*"([^"]+)",\s*"intent":\s*"run_flow"\}\}',
            prompt,
        )
        assert examples, "Expected at least one run_flow example"
        assert any(re.search(r"\b(run|execute|test)\b", ex, re.IGNORECASE) for ex in examples), (
            f"run_flow examples should use run/execute/test verbs, got: {examples}"
        )

    def test_run_examples_are_not_classified_as_build_flow(self):
        prompt = TRANSLATION_PROMPT
        blocks = re.findall(
            r'Input:\s*"([^"]+)"\s*\nOutput:\s*\{\{"translation":\s*"[^"]+",\s*"intent":\s*"([^"]+)"\}\}',
            prompt,
        )
        run_phrase = re.compile(r"\b(rode o flow|run the flow|execute o flow|execute the flow)\b", re.IGNORECASE)
        offenders = [(i, intent) for i, intent in blocks if intent == "build_flow" and run_phrase.search(i)]
        assert not offenders, f"run-the-flow phrasings must be run_flow, not build_flow: {offenders}"

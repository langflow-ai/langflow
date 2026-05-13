"""Unit tests for langflow.services.memory_base.preprocessing.

Coverage:
- is_kill_phrase: exact-match rule, case-insensitivity, substring rejection,
  whitespace tolerance, per-line matching, empty inputs.
- _format_batch: empty list, text-only, content-block text, combined, no-body skip.
- _build_model_config: structure, provider params, optional url/project_id keys.
- run_preprocessing: LLM called once, kill-phrase → skipped, normal → ingested,
  empty-messages early-exit, api-key lookup, system-message construction.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.database.models.message.model import MessageTable

# ------------------------------------------------------------------ #
#  Shared helpers                                                      #
# ------------------------------------------------------------------ #


def _make_message(
    *,
    session_id: str = "sess-1",
    text: str = "hello",
    timestamp: datetime | None = None,
    content_blocks: list | None = None,
    sender_name: str = "Bot",
    sender: str = "AI",
) -> MessageTable:
    return MessageTable(
        id=uuid.uuid4(),
        sender=sender,
        sender_name=sender_name,
        session_id=session_id,
        text=text,
        flow_id=uuid.uuid4(),
        timestamp=timestamp or datetime.now(timezone.utc),
        content_blocks=content_blocks or [],
    )


# ------------------------------------------------------------------ #
#  is_kill_phrase                                                      #
# ------------------------------------------------------------------ #


class TestIsKillPhrase:
    def _call(self, response: str, kill_phrase: str) -> bool:
        from langflow.services.memory_base.preprocessing import is_kill_phrase

        return is_kill_phrase(response, kill_phrase)

    def test_exact_match_returns_true(self):
        assert self._call("NO_INGEST", "NO_INGEST") is True

    def test_case_insensitive_lower(self):
        assert self._call("no_ingest", "NO_INGEST") is True

    def test_case_insensitive_mixed(self):
        assert self._call("No_Ingest", "NO_INGEST") is True

    def test_kill_phrase_case_insensitive_too(self):
        assert self._call("NO_INGEST", "no_ingest") is True

    def test_substring_does_not_match(self):
        assert self._call("NO_INGEST_PLEASE", "NO_INGEST") is False

    def test_prefix_does_not_match(self):
        assert self._call("NO_INGESTION", "NO_INGEST") is False

    def test_response_with_surrounding_whitespace(self):
        assert self._call("  NO_INGEST  ", "NO_INGEST") is True

    def test_kill_phrase_as_standalone_line_matches(self):
        assert self._call("Some text\nNO_INGEST\nmore text", "NO_INGEST") is True

    def test_kill_phrase_on_first_line(self):
        assert self._call("NO_INGEST\nsome other text", "NO_INGEST") is True

    def test_kill_phrase_on_last_line(self):
        assert self._call("some preamble\nNO_INGEST", "NO_INGEST") is True

    def test_kill_phrase_embedded_in_line_does_not_match(self):
        assert self._call("prefix NO_INGEST suffix", "NO_INGEST") is False

    def test_empty_response_returns_false(self):
        assert self._call("", "NO_INGEST") is False

    def test_empty_kill_phrase_returns_false(self):
        assert self._call("NO_INGEST", "") is False

    def test_both_empty_returns_false(self):
        assert self._call("", "") is False

    def test_whitespace_only_kill_phrase_returns_false(self):
        assert self._call("NO_INGEST", "   ") is False

    def test_custom_kill_phrase(self):
        assert self._call("SKIP_THIS", "SKIP_THIS") is True

    def test_custom_kill_phrase_wrong_response(self):
        assert self._call("NO_INGEST", "SKIP_THIS") is False

    def test_kill_phrase_with_leading_whitespace_on_line(self):
        assert self._call("intro\n  NO_INGEST  \ntrailing", "NO_INGEST") is True

    def test_multiline_kill_phrase_line_is_case_insensitive(self):
        assert self._call("preamble\nno_ingest\nmore", "NO_INGEST") is True


# ------------------------------------------------------------------ #
#  _format_batch                                                       #
# ------------------------------------------------------------------ #


class TestFormatBatch:
    def _call(self, messages: list) -> str:
        from langflow.services.memory_base.preprocessing import _format_batch

        return _format_batch(messages)

    def test_empty_list_returns_empty_string(self):
        assert self._call([]) == ""

    def test_single_message_text_included(self):
        msg = _make_message(text="hello world", sender_name="Alice", sender="User")
        result = self._call([msg])
        assert "hello world" in result
        assert "Alice" in result

    def test_single_message_format_contains_timestamp_bracket(self):
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        msg = _make_message(text="hi", timestamp=ts)
        result = self._call([msg])
        assert "[2024-01-15" in result

    def test_whitespace_only_text_and_no_blocks_skipped(self):
        msg = _make_message(text="   ", content_blocks=[])
        result = self._call([msg])
        assert result == ""

    def test_empty_text_and_no_blocks_skipped(self):
        msg = _make_message(text="", content_blocks=[])
        result = self._call([msg])
        assert result == ""

    def test_content_block_text_included_when_text_empty(self):
        msg = _make_message(
            text="",
            content_blocks=[{"contents": [{"type": "text", "text": "from block"}]}],
        )
        result = self._call([msg])
        assert "from block" in result

    def test_text_and_content_block_combined(self):
        msg = _make_message(
            text="main text",
            content_blocks=[{"contents": [{"type": "text", "text": "block text"}]}],
        )
        result = self._call([msg])
        assert "main text" in result
        assert "block text" in result

    def test_multiple_messages_joined_by_separator(self):
        msg1 = _make_message(text="first")
        msg2 = _make_message(text="second")
        result = self._call([msg1, msg2])
        assert "\n\n---\n\n" in result
        assert "first" in result
        assert "second" in result

    def test_sender_name_used_as_speaker(self):
        msg = _make_message(text="hi", sender_name="Bob", sender="AI")
        result = self._call([msg])
        assert "Bob" in result

    def test_sender_fallback_when_sender_name_none(self):
        msg = _make_message(text="hi", sender_name="Bot", sender="AI")
        object.__setattr__(msg, "sender_name", None)
        result = self._call([msg])
        assert "AI" in result

    def test_mixed_valid_and_empty_messages(self):
        msg_valid = _make_message(text="keep me")
        msg_empty = _make_message(text="  ", content_blocks=[])
        result = self._call([msg_valid, msg_empty])
        assert "keep me" in result
        assert "\n\n---\n\n" not in result

    def test_none_timestamp_produces_empty_bracket(self):
        msg = _make_message(text="hi")
        object.__setattr__(msg, "timestamp", None)
        result = self._call([msg])
        assert "[]" in result


# ------------------------------------------------------------------ #
#  _build_model_config                                                 #
# ------------------------------------------------------------------ #


class TestBuildModelConfig:
    def _call(self, provider: str, model_name: str, param_mapping: dict | None = None) -> list:
        from langflow.services.memory_base.preprocessing import _build_model_config

        if param_mapping is None:
            param_mapping = {
                "api_key_param": "api_key",  # pragma: allowlist secret
                "model_class": "ChatOpenAI",
                "model_name_param": "model",
            }
        with patch(
            "langflow.services.memory_base.preprocessing.get_provider_param_mapping",
            return_value=param_mapping,
        ):
            return _build_model_config(provider, model_name)

    def test_returns_list_of_length_one(self):
        result = self._call("OpenAI", "gpt-4o-mini")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_icon_matches_provider(self):
        result = self._call("OpenAI", "gpt-4o-mini")
        assert result[0]["icon"] == "OpenAI"

    def test_name_matches_model_name(self):
        result = self._call("OpenAI", "gpt-4o-mini")
        assert result[0]["name"] == "gpt-4o-mini"

    def test_provider_field_set(self):
        result = self._call("OpenAI", "gpt-4o-mini")
        assert result[0]["provider"] == "OpenAI"

    def test_context_length_is_128000(self):
        result = self._call("OpenAI", "gpt-4o-mini")
        assert result[0]["metadata"]["context_length"] == 128000

    def test_api_key_param_from_mapping(self):
        mapping = {
            "api_key_param": "my_key",  # pragma: allowlist secret
            "model_class": "ChatOpenAI",
            "model_name_param": "model",
        }
        result = self._call("OpenAI", "gpt-4o", mapping)
        assert result[0]["metadata"]["api_key_param"] == "my_key"  # pragma: allowlist secret

    def test_model_class_from_mapping(self):
        mapping = {
            "api_key_param": "api_key",  # pragma: allowlist secret
            "model_class": "MyChatClass",
            "model_name_param": "model",
        }
        result = self._call("OpenAI", "gpt-4o", mapping)
        assert result[0]["metadata"]["model_class"] == "MyChatClass"

    def test_url_param_included_when_in_mapping(self):
        mapping = {
            "api_key_param": "api_key",  # pragma: allowlist secret
            "model_class": "ChatOpenAI",
            "model_name_param": "model",
            "url_param": "base_url",
        }
        result = self._call("OpenAI", "gpt-4o", mapping)
        assert result[0]["metadata"]["url_param"] == "base_url"

    def test_url_param_absent_when_not_in_mapping(self):
        result = self._call("OpenAI", "gpt-4o-mini")
        assert "url_param" not in result[0]["metadata"]

    def test_project_id_param_included_when_in_mapping(self):
        mapping = {
            "api_key_param": "api_key",  # pragma: allowlist secret
            "model_class": "ChatVertexAI",
            "model_name_param": "model",
            "project_id_param": "project",
        }
        result = self._call("VertexAI", "gemini-pro", mapping)
        assert result[0]["metadata"]["project_id_param"] == "project"

    def test_base_url_param_included_when_in_mapping(self):
        mapping = {
            "api_key_param": "api_key",  # pragma: allowlist secret
            "model_class": "ChatOpenAI",
            "model_name_param": "model",
            "base_url_param": "openai_api_base",
        }
        result = self._call("OpenAI", "gpt-4o", mapping)
        assert result[0]["metadata"]["base_url_param"] == "openai_api_base"


# ------------------------------------------------------------------ #
#  run_preprocessing                                                   #
# ------------------------------------------------------------------ #


class TestRunPreprocessing:
    """Tests for run_preprocessing — all external deps mocked."""

    def _mock_llm(self, response_text: str) -> MagicMock:
        mock_llm = MagicMock()
        mock_msg = MagicMock()
        mock_msg.text = response_text
        mock_llm.text_response = AsyncMock(return_value=mock_msg)
        return mock_llm

    def _standard_patches(self, mock_llm: MagicMock):
        return [
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake-key",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ]

    @pytest.mark.asyncio
    async def test_empty_messages_returns_skipped_without_llm_call(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        llm_cls = MagicMock()
        with patch(
            "langflow.services.memory_base.preprocessing.LanguageModelComponent",
            llm_cls,
        ):
            result = await run_preprocessing(
                messages=[],
                preproc_model="gpt-4o-mini",
                preproc_instructions="Summarize.",
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        assert result.status == "skipped"
        assert result.output_text == ""
        assert result.raw_response == ""
        llm_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_response_returns_ingested(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("This conversation is about Python async patterns.")
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            result = await run_preprocessing(
                messages=[_make_message(text="hello")],
                preproc_model="gpt-4o-mini",
                preproc_instructions="Summarize.",
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        assert result.status == "ingested"
        assert result.output_text == "This conversation is about Python async patterns."
        assert result.raw_response == "This conversation is about Python async patterns."

    @pytest.mark.asyncio
    async def test_kill_phrase_response_returns_skipped(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("NO_INGEST")
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            result = await run_preprocessing(
                messages=[_make_message(text="trivial chit-chat")],
                preproc_model="gpt-4o-mini",
                preproc_instructions="Summarize.",
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        assert result.status == "skipped"
        assert result.output_text == ""

    @pytest.mark.asyncio
    async def test_kill_phrase_raw_response_preserved(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("NO_INGEST")
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            result = await run_preprocessing(
                messages=[_make_message(text="trivial")],
                preproc_model="gpt-4o-mini",
                preproc_instructions=None,
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        assert result.raw_response == "NO_INGEST"

    @pytest.mark.asyncio
    async def test_kill_phrase_on_line_in_multiline_response_returns_skipped(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("Some preamble text\nNO_INGEST\nsome trailer")
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            result = await run_preprocessing(
                messages=[_make_message(text="chat")],
                preproc_model="gpt-4o-mini",
                preproc_instructions=None,
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        assert result.status == "skipped"

    @pytest.mark.asyncio
    async def test_infer_llm_provider_called_with_model_name(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("summary")
        infer_mock = MagicMock(return_value="OpenAI")
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                infer_mock,
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            await run_preprocessing(
                messages=[_make_message(text="hi")],
                preproc_model="gpt-4o-mini",
                preproc_instructions=None,
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        infer_mock.assert_called_once_with("gpt-4o-mini")

    @pytest.mark.asyncio
    async def test_api_key_fetched_for_resolved_provider(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("summary")
        key_mock = MagicMock(return_value="sk-real-key")
        user_id = uuid.uuid4()
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                key_mock,
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            await run_preprocessing(
                messages=[_make_message(text="hi")],
                preproc_model="gpt-4o-mini",
                preproc_instructions=None,
                kill_phrase="NO_INGEST",
                user_id=user_id,
            )

        key_mock.assert_called_once_with(user_id, "OpenAI")

    @pytest.mark.asyncio
    async def test_llm_set_called_with_batch_text_as_input_value(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("summary")
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            await run_preprocessing(
                messages=[_make_message(text="message content")],
                preproc_model="gpt-4o-mini",
                preproc_instructions=None,
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        call_kwargs = mock_llm.set.call_args.kwargs
        assert "input_value" in call_kwargs
        assert "message content" in call_kwargs["input_value"]

    @pytest.mark.asyncio
    async def test_system_message_includes_kill_phrase_suffix(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("summary")
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            await run_preprocessing(
                messages=[_make_message(text="hi")],
                preproc_model="gpt-4o-mini",
                preproc_instructions="Summarize the batch.",
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        call_kwargs = mock_llm.set.call_args.kwargs
        system_msg = call_kwargs.get("system_message", "")
        assert "NO_INGEST" in system_msg
        assert "Summarize the batch." in system_msg

    @pytest.mark.asyncio
    async def test_system_message_is_just_suffix_when_instructions_none(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("summary")
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            await run_preprocessing(
                messages=[_make_message(text="hi")],
                preproc_model="gpt-4o-mini",
                preproc_instructions=None,
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        call_kwargs = mock_llm.set.call_args.kwargs
        system_msg = call_kwargs.get("system_message", "")
        assert "NO_INGEST" in system_msg

    @pytest.mark.asyncio
    async def test_temperature_set_to_0_1(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = self._mock_llm("summary")
        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            await run_preprocessing(
                messages=[_make_message(text="hi")],
                preproc_model="gpt-4o-mini",
                preproc_instructions=None,
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        call_kwargs = mock_llm.set.call_args.kwargs
        assert call_kwargs.get("temperature") == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_message_text_none_falls_back_to_str(self):
        from langflow.services.memory_base.preprocessing import run_preprocessing

        mock_llm = MagicMock()
        mock_msg = MagicMock()
        mock_msg.text = None
        str_repr = "FallbackStringRepresentation"
        mock_msg.__str__ = MagicMock(return_value=str_repr)
        mock_llm.text_response = AsyncMock(return_value=mock_msg)

        with (
            patch(
                "langflow.services.memory_base.preprocessing.infer_llm_provider",
                return_value="OpenAI",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.get_api_key_for_provider",
                return_value="sk-fake",
            ),
            patch(
                "langflow.services.memory_base.preprocessing.LanguageModelComponent",
                return_value=mock_llm,
            ),
        ):
            result = await run_preprocessing(
                messages=[_make_message(text="hi")],
                preproc_model="gpt-4o-mini",
                preproc_instructions=None,
                kill_phrase="NO_INGEST",
                user_id=uuid.uuid4(),
            )

        assert result.output_text == str_repr
        assert result.raw_response == str_repr

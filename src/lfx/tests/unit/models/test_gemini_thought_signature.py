"""Tests for Gemini 3.0 thought signature injection.

Gemini 3.0 models require a thought_signature on functionCall parts in
conversation history. The installed google-ai-generativelanguage proto
schema (0.6.15) doesn't include this field, so ChatGoogleGenerativeAIFixed
injects it as raw protobuf bytes using Google's approved dummy value.

See: https://ai.google.dev/gemini-api/docs/thought-signatures
"""

import pytest

# Skip all tests if Google proto packages aren't installed (e.g. in isolated lfx env)
pytest.importorskip("google.ai.generativelanguage_v1beta", reason="google-ai-generativelanguage not installed")
pytest.importorskip("langchain_google_genai", reason="langchain-google-genai not installed")

from google.ai.generativelanguage_v1beta.types import Content, FunctionCall, FunctionResponse, GenerateContentRequest, Part

from lfx.base.models.google_generative_ai_model import (
    _DUMMY_THOUGHT_SIGNATURE,
    _THOUGHT_SIG_PROTO_BYTES,
    _is_gemini_3_model,
)
from lfx.base.models.google_generative_ai_model import (
    _DUMMY_THOUGHT_SIGNATURE,
    _THOUGHT_SIG_PROTO_BYTES,
    _is_gemini_3_model,
)


class TestIsGemini3Model:
    """Test model name detection for Gemini 3.0+ models."""

    @pytest.mark.parametrize(
        "model_name",
        [
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-3-pro-image-preview",
            "gemini-3.1-pro-preview",
            "models/gemini-3-pro-preview",
            "models/gemini-3.1-pro-preview",
        ],
    )
    def test_gemini_3_models_detected(self, model_name):
        assert _is_gemini_3_model(model_name) is True

    @pytest.mark.parametrize(
        "model_name",
        [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "models/gemini-2.5-flash",
            "gpt-4o",
        ],
    )
    def test_non_gemini_3_models_not_detected(self, model_name):
        assert _is_gemini_3_model(model_name) is False


class TestThoughtSignatureProtoEncoding:
    """Test that the protobuf encoding for thought_signature is correct."""

    def test_proto_bytes_length(self):
        # Tag (1 byte) + length varint (1 byte) + value (32 bytes) = 34 bytes
        assert len(_THOUGHT_SIG_PROTO_BYTES) == 34

    def test_proto_bytes_tag(self):
        # Field 13, wire type 2: (13 << 3) | 2 = 106 = 0x6A
        assert _THOUGHT_SIG_PROTO_BYTES[0] == 0x6A

    def test_proto_bytes_length_prefix(self):
        # Length of "skip_thought_signature_validator" = 32 = 0x20
        assert _THOUGHT_SIG_PROTO_BYTES[1] == 0x20

    def test_proto_bytes_value(self):
        assert _THOUGHT_SIG_PROTO_BYTES[2:] == _DUMMY_THOUGHT_SIGNATURE


class TestInjectThoughtSignatures:
    """Test that thought signatures are correctly injected into request protos."""

    def _make_request_with_tool_call(self, model="models/gemini-3-pro-preview"):
        """Create a GenerateContentRequest with a model function call in history."""
        return GenerateContentRequest(
            model=model,
            contents=[
                Content(role="user", parts=[Part(text="What is the weather?")]),
                Content(
                    role="model",
                    parts=[Part(function_call=FunctionCall(name="get_weather", args={"city": "Paris"}))],
                ),
                Content(
                    role="user",
                    parts=[
                        Part(
                            function_response=FunctionResponse(
                                name="get_weather", response={"temperature": "20C"}
                            )
                        )
                    ],
                ),
            ],
        )

    def test_signature_injected_into_function_call_part(self):
        """Thought signature bytes should be present in serialized function call Part."""
        from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed

        request = self._make_request_with_tool_call()
        ChatGoogleGenerativeAIFixed._inject_thought_signatures(request)

        # Check the model content's function call part has the signature bytes
        model_content = request._pb.contents[1]
        fc_part = model_content.parts[0]
        serialized = fc_part.SerializeToString()
        assert _THOUGHT_SIG_PROTO_BYTES in serialized

    def test_function_call_preserved_after_injection(self):
        """The function_call data should remain intact after injection."""
        from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed

        request = self._make_request_with_tool_call()
        ChatGoogleGenerativeAIFixed._inject_thought_signatures(request)

        model_content = request._pb.contents[1]
        fc_part = model_content.parts[0]
        assert fc_part.function_call.name == "get_weather"

    def test_user_parts_not_modified(self):
        """User content parts should not be modified."""
        from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed

        request = self._make_request_with_tool_call()

        # Capture user part bytes before injection
        user_part_before = request._pb.contents[0].parts[0].SerializeToString()

        ChatGoogleGenerativeAIFixed._inject_thought_signatures(request)

        # User part should be unchanged
        user_part_after = request._pb.contents[0].parts[0].SerializeToString()
        assert user_part_before == user_part_after

    def test_no_function_call_no_injection(self):
        """When there are no function calls, nothing should be injected."""
        from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed

        request = GenerateContentRequest(
            model="models/gemini-3-pro-preview",
            contents=[
                Content(role="user", parts=[Part(text="Hello")]),
                Content(role="model", parts=[Part(text="Hi there!")]),
            ],
        )

        # Capture bytes before
        model_part_before = request._pb.contents[1].parts[0].SerializeToString()

        ChatGoogleGenerativeAIFixed._inject_thought_signatures(request)

        # Model text part should be unchanged
        model_part_after = request._pb.contents[1].parts[0].SerializeToString()
        assert model_part_before == model_part_after

    def test_parallel_function_calls_only_first_gets_signature(self):
        """For parallel function calls, only the first should get a signature."""
        from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed

        request = GenerateContentRequest(
            model="models/gemini-3-pro-preview",
            contents=[
                Content(role="user", parts=[Part(text="Check weather in Paris and London")]),
                Content(
                    role="model",
                    parts=[
                        Part(function_call=FunctionCall(name="get_weather", args={"city": "Paris"})),
                        Part(function_call=FunctionCall(name="get_weather", args={"city": "London"})),
                    ],
                ),
            ],
        )

        ChatGoogleGenerativeAIFixed._inject_thought_signatures(request)

        model_content = request._pb.contents[1]

        # First FC part should have signature
        first_fc_bytes = model_content.parts[0].SerializeToString()
        assert _THOUGHT_SIG_PROTO_BYTES in first_fc_bytes

        # Second FC part should NOT have signature
        second_fc_bytes = model_content.parts[1].SerializeToString()
        assert _THOUGHT_SIG_PROTO_BYTES not in second_fc_bytes

    def test_sequential_function_calls_each_model_turn_gets_signature(self):
        """For sequential (multi-step) calls, each model turn's first FC gets a signature."""
        from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed

        request = GenerateContentRequest(
            model="models/gemini-3-pro-preview",
            contents=[
                Content(role="user", parts=[Part(text="Check flight and book taxi")]),
                # Step 1: model calls check_flight
                Content(
                    role="model",
                    parts=[Part(function_call=FunctionCall(name="check_flight", args={"flight": "AA100"}))],
                ),
                Content(
                    role="user",
                    parts=[
                        Part(
                            function_response=FunctionResponse(
                                name="check_flight", response={"status": "delayed"}
                            )
                        )
                    ],
                ),
                # Step 2: model calls book_taxi
                Content(
                    role="model",
                    parts=[Part(function_call=FunctionCall(name="book_taxi", args={"time": "10AM"}))],
                ),
                Content(
                    role="user",
                    parts=[
                        Part(
                            function_response=FunctionResponse(
                                name="book_taxi", response={"status": "confirmed"}
                            )
                        )
                    ],
                ),
            ],
        )

        ChatGoogleGenerativeAIFixed._inject_thought_signatures(request)

        # Both model turns should have signatures on their FC parts
        step1_fc = request._pb.contents[1].parts[0].SerializeToString()
        assert _THOUGHT_SIG_PROTO_BYTES in step1_fc

        step2_fc = request._pb.contents[3].parts[0].SerializeToString()
        assert _THOUGHT_SIG_PROTO_BYTES in step2_fc

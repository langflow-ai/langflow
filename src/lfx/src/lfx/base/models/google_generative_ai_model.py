from langchain_google_genai import ChatGoogleGenerativeAI

# Dummy thought signature to skip validation for Gemini 3.0+ models.
# Gemini 3 requires thought_signature on function call parts when passing
# conversation history back. The installed google-ai-generativelanguage (0.6.15)
# doesn't include this field in its proto schema (field 13 on Part), so we
# inject it as raw protobuf bytes using Google's approved dummy value.
# See: https://ai.google.dev/gemini-api/docs/thought-signatures
_DUMMY_THOUGHT_SIGNATURE = b"skip_thought_signature_validator"

# Protobuf wire encoding for thought_signature field:
# Field 13, wire type 2 (length-delimited/bytes)
# Tag: (13 << 3) | 2 = 106 = 0x6A
_THOUGHT_SIG_PROTO_BYTES = bytes([0x6A, len(_DUMMY_THOUGHT_SIGNATURE)]) + _DUMMY_THOUGHT_SIGNATURE


def _is_gemini_3_model(model_name: str) -> bool:
    """Check if the model is a Gemini 3.0+ model that requires thought signatures."""
    name = model_name.replace("models/", "")
    return name.startswith("gemini-3")


class ChatGoogleGenerativeAIFixed(ChatGoogleGenerativeAI):
    """Custom ChatGoogleGenerativeAI that fixes.

    1. Empty function response names in ToolMessage and FunctionMessage
    2. Missing thought_signature for Gemini 3.0+ models during function calling
    """

    def __init__(self, *args, **kwargs):
        """Initialize with fix for empty function response names in ToolMessage and FunctionMessage."""
        if ChatGoogleGenerativeAI is None:
            msg = "The 'langchain_google_genai' package is required to use the Google Generative AI model."
            raise ImportError(msg)

        # Initialize the parent class
        super().__init__(*args, **kwargs)

    def _prepare_request(self, messages, **kwargs):
        """Override request preparation to fix empty function response names.

        and inject thought signatures for Gemini 3.0+ models.
        """
        from langchain_core.messages import FunctionMessage, ToolMessage

        # Pre-process messages to ensure tool/function messages have names
        fixed_messages = []
        for message in messages:
            fixed_message = message
            if isinstance(message, ToolMessage) and not message.name:
                # Create a new ToolMessage with a default name
                fixed_message = ToolMessage(
                    content=message.content,
                    name="tool_response",
                    tool_call_id=getattr(message, "tool_call_id", None),
                    artifact=getattr(message, "artifact", None),
                )
            elif isinstance(message, FunctionMessage) and not message.name:
                # Create a new FunctionMessage with a default name
                fixed_message = FunctionMessage(content=message.content, name="function_response")
            fixed_messages.append(fixed_message)

        # Call the parent's method with fixed messages
        request = super()._prepare_request(fixed_messages, **kwargs)

        # Inject thought signatures for Gemini 3.0+ models
        if _is_gemini_3_model(self.model):
            self._inject_thought_signatures(request)

        return request

    @staticmethod
    def _inject_thought_signatures(request):
        """Inject dummy thought signatures into function call parts for Gemini 3.0+.

        Gemini 3.0 models require a thought_signature on function call parts when
        passing conversation history back. The installed proto schema doesn't support
        this field, so we inject it as raw protobuf bytes (unknown field 13) using
        Google's approved dummy value to skip signature validation.

        Per Google docs, only the first functionCall part in each model response
        needs a signature (covers both sequential and parallel function calls).

        Reference: https://ai.google.dev/gemini-api/docs/thought-signatures
        """
        for content_pb in request._pb.contents:  # noqa: SLF001
            if content_pb.role == "model":
                for part_pb in content_pb.parts:
                    if part_pb.HasField("function_call"):
                        # Inject thought_signature as raw protobuf bytes.
                        # The unknown field 13 will be preserved through
                        # serialization and sent to the API.
                        part_pb.MergeFromString(_THOUGHT_SIG_PROTO_BYTES)
                        # Only the first FC part per model response needs a
                        # signature; subsequent parallel FCs don't require one.
                        break

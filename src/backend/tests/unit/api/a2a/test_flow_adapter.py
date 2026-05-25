"""Unit tests for the A2A flow adapter (translation layer).

Tests the bidirectional translation between A2A protocol objects
and Langflow flow execution inputs/outputs.

Inbound (A2A → Langflow):
- Text parts become input_value
- Data parts become tweaks
- contextId maps to session_id via HMAC

Outbound (Langflow → A2A):
- Text results become Artifacts with text parts
- Structured results become Artifacts with data parts

These are pure logic tests — no database, no HTTP, no flow execution.
"""

import json

import pytest
from langflow.api.a2a.flow_adapter import translate_inbound, translate_outbound

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Inbound translation: A2A Message → Langflow flow inputs
# ---------------------------------------------------------------------------


class TestTranslateInbound:
    """Tests for translating A2A messages into Langflow execution inputs.

    The adapter must extract the right parts from the A2A message and
    map them to the parameters that simple_run_flow() expects.
    """

    async def test_text_part_becomes_input_value(self):
        """The first text part in the message becomes the flow's input_value.

        This is the primary input mechanism — a text message from the
        calling agent becomes the chat input to the Langflow flow.
        """
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": "What are the security vulnerabilities?"}],
        }
        result = await translate_inbound(message, flow_secret="test-secret")

        assert result["input_value"] == "What are the security vulnerabilities?"

    async def test_multiple_text_parts_concatenated(self):
        """When a message has multiple text parts, they are concatenated.

        Some A2A clients split long messages into multiple parts.
        """
        message = {
            "role": "user",
            "parts": [
                {"kind": "text", "text": "First part."},
                {"kind": "text", "text": " Second part."},
            ],
        }
        result = await translate_inbound(message, flow_secret="test-secret")
        assert result["input_value"] == "First part. Second part."

    async def test_data_part_becomes_tweaks(self):
        """A data part in the message is extracted as flow tweaks.

        This lets callers pass structured configuration alongside
        the text input — e.g., model parameters, feature flags.
        """
        message = {
            "role": "user",
            "parts": [
                {"kind": "text", "text": "Analyze this"},
                {"kind": "data", "data": {"temperature": 0.5, "max_tokens": 100}},
            ],
        }
        result = await translate_inbound(message, flow_secret="test-secret")

        assert result["input_value"] == "Analyze this"
        assert result["tweaks"] == {"temperature": 0.5, "max_tokens": 100}

    async def test_context_id_maps_to_session_id(self):
        """ContextId from the A2A message maps to a Langflow session_id.

        The mapping uses HMAC to prevent session ID guessing between
        different callers. Same contextId + same secret = same session.
        """
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": "Hello"}],
            "contextId": "ctx-abc-123",
        }
        result = await translate_inbound(message, flow_secret="test-secret")

        assert result["session_id"] is not None
        assert result["session_id"].startswith("a2a-")

    async def test_same_context_id_produces_same_session_id(self):
        """Deterministic mapping: same contextId always produces same session.

        This is critical for multi-turn conversations — Turn 2 must
        land in the same session as Turn 1.
        """
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": "Hello"}],
            "contextId": "ctx-abc-123",
        }
        result1 = await translate_inbound(message, flow_secret="test-secret")
        result2 = await translate_inbound(message, flow_secret="test-secret")

        assert result1["session_id"] == result2["session_id"]

    async def test_different_secrets_produce_different_sessions(self):
        """Different flow secrets produce different session IDs.

        This prevents cross-tenant session hijacking — a caller who
        knows a contextId from one flow can't use it to access
        another flow's session.
        """
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": "Hello"}],
            "contextId": "ctx-abc-123",
        }
        result1 = await translate_inbound(message, flow_secret="secret-1")
        result2 = await translate_inbound(message, flow_secret="secret-2")

        assert result1["session_id"] != result2["session_id"]

    async def test_missing_context_id_generates_unique_session(self):
        """When no contextId is provided, a unique session is generated.

        This is the single-turn case — each message gets its own session.
        """
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": "Hello"}],
        }
        result = await translate_inbound(message, flow_secret="test-secret")

        assert result["session_id"] is not None
        assert result["session_id"].startswith("a2a-")

    async def test_empty_message_parts(self):
        """A message with no parts produces an empty input_value."""
        message = {
            "role": "user",
            "parts": [],
        }
        result = await translate_inbound(message, flow_secret="test-secret")
        assert result["input_value"] == ""

    async def test_default_input_and_output_types(self):
        """The adapter always sets input_type='chat' and output_type='chat'."""
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": "Hello"}],
        }
        result = await translate_inbound(message, flow_secret="test-secret")
        assert result["input_type"] == "chat"
        assert result["output_type"] == "chat"


# ---------------------------------------------------------------------------
# Outbound translation: Langflow results → A2A Artifacts
# ---------------------------------------------------------------------------


class TestTranslateOutbound:
    """Tests for translating Langflow execution results into A2A Artifacts.

    The adapter converts the list of RunOutputs from flow execution
    into A2A Artifact objects with the appropriate Part types.
    """

    async def test_text_result_becomes_text_artifact(self):
        """A text message from the flow becomes an Artifact with a text Part.

        This is the most common case — the agent produces a text response.
        """
        run_outputs = [_make_run_output(message_text="Here is your analysis of the codebase.")]
        artifacts = await translate_outbound(run_outputs)

        assert len(artifacts) == 1
        assert artifacts[0]["parts"][0]["kind"] == "text"
        assert artifacts[0]["parts"][0]["text"] == "Here is your analysis of the codebase."

    async def test_structured_result_becomes_data_artifact(self):
        """When the flow returns structured data (dict), it becomes a data Part."""
        run_outputs = [_make_run_output(result_data={"score": 0.95, "labels": ["positive"]})]
        artifacts = await translate_outbound(run_outputs)

        assert len(artifacts) == 1
        assert artifacts[0]["parts"][0]["kind"] == "data"
        assert artifacts[0]["parts"][0]["data"] == {"score": 0.95, "labels": ["positive"]}

    async def test_empty_outputs_produces_empty_artifacts(self):
        """When the flow produces no output, no artifacts are created."""
        artifacts = await translate_outbound([])
        assert artifacts == []

    async def test_multiple_outputs_become_multiple_artifacts(self):
        """Each flow output vertex produces a separate artifact."""
        run_outputs = [
            _make_run_output(message_text="First result"),
            _make_run_output(message_text="Second result"),
        ]
        artifacts = await translate_outbound(run_outputs)
        assert len(artifacts) == 2

    async def test_artifact_has_name_and_description(self):
        """Each artifact has metadata fields for identification."""
        run_outputs = [_make_run_output(message_text="Result")]
        artifacts = await translate_outbound(run_outputs)

        assert "name" in artifacts[0]
        assert "artifactId" in artifacts[0]

    async def test_result_embedding_raw_message_is_json_serializable(self):
        """A result embedding a raw Message still yields a JSON-serializable artifact.

        Regression: an empty-text Message nested under ``message`` fell through
        to the data fallback and was emitted verbatim, so persisting the task
        raised a DB serialization error whose raw text leaked to the A2A caller.
        The fallback now coerces to a JSON-safe structure.
        """
        from lfx.schema.message import Message

        # Exactly the shape that broke task persistence: a dict whose value is
        # a non-JSON Message with empty text (so the text branch is skipped).
        run_output = {"outputs": [{"results": {"message": Message(text="")}}]}
        artifacts = await translate_outbound([run_output])

        # Whatever shape it takes, the artifact must serialize cleanly.
        json.dumps(artifacts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_output(
    *,
    message_text: str | None = None,
    result_data: dict | None = None,
) -> dict:
    """Create a minimal RunOutputs-like dict for testing.

    Mimics the structure returned by simple_run_flow().outputs[].
    The actual RunOutputs has nested ResultData, but the adapter
    should handle this simplified structure.
    """
    outputs = []
    if message_text is not None:
        outputs.append(
            {
                "results": {"message": {"text": message_text}},
                "messages": [{"message": message_text}],
            }
        )
    if result_data is not None:
        outputs.append(
            {
                "results": {"data": result_data},
            }
        )
    return {
        "inputs": {},
        "outputs": outputs,
    }

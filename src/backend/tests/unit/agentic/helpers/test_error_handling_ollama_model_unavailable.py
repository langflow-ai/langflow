"""Ollama 404 ``model not found`` must trigger the assistant model fallback.

Reproduced live (2026-06-12, release-1.11.0, Ollama-only setup): the
assistant default-resolves a catalog model that is not installed locally
(``llama3.3``) and Ollama raises ``model 'llama3.3' not found (status
code: 404)``. ``is_model_unavailable_error`` does not match that phrasing,
so the fallback chain never fires and the user gets a terminal
``Model not available`` error on the first attempt.
"""

from langflow.agentic.helpers.error_handling import is_model_unavailable_error

OLLAMA_MODEL_NOT_FOUND_ERROR = "Error building Component Language Model: model 'llama3.3' not found (status code: 404)."


class TestOllamaModelUnavailableDetection:
    def test_should_flag_model_unavailable_when_ollama_returns_model_not_found_404(self):
        assert is_model_unavailable_error(OLLAMA_MODEL_NOT_FOUND_ERROR) is True

    def test_should_flag_model_unavailable_for_any_model_name_in_ollama_404(self):
        error = "model 'qwen2.5' not found (status code: 404)."

        assert is_model_unavailable_error(error) is True

    def test_should_flag_model_unavailable_when_ollama_cloud_model_requires_subscription(self):
        error = (
            "this model requires a subscription, upgrade for access: https://ollama.com/upgrade "
            "(ref: 0fce2689-75e7-45af-9636-ac7a1ff2dd38) (status code: 403)."
        )

        assert is_model_unavailable_error(error) is True

    def test_should_not_flag_wrong_base_url_404_as_model_unavailable(self):
        error = "404 page not found"

        assert is_model_unavailable_error(error) is False

    def test_should_not_flag_auth_errors_as_model_unavailable(self):
        error = "Error code: 401 - Incorrect API key provided"

        assert is_model_unavailable_error(error) is False


class TestRecursionLimitFriendlyError:
    """The colon-split truncation surfaced the URL tail to the user (2026-06-12)."""

    RECURSION_ERROR = (
        "Error building Component Agent: \n\nRecursion limit of 35 reached without hitting a stop "
        "condition. You can increase the limit by setting the `recursion_limit` config key.\n"
        "For troubleshooting, visit: https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT."
    )

    def test_should_return_clear_message_when_agent_hits_recursion_limit(self):
        from langflow.agentic.helpers.error_handling import extract_friendly_error

        message = extract_friendly_error(self.RECURSION_ERROR)

        assert "//docs.langchain" not in message, f"URL fragment leaked to the user: {message!r}"
        assert "step" in message.lower() or "iteration" in message.lower(), (
            f"Message must explain the agent ran out of steps, got: {message!r}"
        )


class TestMalformedToolCallFriendlyError:
    """gpt-oss leaks reasoning into the tool-call channel; a retry usually fixes it (2026-06-12)."""

    MALFORMED_TOOL_CALL_ERROR = (
        "Error building Component Agent: \n\nerror parsing tool call: "
        'raw=\'We need create flow with 5 random components...{"query":"Random"}\', '
        "err=invalid character 'W' looking for beginning of value (status code: 500)."
    )

    def test_should_explain_malformed_tool_call_instead_of_generic_server_error(self):
        from langflow.agentic.helpers.error_handling import extract_friendly_error

        message = extract_friendly_error(self.MALFORMED_TOOL_CALL_ERROR)

        assert "server error" not in message.lower(), f"Too generic: {message!r}"
        assert "tool call" in message.lower() or "again" in message.lower(), (
            f"Message must say a retry usually fixes a malformed tool call, got: {message!r}"
        )

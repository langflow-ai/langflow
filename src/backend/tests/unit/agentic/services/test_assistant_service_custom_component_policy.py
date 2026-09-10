"""A component request on a server that forbids custom components stops before the model.

LE-2322. The assistant used to generate code, refuse it, feed the refusal back as if it were
a compiler error, and try again -- four times, 78 seconds and 552.1K tokens in the reported
run -- before telling the user "the selected model was unable to generate valid component
code". Every part of that is wrong: nothing was retried that could have succeeded, and the
model was blamed for a decision the operator made.

``validate_component_runtime`` refuses before instantiating anything whenever
``allow_custom_components`` is false, so the outcome is knowable the moment the intent is
classified. These tests pin the refusal to that point, before the first LLM call.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.agentic.helpers.validation import CUSTOM_COMPONENTS_DISABLED_MESSAGE
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import IntentResult
from lfx.services.deps import get_settings_service

MODULE = "langflow.agentic.services.assistant_service"

GENERATED_COMPONENT_RESPONSE = """Here is the component:

```python
from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema import Data


class WordCountComponent(Component):
    display_name = "Word Count"
    description = "Counts words in a text input"
    icon = "Sparkles"

    inputs = [MessageTextInput(name="text", display_name="Text")]
    outputs = [Output(name="result", display_name="Result", method="build_result")]

    def build_result(self) -> Data:
        return Data(data={"count": len((self.text or "").split())})
```
"""


@pytest.fixture
def custom_components(request):
    """Set ``allow_custom_components`` for one test and restore it afterwards."""
    settings = get_settings_service().settings
    saved = settings.allow_custom_components
    settings.allow_custom_components = request.param
    try:
        yield request.param
    finally:
        settings.allow_custom_components = saved


def _complete_payload(events: list[str]) -> dict | None:
    for event_str in reversed(events):
        for line in event_str.strip().split("\n"):
            if not line.startswith("data: "):
                continue
            parsed = json.loads(line[6:])
            if parsed.get("event") == "complete":
                return parsed.get("data", parsed)
    return None


async def _run(input_value: str = "Create a component that counts words in a text input"):
    """Drive the streaming assistant with a ``generate_component`` intent.

    ``execute_flow_file_streaming`` is replaced with a MagicMock returning a real async
    generator, so a test that expects the model to be reached gets a usable stream and one
    that expects a refusal can still assert the call never happened.
    """

    # Real component code, so that WITHOUT the gate the run reaches extraction, validation,
    # the policy refusal and the retry loop -- the behavior these tests exist to rule out.
    async def _stream():
        yield "end", {"result": GENERATED_COMPONENT_RESPONSE}

    mock_flow = MagicMock(side_effect=lambda *_args, **_kwargs: _stream())
    with (
        patch(
            f"{MODULE}.classify_intent",
            AsyncMock(return_value=IntentResult(intent="generate_component", translation=input_value)),
        ),
        patch(f"{MODULE}.execute_flow_file_streaming", mock_flow),
    ):
        events = [
            event
            async for event in execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value=input_value,
                global_variables={},
            )
        ]
    return events, mock_flow


@pytest.mark.parametrize("custom_components", [False], indirect=True)
@pytest.mark.usefixtures("custom_components")
class TestComponentRequestRefusedByPolicy:
    async def test_refuses_before_calling_the_model(self):
        """The expensive half never runs: no generation, so no retries to spend."""
        _events, mock_flow = await _run()
        mock_flow.assert_not_called()

    async def test_answers_with_the_policy_message(self):
        events, _ = await _run()
        payload = _complete_payload(events)
        assert payload is not None
        assert payload.get("result") == CUSTOM_COMPONENTS_DISABLED_MESSAGE

    async def test_does_not_report_a_validation_failure(self):
        """No ``validated``/``validation_error`` keeps the UI off its model-blaming card.

        ``assistant-validation-failed.tsx`` renders "The selected model was unable to
        generate valid component code" whenever ``validated`` is false and
        ``validationError`` is set. A policy decision must not reach the user that way.
        """
        events, _ = await _run()
        payload = _complete_payload(events)
        assert payload is not None
        assert "validated" not in payload
        assert "validation_error" not in payload

    async def test_makes_exactly_one_attempt(self):
        """The reported run reached "Attempt 4 of 4"; a settled refusal gets one."""
        events, _ = await _run()
        attempts = [
            json.loads(line[6:]).get("attempt")
            for event_str in events
            for line in event_str.strip().split("\n")
            if line.startswith("data: ") and json.loads(line[6:]).get("event") == "progress"
        ]
        assert all(a in (None, 1) for a in attempts), f"policy refusal emitted retry attempts: {attempts}"

    async def test_refusal_addresses_the_user_not_the_operator(self):
        """LE-2322 finding 1: the setting name belongs in the log, not the chat."""
        events, _ = await _run()
        payload = _complete_payload(events)
        message = payload.get("result")
        assert "allow_custom_components" not in message
        assert "LANGFLOW_" not in message
        assert "administrator" in message


@pytest.mark.parametrize("custom_components", [True], indirect=True)
@pytest.mark.usefixtures("custom_components")
class TestComponentRequestProceedsWhenAllowed:
    async def test_default_deployment_still_generates(self):
        """The gate must not swallow component requests on an ordinary server."""
        _events, mock_flow = await _run()
        mock_flow.assert_called_once()

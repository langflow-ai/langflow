"""Flow execution types and constants."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Base path for flow files (JSON and Python)
FLOWS_BASE_PATH = Path(__file__).parent.parent / "flows"

# Streaming configuration
STREAMING_QUEUE_MAX_SIZE = 1000
STREAMING_EVENT_TIMEOUT_SECONDS = 300.0

# Assistant configuration
MAX_VALIDATION_RETRIES = 3
VALIDATION_UI_DELAY_SECONDS = 0.3
LANGFLOW_ASSISTANT_FLOW = "LangflowAssistant.json"
TRANSLATION_FLOW = "translation_flow.py"

OFF_TOPIC_REFUSAL_MESSAGE = (
    "I appreciate your interest, but I'm the Langflow Assistant and can only help with "
    "Langflow-related topics such as building components, creating flows, configuring "
    "deployments, and troubleshooting issues. Could you rephrase your question about Langflow?"
)

VALIDATION_RETRY_TEMPLATE = """The previous component code has an error. Please fix it.

ERROR:
{error}

BROKEN CODE:
```python
{code}
```

Please provide a corrected version of the component code."""


@dataclass
class IntentResult:
    """Result from intent classification flow."""

    translation: str
    intent: str  # "generate_component", "question", or "off_topic"


@dataclass
class FlowExecutionResult:
    """Holds the result or error from async flow execution."""

    result: dict[str, Any] = field(default_factory=dict)
    error: Exception | None = None

    @property
    def has_error(self) -> bool:
        return self.error is not None

    @property
    def has_result(self) -> bool:
        return bool(self.result)

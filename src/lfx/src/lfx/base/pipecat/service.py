"""Base class for Pipecat Service components (STT / LLM / TTS / S2S).

Concrete subclasses live under ``lfx/components/pipecat_services/`` and implement
``build_service()`` to return the live Pipecat service object (e.g.
``DeepgramSTTService``, ``OpenAILLMService``, ``ElevenLabsTTSService``,
``GeminiLiveLLMService``).
"""

from abc import abstractmethod
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import InputTypes
from lfx.io import HandleInput, SecretStrInput


class PipecatServiceComponent(Component):
    """Base for STT / LLM / TTS / S2S service components.

    Subclasses declare:
      - inputs (provider-specific config + api key)
      - outputs (one Output of the matching Pipecat type, method="build_service")
      - implement ``build_service()``
    """

    trace_type = "pipecat_service"
    category = "pipecat"

    # Provider-specific subclasses extend this list with model/voice/etc inputs.
    _base_inputs: list[InputTypes] = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Provider API key. May be optional for local/self-hosted services.",
            required=False,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["PipecatTool"],
            is_list=True,
            required=False,
            info="Optional list of VoiceTool outputs to register on this service.",
        ),
    ]

    def _register_tools(self, service: Any) -> None:
        """Register any connected (FunctionSchema, handler) tools on the service.

        Pipecat LLM/S2S services expose ``register_function(name, handler, ...)``.
        STT / TTS services do not, so subclasses that don't accept tools should
        either remove ``tools`` from their inputs or skip calling this helper.
        """
        tools = getattr(self, "tools", None) or []
        register = getattr(service, "register_function", None)
        if not tools or register is None:
            return
        for schema, handler in tools:
            register(schema.name, handler)

    @abstractmethod
    def build_service(self) -> Any:
        """Build and return the live Pipecat service object."""

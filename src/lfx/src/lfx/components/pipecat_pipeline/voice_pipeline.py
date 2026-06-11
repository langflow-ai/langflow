"""VoicePipelineComponent — the terminal node of every voice graph.

Direct parallel of ``AgentComponent.build_agent()`` returning an
``AgentExecutor``. Instead it returns a ``PipelineTask`` that the API runner
hands to ``PipelineRunner.run()``.

Wiring expected upstream:
  - ``transport``: one transport component (FastAPI WS / Exotel / Twilio).
  - ``processors``: ordered list of frame processors that sit between
    ``transport.input()`` and ``transport.output()``. Typical order for a
    Deepgram+OpenAI+ElevenLabs stack:
        [stt, user_aggregator, llm, assistant_aggregator, tts, mic_gate]
    For a Gemini Live S2S stack:
        [user_aggregator, gemini_live, assistant_aggregator, mic_gate]
  - ``llm`` (optional): the LLM/S2S service used for late tool registration.
  - ``tools`` (optional): any ``PipecatTool`` outputs to register on the LLM
    that weren't wired directly into the service component.
"""

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.field_typing.voice_types import PipecatPipelineTask
from lfx.io import BoolInput, HandleInput, IntInput, Output


class VoicePipelineComponent(Component):
    display_name = "Voice Pipeline"
    description = "Assembles connected Pipecat services into a runnable PipelineTask."
    icon = "AudioWaveform"
    name = "VoicePipeline"
    category = "pipecat"

    inputs = [
        HandleInput(
            name="transport",
            display_name="Transport",
            input_types=["PipecatTransport"],
            required=True,
        ),
        HandleInput(
            name="processors",
            display_name="Processors",
            input_types=["PipecatFrameProcessor"],
            is_list=True,
            required=True,
            info=(
                "Ordered list of frame processors that sit between transport.input() "
                "and transport.output(). Edge-arrival order determines pipeline order."
            ),
        ),
        HandleInput(
            name="llm",
            display_name="LLM / S2S Service",
            input_types=["PipecatLLMService", "PipecatS2SService"],
            required=False,
            info=(
                "Optional. Wire the LLM here if you want the pipeline component to "
                "register late-bound tools on it. Already wired on a service "
                "component? No need to repeat — just leave this empty."
            ),
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["PipecatTool"],
            is_list=True,
            required=False,
            info=(
                "Optional VoiceTool outputs to register on `llm` at task-build time. "
                "Use this when a tool was not wired directly into the LLM service "
                "component's `tools` input."
            ),
        ),
        BoolInput(
            name="enable_metrics",
            display_name="Enable Metrics",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="enable_usage_metrics",
            display_name="Enable Usage Metrics",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="audio_in_sample_rate",
            display_name="Input Sample Rate",
            value=16000,
            advanced=True,
            info="Should match the transport's input sample rate.",
        ),
        IntInput(
            name="audio_out_sample_rate",
            display_name="Output Sample Rate",
            value=16000,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Pipeline Task",
            name="task",
            method="build_task",
            types=["PipecatPipelineTask"],
        ),
    ]

    def _register_late_tools(self, llm: Any, tools: list[Any]) -> None:
        """Register any (schema, handler) tuples on the LLM, skipping duplicates."""
        if not llm or not tools:
            return
        register = getattr(llm, "register_function", None)
        if register is None:
            return
        # pipecat services keep a private registry; introspect to skip dupes if possible.
        existing = getattr(llm, "_function_handlers", None) or getattr(llm, "_functions", None)
        existing_names = set(existing.keys()) if isinstance(existing, dict) else set()
        for schema, handler in tools:
            if schema.name in existing_names:
                continue
            register(schema.name, handler)
            existing_names.add(schema.name)

    def build_task(self) -> PipecatPipelineTask:
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.task import PipelineParams, PipelineTask

        transport = self.transport
        processors = list(self.processors or [])
        if not processors:
            msg = "VoicePipeline requires at least one processor between transport.input() and transport.output()."
            raise ValueError(msg)

        self._register_late_tools(self.llm, list(self.tools or []))

        pipeline = Pipeline(
            [
                transport.input(),
                *processors,
                transport.output(),
            ]
        )
        params = PipelineParams(
            enable_metrics=bool(self.enable_metrics),
            enable_usage_metrics=bool(self.enable_usage_metrics),
            audio_in_sample_rate=int(self.audio_in_sample_rate),
            audio_out_sample_rate=int(self.audio_out_sample_rate),
        )
        return PipelineTask(pipeline, params=params)

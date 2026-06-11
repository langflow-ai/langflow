"""LLM Context Aggregator Pair component.

Outputs a paired (user, assistant) aggregator that wraps an ``LLMContext``.
The user aggregator goes between STT and LLM; the assistant aggregator goes
after the TTS output (so its text matches what was actually spoken).
"""

from lfx.custom.custom_component.component import Component
from lfx.field_typing.voice_types import PipecatContextAggregatorPair, PipecatFrameProcessor
from lfx.io import HandleInput, Output


class LLMContextAggregatorPairComponent(Component):
    display_name = "LLM Context Aggregator Pair"
    description = "Builds the user/assistant context aggregators around an LLMContext."
    icon = "GitBranch"
    name = "LLMContextAggregatorPair"
    category = "pipecat"

    inputs = [
        HandleInput(
            name="context",
            display_name="LLM Context",
            input_types=["PipecatContext"],
            required=True,
        ),
        HandleInput(
            name="vad_analyzer",
            display_name="VAD Analyzer",
            input_types=["PipecatVADAnalyzer"],
            required=False,
            info="Optional VAD analyzer used by the user aggregator for turn detection.",
        ),
    ]

    outputs = [
        Output(
            display_name="Aggregator Pair",
            name="pair",
            method="build_pair",
            types=["PipecatContextAggregatorPair"],
        ),
        Output(
            display_name="User Aggregator",
            name="user_aggregator",
            method="build_user_aggregator",
            types=["PipecatFrameProcessor"],
        ),
        Output(
            display_name="Assistant Aggregator",
            name="assistant_aggregator",
            method="build_assistant_aggregator",
            types=["PipecatFrameProcessor"],
        ),
    ]

    _pair: PipecatContextAggregatorPair | None = None

    def _get_or_build_pair(self) -> PipecatContextAggregatorPair:
        if self._pair is not None:
            return self._pair
        from pipecat.processors.aggregators.llm_response_universal import (
            LLMContextAggregatorPair,
            LLMUserAggregatorParams,
        )

        user_params = LLMUserAggregatorParams(vad_analyzer=self.vad_analyzer) if self.vad_analyzer else None
        self._pair = LLMContextAggregatorPair(self.context, user_params=user_params)
        return self._pair

    def build_pair(self) -> PipecatContextAggregatorPair:
        return self._get_or_build_pair()

    def build_user_aggregator(self) -> PipecatFrameProcessor:
        return self._get_or_build_pair().user()

    def build_assistant_aggregator(self) -> PipecatFrameProcessor:
        return self._get_or_build_pair().assistant()

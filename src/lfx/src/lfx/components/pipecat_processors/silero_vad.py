"""Silero VAD analyzer component.

Outputs a ``SileroVADAnalyzer`` that a transport component consumes via its
``vad_analyzer`` input, OR that the ``LLMContextAggregatorPair`` consumes for
user-turn detection.
"""

from lfx.custom.custom_component.component import Component
from lfx.field_typing.voice_types import PipecatVADAnalyzer
from lfx.io import FloatInput, IntInput, Output


class SileroVADComponent(Component):
    display_name = "Silero VAD"
    description = "Voice activity detector using the Silero ONNX model."
    icon = "AudioWaveform"
    name = "SileroVAD"
    category = "pipecat"

    inputs = [
        IntInput(
            name="sample_rate",
            display_name="Sample Rate",
            value=16000,
            info="Audio sample rate in Hz. Use 8000 for telephony, 16000 for browser PCM.",
        ),
        FloatInput(
            name="confidence",
            display_name="Confidence",
            value=0.85,
            info="Minimum VAD confidence required to mark audio as speech (0-1).",
        ),
        FloatInput(
            name="start_secs",
            display_name="Start Seconds",
            value=0.2,
            info="Seconds of speech required to fire 'user started speaking'.",
            advanced=True,
        ),
        FloatInput(
            name="stop_secs",
            display_name="Stop Seconds",
            value=0.8,
            info="Seconds of silence required to fire 'user stopped speaking'.",
            advanced=True,
        ),
        FloatInput(
            name="min_volume",
            display_name="Min Volume",
            value=0.6,
            info="Minimum normalized audio volume (0-1) to consider as speech.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="VAD Analyzer",
            name="vad_analyzer",
            method="build_vad_analyzer",
            types=["PipecatVADAnalyzer"],
        ),
    ]

    def build_vad_analyzer(self) -> PipecatVADAnalyzer:
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.audio.vad.vad_analyzer import VADParams

        confidence = float(self.confidence)
        min_volume = float(self.min_volume)
        if not 0.0 <= confidence <= 1.0:
            msg = f"confidence must be between 0 and 1, got {confidence}"
            raise ValueError(msg)
        if not 0.0 <= min_volume <= 1.0:
            msg = f"min_volume must be between 0 and 1, got {min_volume}"
            raise ValueError(msg)

        params = VADParams(
            confidence=confidence,
            start_secs=float(self.start_secs),
            stop_secs=float(self.stop_secs),
            min_volume=min_volume,
        )
        return SileroVADAnalyzer(sample_rate=int(self.sample_rate), params=params)

"""Mic-gate processor component.

Pauses the LLM's audio input while the bot is speaking, then re-opens it on
the next user-VAD-start. Without this, bot audio bleeds into the LLM's input
context and inflates TTFB. Re-opens on VAD-user-start so the start of an
interruption is not dropped.

Mirrors the implementation that ships with the legacy ``lfx.voice.processors``
module of the deep integration project.
"""

from lfx.base.pipecat.processor import PipecatFrameProcessorComponent
from lfx.field_typing.voice_types import PipecatFrameProcessor
from lfx.io import HandleInput


class MicGateProcessorComponent(PipecatFrameProcessorComponent):
    display_name = "Mic Gate"
    description = "Mutes the LLM's audio input while the bot is speaking."
    icon = "MicOff"
    name = "MicGateProcessor"

    inputs = [
        HandleInput(
            name="llm",
            display_name="LLM Service",
            input_types=["PipecatLLMService", "PipecatS2SService"],
            required=True,
            info="The LLM/S2S service whose audio input should be paused while the bot speaks.",
        ),
    ]

    def build_processor(self) -> PipecatFrameProcessor:
        from pipecat.frames.frames import (
            BotStartedSpeakingFrame,
            BotStoppedSpeakingFrame,
            VADUserStartedSpeakingFrame,
        )
        from pipecat.processors.frame_processor import FrameProcessor

        llm = self.llm

        class _MicGate(FrameProcessor):
            def __init__(self) -> None:
                super().__init__()
                self._bot_speaking = False

            async def process_frame(self, frame, direction) -> None:
                await super().process_frame(frame, direction)
                await self.push_frame(frame, direction)
                if isinstance(frame, BotStartedSpeakingFrame):
                    self._bot_speaking = True
                    llm.set_audio_input_paused(True)
                elif isinstance(frame, BotStoppedSpeakingFrame):
                    self._bot_speaking = False
                    llm.set_audio_input_paused(False)
                elif isinstance(frame, VADUserStartedSpeakingFrame) and self._bot_speaking:
                    llm.set_audio_input_paused(False)

        return _MicGate()

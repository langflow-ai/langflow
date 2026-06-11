"""Base class for Pipecat FrameProcessor components.

Concrete subclasses live under ``lfx/components/pipecat_processors/`` and return
a live ``FrameProcessor`` from ``build_processor()``. The resulting object is
inserted into the linear Pipecat pipeline by ``VoicePipelineComponent``.

Use this base for VAD analyzers, context aggregators, mic-gates, transcript
loggers, and any other custom processor that sits between transport.input() and
transport.output().
"""

from abc import abstractmethod
from typing import TYPE_CHECKING

from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output

if TYPE_CHECKING:
    from pipecat.processors.frame_processor import FrameProcessor


class PipecatFrameProcessorComponent(Component):
    """Base for any custom Pipecat FrameProcessor exposed as a Langflow component."""

    trace_type = "pipecat_processor"
    category = "pipecat"

    outputs = [
        Output(
            display_name="Processor",
            name="processor",
            method="build_processor",
            types=["PipecatFrameProcessor"],
        ),
    ]

    @abstractmethod
    def build_processor(self) -> "FrameProcessor":
        """Build and return the live Pipecat FrameProcessor instance."""

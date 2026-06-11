"""Base classes for Pipecat-backed Langflow components.

These mirror the role of ``LCModelComponent`` / LangChain base classes in
``lfx.base.models``: they provide shared input scaffolding, a category tag, and
the abstract build hook each concrete component implements.
"""

from lfx.base.pipecat.processor import PipecatFrameProcessorComponent
from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.base.pipecat.tool import PipecatToolComponent

__all__ = [
    "PipecatFrameProcessorComponent",
    "PipecatServiceComponent",
    "PipecatToolComponent",
]

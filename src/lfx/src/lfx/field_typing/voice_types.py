"""Opaque type aliases for Pipecat primitives used as Component input/output types.

These are the voice-domain equivalents of the LangChain types defined in
``constants.py`` (``LanguageModel``, ``Tool``, ``Memory``, etc.). The graph engine
uses them only for edge validation — components carry the live Pipecat objects as
their runtime values.
"""

from collections.abc import Awaitable, Callable
from typing import TypeAlias

# Try imports; fall back to stubs if pipecat is not installed (matches the pattern
# used in constants.py for langchain). This keeps lfx importable in environments
# without pipecat-ai.
try:
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.audio.vad.vad_analyzer import VADAnalyzer
    from pipecat.pipeline.task import PipelineTask
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.services.llm_service import FunctionCallParams, LLMService
    from pipecat.services.stt_service import STTService
    from pipecat.services.tts_service import TTSService
    from pipecat.transports.base_transport import BaseTransport
    # pipecat-ai-flows — optional state-machine orchestrator (Phase 5b).
    try:
        from pipecat_flows import FlowManager
        from pipecat_flows.types import NodeConfig
    except ImportError:
        class FlowManager:  # noqa: D401
            pass

        class NodeConfig:  # noqa: D401
            pass
except (ImportError, OSError):

    class BaseTransport:
        pass

    class VADAnalyzer:
        pass

    class FrameProcessor:
        pass

    class LLMContext:
        pass

    class LLMContextAggregatorPair:
        pass

    class LLMService:
        pass

    class STTService:
        pass

    class TTSService:
        pass

    class PipelineTask:
        pass

    class FunctionSchema:
        pass

    class FunctionCallParams:
        pass

    class FlowManager:
        pass

    class NodeConfig:
        pass


# --- Type aliases used by component HandleInput / Output declarations ---

PipecatTransport: TypeAlias = BaseTransport
PipecatVADAnalyzer: TypeAlias = VADAnalyzer
PipecatFrameProcessor: TypeAlias = FrameProcessor

PipecatSTTService: TypeAlias = STTService
PipecatLLMService: TypeAlias = LLMService
PipecatTTSService: TypeAlias = TTSService
# Pipecat S2S services (Gemini Live, OpenAI Realtime) subclass LLMService.
PipecatS2SService: TypeAlias = LLMService

PipecatContext: TypeAlias = LLMContext
PipecatContextAggregatorPair: TypeAlias = LLMContextAggregatorPair

# A tool is a (schema, async-handler) tuple. The handler receives FunctionCallParams
# from the Pipecat LLM service and calls params.result_callback(result) to return.
PipecatToolHandler: TypeAlias = Callable[[FunctionCallParams], Awaitable[None]]
PipecatTool: TypeAlias = tuple[FunctionSchema, PipecatToolHandler]

PipecatPipelineTask: TypeAlias = PipelineTask

# Pipecat Flows (state-machine orchestrator) — Phase 5b.
PipecatFlowManager: TypeAlias = FlowManager
# NodeConfig is a TypedDict — we expose its JSON-dict shape as PipecatNodeConfig.
PipecatNodeConfig: TypeAlias = NodeConfig


PIPECAT_BASE_TYPES = {
    "PipecatTransport": PipecatTransport,
    "PipecatVADAnalyzer": PipecatVADAnalyzer,
    "PipecatFrameProcessor": PipecatFrameProcessor,
    "PipecatSTTService": PipecatSTTService,
    "PipecatLLMService": PipecatLLMService,
    "PipecatTTSService": PipecatTTSService,
    "PipecatS2SService": PipecatS2SService,
    "PipecatContext": PipecatContext,
    "PipecatContextAggregatorPair": PipecatContextAggregatorPair,
    "PipecatTool": PipecatTool,
    "PipecatPipelineTask": PipecatPipelineTask,
    "PipecatFlowManager": PipecatFlowManager,
    "PipecatNodeConfig": PipecatNodeConfig,
}

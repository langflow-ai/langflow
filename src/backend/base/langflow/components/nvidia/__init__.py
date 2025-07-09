import sys

from .nemo_guardrails import NVIDIANeMoGuardrailsComponent
from .nvidia import NVIDIAModelComponent
from .nvidia_embedding import NVIDIAEmbeddingsComponent
from .nvidia_ingest import NvidiaIngestComponent
from .nvidia_rerank import NvidiaRerankComponent

if sys.platform == "win32":
    from .system_assist import NvidiaSystemAssistComponent

    __all__ = [
        "NVIDIAEmbeddingsComponent",
        "NVIDIAModelComponent",
        "NVIDIANeMoGuardrailsComponent",
        "NvidiaIngestComponent",
        "NvidiaRerankComponent",
        "NvidiaSystemAssistComponent",
    ]
else:
    __all__ = [
        "NVIDIAEmbeddingsComponent",
        "NVIDIAModelComponent",
        "NVIDIANeMoGuardrailsComponent",
        "NvidiaIngestComponent",
        "NvidiaRerankComponent",
    ]

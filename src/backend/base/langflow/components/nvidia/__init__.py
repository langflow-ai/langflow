import sys

from .nemo_guardrails import NVIDIANeMoGuardrailsComponent
from .nvidia_ingest import NvidiaIngestComponent
from .nvidia_rerank import NvidiaRerankComponent

if sys.platform == "win32":
    from .system_assist import NvidiaSystemAssistComponent

    __all__ = ["NVIDIANeMoGuardrailsComponent", "NvidiaIngestComponent", "NvidiaRerankComponent", "NvidiaSystemAssistComponent"]
else:
    __all__ = ["NVIDIANeMoGuardrailsComponent", "NvidiaIngestComponent", "NvidiaRerankComponent"]

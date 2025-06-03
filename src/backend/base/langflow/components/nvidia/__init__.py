import sys

from .nvidia_ingest import NvidiaIngestComponent
from .nvidia_rerank import NvidiaRerankComponent

if sys.platform == "win32":
    from .system_assist import NvidiaSystemAssistComponent

    __all__ = ["NvidiaIngestComponent", "NvidiaRerankComponent", "NvidiaSystemAssistComponent"]
else:
    __all__ = ["NvidiaIngestComponent", "NvidiaRerankComponent"]

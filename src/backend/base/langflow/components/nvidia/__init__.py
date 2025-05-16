from .nvidia_ingest import NvidiaIngestComponent
from .nvidia_rerank import NvidiaRerankComponent

try:
    import gassist.rise  # noqa: F401

    from .system_assist import NvidiaSystemAssistComponent

    __all__ = ["NvidiaIngestComponent", "NvidiaRerankComponent", "NvidiaSystemAssistComponent"]
except ImportError:  # skip the component if gassist is not installed (sys_platform != win32)
    __all__ = ["NvidiaIngestComponent", "NvidiaRerankComponent"]

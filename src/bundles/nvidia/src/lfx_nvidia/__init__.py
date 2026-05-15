"""lfx-nvidia: Nvidia bundle.

Distribution unit ``lfx-nvidia``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:nvidia:<Class>@official``.
"""

from lfx_nvidia.components.nvidia.nvidia import NVIDIAModelComponent
from lfx_nvidia.components.nvidia.nvidia_embedding import NVIDIAEmbeddingsComponent
from lfx_nvidia.components.nvidia.nvidia_ingest import NvidiaIngestComponent
from lfx_nvidia.components.nvidia.nvidia_rerank import NvidiaRerankComponent
from lfx_nvidia.components.nvidia.system_assist import NvidiaSystemAssistComponent

__all__ = [
    "NVIDIAEmbeddingsComponent",
    "NVIDIAModelComponent",
    "NvidiaIngestComponent",
    "NvidiaRerankComponent",
    "NvidiaSystemAssistComponent",
]

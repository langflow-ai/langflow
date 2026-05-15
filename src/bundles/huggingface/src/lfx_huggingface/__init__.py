"""lfx-huggingface: Huggingface bundle.

Distribution unit ``lfx-huggingface``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:huggingface:<Class>@official``.
"""

from lfx_huggingface.components.huggingface.huggingface import HuggingFaceEndpointsComponent
from lfx_huggingface.components.huggingface.huggingface_inference_api import HuggingFaceInferenceAPIEmbeddingsComponent

__all__ = [
    "HuggingFaceEndpointsComponent",
    "HuggingFaceInferenceAPIEmbeddingsComponent",
]

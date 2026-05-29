"""lfx-google-genai: Google Generative AI bundle.

Distribution unit ``lfx-google-genai``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:google_genai:<Class>@official``.

Part of the Google split: 9 components from the in-tree ``google/``
directory were partitioned across 4 lfx-google-* bundles by audience
(GenAI / Workspace / BigQuery / Search).
"""

from lfx_google_genai.components.google_genai.google_generative_ai import (
    GoogleGenerativeAIComponent,
)
from lfx_google_genai.components.google_genai.google_generative_ai_embeddings import (
    GoogleGenerativeAIEmbeddingsComponent,
)

__all__ = [
    "GoogleGenerativeAIComponent",
    "GoogleGenerativeAIEmbeddingsComponent",
]

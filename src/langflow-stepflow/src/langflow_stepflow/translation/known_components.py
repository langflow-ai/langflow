"""Hash-to-module mappings for known Langflow core components.

This module contains mappings of code hashes to component module paths for
known Langflow core components. When a component's code_hash matches an entry
here and the module matches, we can use the core executor instead of compiling
custom code from a blob.

The hashes are derived from the Langflow workflow metadata and can be found in
the `metadata.code_hash` and `metadata.module` fields of each node.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KnownComponent:
    """A known core component mapping."""

    code_hash: str
    module: str  # Full module path, e.g., "lfx_docling.components.docling.DoclingInlineComponent"
    description: str = ""
    # Alternative module paths that are functionally equivalent
    # (e.g., custom_components variants)
    aliases: tuple[str, ...] = ()


# Mapping of code_hash -> KnownComponent
# These hashes are version-specific and may need updating when Langflow versions change
KNOWN_COMPONENTS: dict[str, KnownComponent] = {
    # ChatInput component (lfx)
    "f701f686b325": KnownComponent(  # pragma: allowlist secret
        code_hash="f701f686b325",  # pragma: allowlist secret
        module="lfx.components.input_output.chat.ChatInput",
        description="Chat Input component",
    ),
    # ChatOutput component (lfx)
    "9647f4d2f4b4": KnownComponent(
        code_hash="9647f4d2f4b4",
        module="lfx.components.input_output.chat_output.ChatOutput",
        description="Chat Output component",
    ),
    # LanguageModelComponent (lfx)
    "bb5f8714781b": KnownComponent(
        code_hash="bb5f8714781b",
        module="lfx.components.models.language_model.LanguageModelComponent",
        description="Language Model component",
    ),
    # Note: PromptComponent (langflow.components.prompts.prompt) is NOT included
    # because the module doesn't exist in the lfx package - it must be compiled
    # from custom code.
    #
    # Docling components (lfx-docling bundle)
    # Note: Some workflows use custom_components.docling_serve which requires
    # custom_code compilation. The lfx_docling DoclingRemoteComponent provides
    # the standard component for connecting to docling-serve.
    "d76b3853ceb4": KnownComponent(  # pragma: allowlist secret
        code_hash="d76b3853ceb4",  # pragma: allowlist secret
        module="lfx_docling.components.docling.docling_inline.DoclingInlineComponent",
        description="Docling inline document processing (local/sidecar)",
        aliases=("lfx.components.docling.docling_inline.DoclingInlineComponent",),
    ),
    "26eeb513dded": KnownComponent(
        code_hash="26eeb513dded",
        module="lfx_docling.components.docling.docling_remote.DoclingRemoteComponent",
        description="Docling remote processing via docling-serve API",
        aliases=("lfx.components.docling.docling_remote.DoclingRemoteComponent",),
    ),
    # Custom "Docling Serve" variant used in production workflows
    # Same class as DoclingRemoteComponent but with workflow-specific customizations
    "5723576d00e5": KnownComponent(
        code_hash="5723576d00e5",
        module="lfx_docling.components.docling.docling_remote.DoclingRemoteComponent",
        description="Docling Serve (custom variant of DoclingRemoteComponent)",
        aliases=("lfx.components.docling.docling_remote.DoclingRemoteComponent", "custom_components.docling_serve"),
    ),
    "397fa38f89d7": KnownComponent(
        code_hash="397fa38f89d7",
        module="lfx_docling.components.docling.chunk_docling_document.ChunkDoclingDocumentComponent",
        description="Chunk DoclingDocument for RAG pipelines",
        aliases=("lfx.components.docling.chunk_docling_document.ChunkDoclingDocumentComponent",),
    ),
    "4de16ddd37ac": KnownComponent(
        code_hash="4de16ddd37ac",
        module="lfx_docling.components.docling.export_docling_document.ExportDoclingDocumentComponent",
        description="Export DoclingDocument to markdown, html or other formats",
        aliases=("lfx.components.docling.export_docling_document.ExportDoclingDocumentComponent",),
    ),
    # EmbeddingModel component (lfx)
    "0e2d6fe67a26": KnownComponent(
        code_hash="0e2d6fe67a26",
        module="lfx.components.models_and_agents.embedding_model.EmbeddingModelComponent",
        description="Embedding Model - generate embeddings using OpenAI/Ollama",
        aliases=("custom_components.embedding_model",),
    ),
    # Add more known components here as needed
}


def lookup_known_component(code_hash: str, module: str | None = None) -> KnownComponent | None:
    """Look up a known component by code hash.

    Args:
        code_hash: The code_hash from workflow metadata
        module: Optional module path to verify (safety check)

    Returns:
        KnownComponent if found and module matches (if provided), None otherwise
    """
    known = KNOWN_COMPONENTS.get(code_hash)

    if known is None:
        return None

    # If module provided, verify it matches (or is a known alias)
    if module is not None and known.module != module:
        # Check if module is a known alias
        if module not in known.aliases:
            # Hash collision or outdated mapping - log warning and return None
            logger.warning(
                f"Code hash {code_hash} matches known component {known.module} "
                f"but workflow specifies {module}. Using custom_code executor."
            )
            return None
        # Module is a known alias, proceed with the known component
        logger.info(f"Code hash {code_hash} using alias {module} -> {known.module}")

    return known


def module_to_path(module: str) -> str:
    """Convert module path to URL path segment.

    Example: "lfx_docling.components.docling.DoclingInlineComponent"
          -> "lfx_docling/components/docling/DoclingInlineComponent"

    Args:
        module: Full module path with dots

    Returns:
        URL path segment with slashes
    """
    return module.replace(".", "/")

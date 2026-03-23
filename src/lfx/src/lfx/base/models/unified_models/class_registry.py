"""Lazy-import registry for model and embedding provider classes.

Keeps import tables and caching logic for provider classes (e.g. ChatOpenAI,
OpenAIEmbeddings) so that only the package actually needed gets imported at
runtime.
"""

from __future__ import annotations

import importlib

# ---------------------------------------------------------------------------
# Import registries
# Mapping from class name to (module_path, attribute_name, install_hint | None).
# ---------------------------------------------------------------------------

_MODEL_CLASS_IMPORTS: dict[str, tuple[str, str, str | None]] = {
    "ChatOpenAI": ("langchain_openai", "ChatOpenAI", None),
    "ChatAnthropic": ("langchain_anthropic", "ChatAnthropic", None),
    "ChatGoogleGenerativeAIFixed": (
        "lfx.base.models.google_generative_ai_model",
        "ChatGoogleGenerativeAIFixed",
        "langchain-google-genai",
    ),
    "ChatOllama": ("langchain_ollama", "ChatOllama", None),
    "ChatWatsonx": ("langchain_ibm", "ChatWatsonx", None),
}

_EMBEDDING_CLASS_IMPORTS: dict[str, tuple[str, str, str | None]] = {
    "OpenAIEmbeddings": ("langchain_openai", "OpenAIEmbeddings", None),
    "GoogleGenerativeAIEmbeddings": (
        "langchain_google_genai",
        "GoogleGenerativeAIEmbeddings",
        None,
    ),
    "OllamaEmbeddings": ("langchain_ollama", "OllamaEmbeddings", None),
    "WatsonxEmbeddings": ("langchain_ibm", "WatsonxEmbeddings", None),
}

# Canonical mapping of provider name → embedding class name.
# Used by EmbeddingModelComponent and by flow_requirements to resolve
# which PyPI package a given embedding provider needs at runtime.
EMBEDDING_PROVIDER_CLASS_MAPPING: dict[str, str] = {
    "OpenAI": "OpenAIEmbeddings",
    "Google Generative AI": "GoogleGenerativeAIEmbeddings",
    "Ollama": "OllamaEmbeddings",
    "IBM WatsonX": "WatsonxEmbeddings",
    "IBM watsonx.ai": "WatsonxEmbeddings",  # Alias used by MODEL_PROVIDERS_DICT
}

# NOTE: These module-level caches are never invalidated.  This is intentional
# for production, but tests that need to swap model/embedding classes should
# patch `get_model_class` / `get_embedding_class` at the *call site* rather
# than mutating these dicts, to avoid cross-test pollution.
_model_class_cache: dict[str, type] = {}
_embedding_class_cache: dict[str, type] = {}


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _import_class(
    class_name: str,
    registry: dict[str, tuple[str, str, str | None]],
    cache: dict[str, type],
    kind: str,
) -> type:
    """Import and return a single class by name from *registry*.

    Parameters
    ----------
    class_name:
        Key into *registry*.
    registry:
        One of ``_MODEL_CLASS_IMPORTS`` / ``_EMBEDDING_CLASS_IMPORTS``.
    cache:
        One of ``_model_class_cache`` / ``_embedding_class_cache``.
    kind:
        Human-readable label (``"model"`` or ``"embedding"``) for error messages.
    """
    if class_name in cache:
        return cache[class_name]

    import_info = registry.get(class_name)
    if import_info is None:
        msg = f"Unknown {kind} class: {class_name}"
        raise ValueError(msg)

    module_path, attr_name, install_hint = import_info
    pkg_hint = install_hint or module_path.split(".")[0].replace("_", "-")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        msg = (
            f"Could not import '{module_path}' for {kind} class '{class_name}'. "
            f"Install the missing package (e.g. uv pip install {pkg_hint})."
        )
        raise ImportError(msg) from exc
    try:
        cls = getattr(module, attr_name)
    except AttributeError as exc:
        msg = (
            f"Module '{module_path}' was imported but does not have attribute '{attr_name}'. "
            f"This may indicate a version mismatch. "
        )
        raise AttributeError(msg) from exc
    cache[class_name] = cls
    return cls


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_model_class(class_name: str) -> type:
    """Import and return a single model class by name.

    Only imports the provider package that is actually needed.
    """
    return _import_class(class_name, _MODEL_CLASS_IMPORTS, _model_class_cache, "model")


def get_embedding_class(class_name: str) -> type:
    """Import and return a single embedding class by name.

    Only imports the provider package that is actually needed.
    """
    return _import_class(class_name, _EMBEDDING_CLASS_IMPORTS, _embedding_class_cache, "embedding")

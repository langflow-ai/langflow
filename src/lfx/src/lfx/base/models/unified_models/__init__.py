"""Backward-compatible unified models API.

This package replaces the former monolithic ``unified_models.py`` module while
preserving the import surface used across the codebase.
"""

from .build_config import (
    _MODEL_OPTIONS_CACHE_TTL_SECONDS,
    _get_all_provider_mapped_fields,
    apply_provider_variable_config_to_build_config,
    handle_model_input_update,
    update_model_options_in_build_config,
)
from .class_registry import (
    _EMBEDDING_CLASS_IMPORTS,
    _MODEL_CLASS_IMPORTS,
    EMBEDDING_PROVIDER_CLASS_MAPPING,
    get_embedding_class,
    get_model_class,
)
from .credentials import (
    get_all_variables_for_provider,
    get_api_key_for_provider,
    validate_model_provider_key,
)
from .instantiation import get_embeddings, get_llm
from .model_catalog import (
    get_embedding_model_options,
    get_language_model_options,
    get_unified_models_detailed,
    normalize_model_names_to_dicts,
)
from .provider_queries import (
    MODELS_DETAILED,
    get_model_provider_metadata,
    get_model_provider_variable_mapping,
    get_model_providers,
    get_models_detailed,
    get_provider_all_variables,
    get_provider_from_variable_key,
    get_provider_required_variable_keys,
    model_provider_metadata,
)

__all__ = [
    "EMBEDDING_PROVIDER_CLASS_MAPPING",
    "MODELS_DETAILED",
    "_EMBEDDING_CLASS_IMPORTS",
    "_MODEL_CLASS_IMPORTS",
    "_MODEL_OPTIONS_CACHE_TTL_SECONDS",
    "_get_all_provider_mapped_fields",
    "apply_provider_variable_config_to_build_config",
    "get_all_variables_for_provider",
    "get_api_key_for_provider",
    "get_embedding_class",
    "get_embedding_model_options",
    "get_embeddings",
    "get_language_model_options",
    "get_llm",
    "get_model_class",
    "get_model_provider_metadata",
    "get_model_provider_variable_mapping",
    "get_model_providers",
    "get_models_detailed",
    "get_provider_all_variables",
    "get_provider_from_variable_key",
    "get_provider_required_variable_keys",
    "get_unified_models_detailed",
    "handle_model_input_update",
    "model_provider_metadata",
    "normalize_model_names_to_dicts",
    "update_model_options_in_build_config",
    "validate_model_provider_key",
]

from __future__ import annotations

__all__ = [
    "LIVE_MODEL_PROVIDERS",
    "LCModelComponent",
    "apply_provider_variable_config_to_build_config",
    "fetch_live_ollama_models",
    "fetch_live_watsonx_models",
    "get_embeddings",
    "get_live_models_for_provider",
    "get_model_provider_metadata",
    "get_model_provider_variable_mapping",
    "get_model_providers",
    "get_ollama_embedding_models",
    "get_ollama_llm_models",
    "get_provider_all_variables",
    "get_provider_from_variable_key",
    "get_provider_required_variable_keys",
    "get_provider_variable_value",
    "get_unified_models_detailed",
    "get_watsonx_embedding_models",
    "get_watsonx_llm_models",
    "handle_model_input_update",
    "replace_with_live_models",
]

_SOURCE_MAP: dict[str, str] = {
    "LCModelComponent": ".model",
    "LIVE_MODEL_PROVIDERS": ".model_metadata",
    "fetch_live_ollama_models": ".model_utils",
    "fetch_live_watsonx_models": ".model_utils",
    "get_live_models_for_provider": ".model_utils",
    "get_ollama_embedding_models": ".model_utils",
    "get_ollama_llm_models": ".model_utils",
    "get_provider_variable_value": ".model_utils",
    "get_watsonx_embedding_models": ".model_utils",
    "get_watsonx_llm_models": ".model_utils",
    "replace_with_live_models": ".model_utils",
    "apply_provider_variable_config_to_build_config": ".unified_models",
    "get_embeddings": ".unified_models",
    "get_model_provider_metadata": ".unified_models",
    "get_model_provider_variable_mapping": ".unified_models",
    "get_model_providers": ".unified_models",
    "get_provider_all_variables": ".unified_models",
    "get_provider_from_variable_key": ".unified_models",
    "get_provider_required_variable_keys": ".unified_models",
    "get_unified_models_detailed": ".unified_models",
    "handle_model_input_update": ".unified_models",
}


def __getattr__(name: str):
    if name not in _SOURCE_MAP:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    import importlib

    mod = importlib.import_module(_SOURCE_MAP[name], package=__spec__.parent)
    val = getattr(mod, name)
    globals()[name] = val
    return val

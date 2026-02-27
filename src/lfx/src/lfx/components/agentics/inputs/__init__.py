"""Common input field definitions and utilities for Agentics components.

Provides reusable input configurations for:
- Model provider selection and authentication
- Output schema definition
- Provider-specific settings (WatsonX, Ollama)
"""

from __future__ import annotations

from lfx.components.agentics.inputs.common_inputs import (
    GENERATED_FIELDS_TABLE_SCHEMA,
    get_api_key_input,
    get_generated_fields_input,
    get_model_provider_inputs,
    get_ollama_url_input,
    get_watsonx_inputs,
)

__all__ = [
    "GENERATED_FIELDS_TABLE_SCHEMA",
    "get_api_key_input",
    "get_generated_fields_input",
    "get_model_provider_inputs",
    "get_ollama_url_input",
    "get_watsonx_inputs",
]

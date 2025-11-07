"""
Provider-specific default configurations for Agent components.
"""

import os
from typing import Dict, Any


def get_provider_defaults(provider: str, build_config: dict) -> Dict[str, Any]:
    """
    Get default field values for a specific provider.
    
    Args:
        provider: The name of the provider (e.g., "Azure OpenAI")
        build_config: Current build configuration
        
    Returns:
        Dictionary of field updates with default values
    """
    defaults = {}
    
    if provider == "Azure OpenAI":
        defaults = _get_azure_openai_defaults(build_config)
    
    return defaults


def _get_azure_openai_defaults(build_config: dict) -> Dict[str, Any]:
    """Get default values for Azure OpenAI provider."""
    return {
        "api_key": {
            **build_config.get("api_key", {}),
            "value": os.environ.get("AZURE_OPENAI_API_KEY", "")
        },
        "azure_deployment": {
            **build_config.get("azure_deployment", {}),
            "value": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")
        },
        "azure_endpoint": {
            **build_config.get("azure_endpoint", {}),
            "value": os.environ.get("AZURE_OPENAI_ENDPOINT", "https://your-resource.openai.azure.com/")
        },
        "azure_api_version": {
            **build_config.get("azure_api_version", {}),
            "value": os.environ.get("AZURE_API_VERSION", "2024-02-15-preview")
        }
    }


def apply_provider_defaults(provider: str, build_config: dict) -> dict:
    """
    Apply default values for a provider to the build config.
    
    Args:
        provider: The provider name
        build_config: The build configuration to update
        
    Returns:
        Updated build configuration
    """
    defaults = get_provider_defaults(provider, build_config)
    
    # Apply defaults to build_config
    for field_name, field_config in defaults.items():
        if field_name in build_config:
            build_config[field_name].update(field_config)
    
    return build_config
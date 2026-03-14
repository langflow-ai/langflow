"""Adapter namespaces for service-scoped plugin registries."""

from .payload import AdapterPayload, AdapterPayloadValidationError, PayloadSlot, ProviderPayloadSchemas

__all__ = [
    "AdapterPayload",
    "AdapterPayloadValidationError",
    "PayloadSlot",
    "ProviderPayloadSchemas",
]

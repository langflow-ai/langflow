"""Adapter namespaces for service-scoped plugin registries."""

from .payload import (
    AdapterPayload,
    AdapterPayloadValidationError,
    PayloadSlot,
    PayloadSlotPolicy,
    ProviderPayloadSchemas,
)

__all__ = [
    "AdapterPayload",
    "AdapterPayloadValidationError",
    "PayloadSlot",
    "PayloadSlotPolicy",
    "ProviderPayloadSchemas",
]

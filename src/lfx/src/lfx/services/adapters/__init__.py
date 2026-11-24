"""Adapter namespaces for service-scoped plugin registries."""

from .payload import (
    AdapterPayload,
    AdapterPayloadMissingError,
    AdapterPayloadValidationError,
    PayloadSlot,
    PayloadSlotPolicy,
    ProviderPayloadSchemas,
)

__all__ = [
    "AdapterPayload",
    "AdapterPayloadMissingError",
    "AdapterPayloadValidationError",
    "PayloadSlot",
    "PayloadSlotPolicy",
    "ProviderPayloadSchemas",
]

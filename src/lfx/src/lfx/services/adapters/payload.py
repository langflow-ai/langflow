"""Shared payload contracts and schema registry primitives.

Ownership boundaries start here:

- ``PayloadSlot`` is a generic parse/dump contract and is layer-agnostic.
  Both adapter-side and API-side registries use the same slot primitive.
- ``ProviderPayloadSchemas`` is a structural base for named slot registries.
  It owns introspection helpers only (``slots`` / ``active_slots``), not
  any adapter- or API-specific slot names.
- Concrete ``*PayloadFields`` classes (for example deployment payload fields)
  define canonical slot names in lfx so both layers share one structure.
- Adapter integrations populate adapter-side registries in lfx
  (``*PayloadSchemas`` subclasses).
- Langflow integrations populate API-side registries in Langflow
  (for example ``DeploymentApiPayloads``), including Langflow-specific
  validation/reshaping decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Generic

from pydantic import BaseModel, ValidationError
from typing_extensions import TypeVar

AdapterPayload = dict[str, Any]
T_Model = TypeVar("T_Model", bound=BaseModel)


class PayloadSlotPolicy(str, Enum):
    """Controls how a slot applies schema validation."""

    VALIDATE_ONLY = "validate_only"
    VALIDATE_AND_DUMP = "validate_and_dump"


class AdapterPayloadValidationError(ValueError):
    """Raised when a payload fails adapter schema validation."""

    def __init__(self, *, model_name: str, error: ValidationError) -> None:
        self.model_name = model_name
        self.error = error
        # Keep public exception text sanitized to avoid leaking raw payload
        # fragments from ValidationError.__str__() into logs/responses.
        super().__init__(f"Invalid payload for '{model_name}'.")


@dataclass(frozen=True)
class PayloadSlot(Generic[T_Model]):
    """Layer-agnostic contract between raw payload dicts and typed models."""

    adapter_model: type[T_Model]
    policy: PayloadSlotPolicy = PayloadSlotPolicy.VALIDATE_AND_DUMP

    def parse(self, raw: AdapterPayload) -> T_Model:
        """Validate and parse raw provider payload into the typed model."""
        try:
            return self.adapter_model.model_validate(raw)
        except ValidationError as exc:
            raise AdapterPayloadValidationError(model_name=self.adapter_model.__name__, error=exc) from exc

    def dump(self, value: T_Model) -> AdapterPayload:
        """Serialize typed model back into a plain provider payload dict."""
        return value.model_dump(mode="json")

    def apply(self, raw: AdapterPayload) -> AdapterPayload:
        """Apply slot policy to a raw payload dict."""
        validated = self.parse(raw)
        if self.policy is PayloadSlotPolicy.VALIDATE_ONLY:
            return raw
        return self.dump(validated)


@dataclass(frozen=True)
class ProviderPayloadSchemas:
    """Structural base class for named slot registries.

    This class intentionally avoids defining slot names or ownership policy.
    Concrete subclasses declare domain-specific fields and are owned by the
    module that defines that domain contract (for example deployment).
    """

    def slots(self) -> dict[str, PayloadSlot[Any] | None]:
        """Return all registry slots, keyed by slot name."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def active_slots(self) -> dict[str, PayloadSlot[Any]]:
        """Return only populated (non-None) slots."""
        return {name: slot for name, slot in self.slots().items() if slot is not None}

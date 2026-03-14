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
from typing import Any, Generic

from pydantic import BaseModel, ValidationError
from typing_extensions import TypeVar

AdapterPayload = dict[str, Any]
T_Model = TypeVar("T_Model", bound=BaseModel)


class AdapterPayloadValidationError(ValueError):
    """Raised when a payload fails adapter schema validation."""

    def __init__(self, *, model_name: str, error: ValidationError) -> None:
        self.model_name = model_name
        self.error = error
        super().__init__(f"Invalid payload for '{model_name}': {error}")


@dataclass(frozen=True)
class PayloadSlot(Generic[T_Model]):
    """Layer-agnostic contract between raw payload dicts and typed models."""

    adapter_model: type[T_Model]

    def parse(self, raw: AdapterPayload) -> T_Model:
        """Validate and parse raw provider payload into the typed model."""
        try:
            return self.adapter_model.model_validate(raw)
        except ValidationError as exc:
            raise AdapterPayloadValidationError(model_name=self.adapter_model.__name__, error=exc) from exc

    def dump(self, value: T_Model) -> AdapterPayload:
        """Serialize typed model back into a plain provider payload dict."""
        return value.model_dump(mode="json")


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

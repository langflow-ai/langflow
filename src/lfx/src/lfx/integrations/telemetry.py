"""Low-cardinality telemetry boundary for integration actions."""

from __future__ import annotations

import contextlib
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from lfx.integrations.errors import INTEGRATION_ERROR_CODES, IntegrationError, normalize_integration_error
from lfx.observability import outbound_call_span
from lfx.services.schema import ServiceType
from lfx.services.telemetry.schema import IntegrationActionPayload

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.custom.custom_component.component import Component


async def _emit(payload: IntegrationActionPayload) -> None:
    """Best-effort enqueue without creating a telemetry service as a side effect."""
    try:
        from lfx.services.manager import get_service_manager

        service = get_service_manager().services.get(ServiceType.TELEMETRY_SERVICE)
        if service is not None:
            await service.send_telemetry_data(payload, "integration_action")
    except Exception:  # noqa: BLE001 - telemetry must never take down an action
        return


@asynccontextmanager
async def integration_action(
    component: Component,
    *,
    provider: str,
    capability: str,
    owner_kind: str,
) -> AsyncIterator[None]:
    """Measure, classify, and safely trace one provider action."""
    started = time.monotonic()
    principal = getattr(getattr(component, "graph", None), "execution_principal", None)
    principal_kind = getattr(principal, "kind", "unknown")
    error_code: str | None = None
    success = False
    attributes = {
        "integration.provider": provider,
        "integration.capability": capability,
        "integration.owner_kind": owner_kind,
        "integration.principal_kind": principal_kind,
    }
    try:
        with outbound_call_span("integration.action", attributes) as span:
            try:
                yield
                success = True
            except IntegrationError as exc:
                error_code = exc.code
                span.set_attribute("integration.error_code", error_code)
                span.record_error(error_code)
                raise
            except Exception as exc:
                normalized = normalize_integration_error(exc, provider=provider)
                error_code = normalized.code
                span.set_attribute("integration.error_code", error_code)
                span.record_error(error_code)
                raise normalized from exc
            else:
                span.set_attribute("integration.error_code", "none")
    finally:
        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
        payload = IntegrationActionPayload(
            provider=provider,
            capability=capability,
            ms=elapsed_ms,
            success=success,
            error_code=error_code if error_code in INTEGRATION_ERROR_CODES else ("other" if error_code else None),
            owner_kind=owner_kind,
            principal_kind=principal_kind,
        )
        await _emit(payload)
        with contextlib.suppress(Exception):
            component.log(
                {
                    "provider": provider,
                    "capability": capability,
                    "success": success,
                    "error_code": payload.error_code,
                    "ms": elapsed_ms,
                },
                name="Integration action",
            )

"""Backwards-compatible re-export of the OTel FastAPI route-detail patch.

The patch moved to :mod:`lfx.observability`, alongside the rest of the application-telemetry
bootstrap, so that ``lfx serve`` instruments its own app the same way langflow does. This
module re-exports it for importers that still reference the old path.
"""

from lfx.observability import (
    _resolve_included_route,
    _safe_get_route_details,
    patch_otel_fastapi_route_details,
)

__all__ = [
    "_resolve_included_route",
    "_safe_get_route_details",
    "patch_otel_fastapi_route_details",
]

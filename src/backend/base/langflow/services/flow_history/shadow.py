"""Deriving operations from accepted saves without recording them.

Before history is written, every accepted graph write derives its operations
and verifies their replay here, only to measure: how often derivation fails,
how many operations a save produces, and how long it takes. Nothing is stored
and nothing can fail the save, because no completeness promise exists yet.

Logs carry the flow ID, sizes and error codes, never graph values or error
messages, which can quote them.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from lfx.services.flow_operations import FlowDataValidationError, FlowOperationError

from langflow.services.deps import get_flow_operation_service

if TYPE_CHECKING:
    from uuid import UUID


def observe_graph_write(flow_id: UUID, before: Any, after: Any) -> None:
    """Derive and verify the operations of one accepted write, logging only aggregates."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return
    started = time.perf_counter()
    try:
        derived = get_flow_operation_service().derive(before, after)
    except FlowDataValidationError as exc:
        logger.info(
            "Flow history shadow derivation skipped a graph that breaks the engine's rules",
            flow_id=str(flow_id),
            error_code=exc.code,
            violation_codes=sorted({violation.code.value for violation in exc.violations}),
            elapsed_ms=_elapsed_ms(started),
        )
    except FlowOperationError as exc:
        logger.warning(
            "Flow history shadow derivation failed",
            flow_id=str(flow_id),
            error_type=type(exc).__name__,
            error_code=exc.code,
            elapsed_ms=_elapsed_ms(started),
        )
    except Exception as exc:  # noqa: BLE001 -- shadow mode must never fail a save
        logger.warning(
            "Flow history shadow derivation raised unexpectedly",
            flow_id=str(flow_id),
            error_type=type(exc).__name__,
            elapsed_ms=_elapsed_ms(started),
        )
    else:
        logger.debug(
            "Flow history shadow derivation succeeded",
            flow_id=str(flow_id),
            operation_count=len(derived.operations),
            elapsed_ms=_elapsed_ms(started),
        )


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)

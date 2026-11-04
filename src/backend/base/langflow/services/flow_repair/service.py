"""Apply selected repairs with one recovery transaction per flow."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from lfx.log import logger
from lfx.utils.flow_validation import CustomComponentValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, select, update

from langflow.api.utils.migration_pause import is_paused
from langflow.services.audit import vocabulary as audit_vocab
from langflow.services.audit.attribution import resolve_audit_actor
from langflow.services.audit.writer import AuditEventDraft, stage_audit_event
from langflow.services.authorization.guards import audit_guard_in_transaction
from langflow.services.database.lock_retry import is_database_lock_error
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.crud import create_flow_version_entry, set_flow_version_retained
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.flow_repair.models import RepairBatchResult, RepairResult, RepairSelection
from langflow.services.flow_repair.planning import RepairPlan, data_digest, plan_flow_repair
from langflow.services.flow_repair.policy import authorize_flow, require_admin, validate_owner_policy
from langflow.services.flow_repair.providers import ProviderSelectionUnverifiableError
from langflow.services.flow_repair.retention import REPAIR_RETENTION_REASON
from langflow.services.maintenance.state import maintenance_status
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.flow_repair.models import RepairApplyRequest, RepairPreviewRequest


async def target_registry() -> dict[str, Any]:
    from lfx.interface.components import get_and_cache_all_types_dict

    return await get_and_cache_all_types_dict(settings_service=get_settings_service())


async def require_repair_window(session: AsyncSession) -> None:
    if is_paused():
        raise HTTPException(status_code=503, detail="The instance migration pause does not permit repairs")
    state = await maintenance_status(session)
    if not state.maintenance:
        raise HTTPException(status_code=409, detail="Enable database maintenance before applying repairs")
    if state.running_jobs:
        raise HTTPException(status_code=409, detail="Wait for running jobs to finish before applying repairs")


async def _require_report(session: AsyncSession, report_id: UUID | None) -> None:
    if report_id is not None:
        from langflow.services.upgrade_reports.history import require_report

        try:
            await require_report(session, report_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Upgrade report not found") from exc


async def _record_result(
    session: AsyncSession, result: RepairResult, *, report_id: UUID | None, actor_id: UUID, target_sha256: str
) -> None:
    if report_id is not None:
        from langflow.services.upgrade_reports.history import record_repair_result

        await record_repair_result(
            session,
            report_id=report_id,
            actor_id=actor_id,
            target_sha256=target_sha256,
            result=result.model_dump(mode="json"),
        )


async def _plan_selected(
    session: AsyncSession, flow_id: UUID, actor_id: UUID, all_types: Mapping[str, Any], *, for_update: bool
) -> tuple[Flow | None, RepairPlan | None, RepairResult]:
    actor = await require_admin(session, actor_id)
    query = select(Flow).where(Flow.id == flow_id)
    if for_update:
        query = query.with_for_update()
    flow = (await session.exec(query.execution_options(populate_existing=True))).first()
    if flow is None:
        return None, None, RepairResult(flow_id=flow_id, status="not_found", reason_codes=["flow_not_found"])
    owner = await authorize_flow(session, flow, actor)
    result = RepairResult(flow_id=flow_id, status="manual", version_token=flow.version_token)
    if owner is None:
        result.reason_codes = ["owner_unavailable"]
    elif flow.locked:
        result.reason_codes = ["flow_locked"]
    elif flow.fs_path:
        result.reason_codes = ["file_backed_flow"]
    elif not isinstance(flow.data, dict):
        result.reason_codes = ["malformed_flow"]
    else:
        result.data_sha256 = data_digest(flow.data)
        plan = plan_flow_repair(flow.data, all_types)
        result.reason_codes = plan.reason_codes
        if plan.data is not None:
            await validate_owner_policy(flow, owner, plan.data, all_types)
            result.updated_nodes = plan.updated_nodes
            result.status = "ready" if plan.updated_nodes else "unchanged"
            return flow, plan, result
    return flow, None, result


def _failed_result(flow_id: UUID, exc: Exception) -> RepairResult:
    if isinstance(exc, HTTPException):
        status: Literal["forbidden", "conflict", "failed"] = (
            "forbidden" if exc.status_code in {401, 403} else "conflict" if exc.status_code in {409, 428} else "failed"
        )
        return RepairResult(
            flow_id=flow_id,
            status=status,
            reason_codes=["authorization_denied" if status == "forbidden" else "repair_unavailable"],
        )
    if isinstance(exc, ImportError):
        return RepairResult(flow_id=flow_id, status="failed", reason_codes=["repair_prerequisite_unavailable"])
    if isinstance(exc, ProviderSelectionUnverifiableError):
        return RepairResult(flow_id=flow_id, status="manual", reason_codes=["provider_selection_unverifiable"])
    if isinstance(exc, PermissionError | CustomComponentValidationError):
        return RepairResult(flow_id=flow_id, status="manual", reason_codes=["owner_policy_denied"])
    if isinstance(exc, ValueError | TypeError):
        return RepairResult(flow_id=flow_id, status="manual", reason_codes=["malformed_flow"])
    if isinstance(exc, SQLAlchemyError) and is_database_lock_error(exc):
        return RepairResult(flow_id=flow_id, status="conflict", reason_codes=["database_busy"])
    if isinstance(exc, SQLAlchemyError):
        return RepairResult(flow_id=flow_id, status="failed", reason_codes=["database_unavailable"])
    return RepairResult(flow_id=flow_id, status="failed", reason_codes=["repair_failed"])


def _batch_result(fingerprint: str, results: list[RepairResult]) -> RepairBatchResult:
    info = get_version_info()
    try:
        lfx_version = version("lfx")
    except PackageNotFoundError:
        lfx_version = None
    return RepairBatchResult(
        target_sha256=fingerprint,
        target_version=info["version"] if info is not None else None,
        lfx_version=lfx_version,
        results=results,
    )


async def preview_repairs(payload: RepairPreviewRequest, actor_id: UUID) -> RepairBatchResult:
    all_types = await target_registry()
    fingerprint = data_digest(all_types)
    async with session_scope() as session:
        await require_admin(session, actor_id)
        await _require_report(session, payload.report_id)
    results = []
    for flow_id in payload.flow_ids:
        try:
            async with session_scope() as session, audit_guard_in_transaction(session):
                _flow, _plan, result = await _plan_selected(session, flow_id, actor_id, all_types, for_update=False)
        except Exception as exc:  # noqa: BLE001
            result = _failed_result(flow_id, exc)
        results.append(result)
    return _batch_result(fingerprint, results)


async def _write_selected(
    session: AsyncSession, selection: RepairSelection, actor_id: UUID, all_types: Mapping[str, Any]
) -> RepairResult:
    await require_repair_window(session)
    flow, plan, result = await _plan_selected(session, selection.flow_id, actor_id, all_types, for_update=True)
    if (
        flow is not None
        and result.data_sha256 is not None
        and (selection.version_token != flow.version_token or selection.data_sha256 != result.data_sha256)
    ):
        result.status, result.reason_codes = "conflict", ["source_changed"]
        return result
    if result.status != "ready" or flow is None or plan is None:
        return result
    owner_id = flow.user_id
    if owner_id is None:
        result.status, result.reason_codes = "manual", ["owner_unavailable"]
        return result
    claim = uuid4()
    token_condition = (
        Flow.version_token == selection.version_token
        if selection.version_token is not None
        else col(Flow.version_token).is_(None)
    )
    claimed = await session.exec(
        update(Flow)
        .where(Flow.id == flow.id, token_condition)
        .values(version_token=claim)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        result.status, result.reason_codes = "conflict", ["source_changed"]
        return result
    recovery = await create_flow_version_entry(
        session,
        flow_id=flow.id,
        user_id=owner_id,
        data=copy.deepcopy(flow.data),
        description="Recovery before an administrator upgraded this flow",
        prune=False,
    )
    await set_flow_version_retained(session, recovery.id, retained=True, reason=REPAIR_RETENTION_REASON)
    written = await session.exec(
        update(Flow)
        .where(Flow.id == flow.id, Flow.version_token == claim)
        .values(data=plan.data, version_token=claim, updated_at=datetime.now(timezone.utc), last_modified_by=actor_id)
        .execution_options(synchronize_session=False)
    )
    if written.rowcount != 1:
        raise HTTPException(status_code=409, detail="The flow changed during repair")
    await stage_audit_event(
        session,
        AuditEventDraft(
            resource_type=audit_vocab.AuditResourceType.FLOW,
            resource_id=flow.id,
            resource_name=flow.name,
            action=audit_vocab.FLOW_WRITE,
            operation=audit_vocab.AuditOperation.PATCH,
            event_type=audit_vocab.AuditEventType.ACTION,
            result=audit_vocab.AuditResult.SUCCEEDED,
            actor=resolve_audit_actor(actor_id),
            details={"schema_version": 1, "written_fields": ["data"]},
        ),
    )
    return RepairResult(
        flow_id=flow.id,
        status="updated",
        version_token=claim,
        data_sha256=data_digest(plan.data),
        updated_nodes=plan.updated_nodes,
        recovery_version_id=recovery.id,
    )


async def apply_repairs(payload: RepairApplyRequest, actor_id: UUID) -> RepairBatchResult:
    all_types = await target_registry()
    fingerprint = data_digest(all_types)
    async with session_scope() as session:
        await require_admin(session, actor_id)
        await require_repair_window(session)
        await _require_report(session, payload.report_id)
    if fingerprint != payload.target_sha256:
        raise HTTPException(status_code=409, detail="The target registry changed. Preview the selected flows again")
    results = []
    for selection in payload.flows:
        try:
            async with session_scope() as session, audit_guard_in_transaction(session):
                result = await _write_selected(session, selection, actor_id, all_types)
                await _record_result(
                    session, result, report_id=payload.report_id, actor_id=actor_id, target_sha256=fingerprint
                )
        except Exception as exc:  # noqa: BLE001
            result = _failed_result(selection.flow_id, exc)
            await logger.aerror("Flow repair did not commit for flow %s (%s)", selection.flow_id, type(exc).__name__)
            if payload.report_id is not None:
                try:
                    async with session_scope() as session:
                        await _record_result(
                            session, result, report_id=payload.report_id, actor_id=actor_id, target_sha256=fingerprint
                        )
                except Exception:  # noqa: BLE001
                    result.reason_codes.append("outcome_record_unavailable")
        results.append(result)
    return _batch_result(fingerprint, results)

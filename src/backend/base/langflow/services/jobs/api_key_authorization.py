"""Retain restricted credential provenance across queued execution boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from lfx.services.authorization import AuthorizationPrincipal
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import select

from langflow.services.auth.context import (
    AUTH_METHOD_API_KEY,
    AuthCredentialContext,
    current_auth_is_restricted_api_key,
    get_current_auth_context,
    set_current_auth_context,
)
from langflow.services.database.models.api_key.crud import (
    _external_access_ceiling_blocks_user,
    _is_expired,
    _scoped_key_can_authenticate,
)
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus, JobType
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_settings_service, session_scope

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.jobs.model import Job
    from langflow.services.jobs.service import JobService

API_KEY_AUTHORIZATION_METADATA = "api_key_authorization"  # pragma: allowlist secret
JOB_AUTHORIZATION_ERROR = {"type": "authorization_denied", "detail": "Job authorization is no longer valid."}


class JobAuthorizationError(PermissionError):
    def __init__(self) -> None:
        super().__init__(JOB_AUTHORIZATION_ERROR["detail"])


class ApiKeyJobTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: Literal["flow", "knowledge_base"]
    resource_id: UUID
    action: Literal["execute", "ingest"]


class ApiKeyJobAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    api_key_id: UUID
    actor_user_id: UUID
    targets: list[ApiKeyJobTarget] = Field(min_length=1, max_length=2)


async def _targets_for_job(
    session: AsyncSession, *, flow_id: UUID, job_type: JobType, asset_id: UUID | None, asset_type: str | None
) -> list[ApiKeyJobTarget]:
    if job_type in {JobType.WORKFLOW, JobType.EVALUATION}:
        return [ApiKeyJobTarget(resource_type="flow", resource_id=flow_id, action="execute")]
    if job_type == JobType.INGESTION and asset_type == "knowledge_base" and asset_id is not None:
        return [ApiKeyJobTarget(resource_type="knowledge_base", resource_id=asset_id, action="ingest")]
    if job_type == JobType.INGESTION and asset_type == "memory_base" and asset_id is not None:
        memory_base = await session.get(MemoryBase, asset_id)
        if memory_base is None or memory_base.flow_id != flow_id:
            raise JobAuthorizationError
        knowledge_base = (
            await session.exec(
                select(KnowledgeBaseRecord).where(
                    KnowledgeBaseRecord.user_id == memory_base.user_id,
                    KnowledgeBaseRecord.name == memory_base.kb_name,
                )
            )
        ).first()
        if knowledge_base is None:
            raise JobAuthorizationError
        return [
            ApiKeyJobTarget(resource_type="flow", resource_id=flow_id, action="execute"),
            ApiKeyJobTarget(resource_type="knowledge_base", resource_id=knowledge_base.id, action="ingest"),
        ]
    raise JobAuthorizationError


async def stamp_api_key_job_authorization(
    session: AsyncSession,
    *,
    metadata: dict[str, Any],
    flow_id: UUID,
    job_type: JobType,
    asset_id: UUID | None,
    asset_type: str | None,
) -> dict[str, Any]:
    """Overwrite untrusted provenance with the selected credential's server-owned identity."""
    result = {key: value for key, value in metadata.items() if key != API_KEY_AUTHORIZATION_METADATA}
    if not current_auth_is_restricted_api_key():
        return result
    context = get_current_auth_context()
    if context is None or context.api_key_id is None:
        raise JobAuthorizationError
    key = await session.get(ApiKey, context.api_key_id)
    if key is None:
        raise JobAuthorizationError
    origin = ApiKeyJobAuthorization(
        version=1,
        api_key_id=key.id,
        actor_user_id=key.user_id,
        targets=await _targets_for_job(
            session, flow_id=flow_id, job_type=job_type, asset_id=asset_id, asset_type=asset_type
        ),
    )
    result[API_KEY_AUTHORIZATION_METADATA] = origin.model_dump(mode="json")
    return result


def preserve_api_key_job_authorization(existing: dict | None, patch: dict, *, replace: bool = False) -> dict:
    """Keep original admission provenance through progress updates, suspension, and replay."""
    previous = existing or {}
    if API_KEY_AUTHORIZATION_METADATA in patch and (
        API_KEY_AUTHORIZATION_METADATA not in previous
        or patch[API_KEY_AUTHORIZATION_METADATA] != previous[API_KEY_AUTHORIZATION_METADATA]
    ):
        raise JobAuthorizationError
    result = dict(patch) if replace else {**previous, **patch}
    if API_KEY_AUTHORIZATION_METADATA in previous:
        result[API_KEY_AUTHORIZATION_METADATA] = previous[API_KEY_AUTHORIZATION_METADATA]
    return result


async def _revalidate_job(job: Job) -> AuthCredentialContext | None:
    from langflow.services.authorization.actions import FlowAction, KnowledgeBaseAction
    from langflow.services.authorization.guards import ensure_flow_permission, ensure_knowledge_base_permission

    metadata = job.job_metadata
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        raise JobAuthorizationError
    if API_KEY_AUTHORIZATION_METADATA not in metadata:
        return None
    origin = ApiKeyJobAuthorization.model_validate(metadata[API_KEY_AUTHORIZATION_METADATA])
    async with session_scope() as session:
        key = await session.get(ApiKey, origin.api_key_id)
        if key is None or key.user_id != origin.actor_user_id or not key.is_active or _is_expired(key.expires_at):
            raise JobAuthorizationError
        if not await _scoped_key_can_authenticate(key, get_settings_service()):
            raise JobAuthorizationError
        user = await session.get(User, origin.actor_user_id)
        if (
            user is None
            or not user.is_active
            or await _external_access_ceiling_blocks_user(session, user, get_settings_service())
        ):
            raise JobAuthorizationError
        targets = await _targets_for_job(
            session, flow_id=job.flow_id, job_type=job.type, asset_id=job.asset_id, asset_type=job.asset_type
        )
        if targets != origin.targets:
            raise JobAuthorizationError
        context = AuthCredentialContext(
            method=AUTH_METHOD_API_KEY,
            api_key_id=key.id,
            api_key_source="db",  # pragma: allowlist secret
            api_key_restricted=key.permissions is not None,
            api_key_permissions=key.permissions,
        )
        user_snapshot = UserRead.model_validate(user, from_attributes=True)
        checks: list[tuple[str, dict[str, Any]]] = []
        for target in targets:
            if target.resource_type == "flow":
                flow = await session.get(Flow, target.resource_id)
                if flow is None:
                    raise JobAuthorizationError
                checks.append(
                    (
                        "flow",
                        {
                            "flow_id": flow.id,
                            "flow_user_id": flow.user_id,
                            "workspace_id": flow.workspace_id,
                            "folder_id": flow.folder_id,
                        },
                    )
                )
            else:
                knowledge_base = await session.get(KnowledgeBaseRecord, target.resource_id)
                if knowledge_base is None:
                    raise JobAuthorizationError
                checks.append(
                    (
                        "knowledge_base",
                        {
                            "kb_id": knowledge_base.id,
                            "kb_name": knowledge_base.name,
                            "kb_user_id": knowledge_base.user_id,
                        },
                    )
                )
    # Release the read transaction before enforcement can open its own policy
    # or durable audit session, including on single-connection deployments.
    previous_context = get_current_auth_context()
    set_current_auth_context(context)
    try:
        for resource_type, kwargs in checks:
            if resource_type == "flow":
                await ensure_flow_permission(user_snapshot, FlowAction.EXECUTE, **kwargs)
            else:
                await ensure_knowledge_base_permission(user_snapshot, KnowledgeBaseAction.INGEST, **kwargs)
    finally:
        set_current_auth_context(previous_context)
    return context


async def authorize_job_start(
    service: JobService, job_id: UUID, *, job: Job | None = None
) -> AuthCredentialContext | None:
    """Recheck before components run and durably refuse invalid queued admission."""
    if job is None or job.job_id != job_id:
        job = await service.get_job_by_job_id(job_id)
    if job is None:
        return None
    try:
        return await _revalidate_job(job)
    except Exception as exc:
        from langflow.services.authorization.audit import AUDIT_EVENT_DECISION, audit_decision

        await service.set_error(job_id, dict(JOB_AUTHORIZATION_ERROR))
        await service.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
        metadata = job.job_metadata if isinstance(job.job_metadata, dict) else {}
        principal = None
        details = {"event": AUDIT_EVENT_DECISION, "reason": "job_credential_authorization_invalid"}
        try:
            origin = ApiKeyJobAuthorization.model_validate(metadata.get(API_KEY_AUTHORIZATION_METADATA))
            async with session_scope() as session:
                owner_id = origin.actor_user_id if await session.get(User, origin.actor_user_id) is not None else None
            principal = AuthorizationPrincipal(actor_type="api_key", actor_id=origin.api_key_id, user_id=owner_id)
            if owner_id is None:
                details["originating_user_id"] = str(origin.actor_user_id)
        except ValueError:
            pass
        await audit_decision(
            user_id=None,
            principal=principal,
            action="job:execute",
            obj=f"job:{job_id}",
            result="deny",
            details=details,
        )
        raise JobAuthorizationError from exc

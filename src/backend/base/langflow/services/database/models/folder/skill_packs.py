"""Authorize and describe a Skill Pack through the shared type resolver."""

from uuid import UUID

from fastapi import HTTPException
from lfx.projects.lifecycle import ProjectConfigError
from lfx.projects.source_resolution import resolve_skill_pack as resolve_sources

from langflow.services.authorization import FlowAction
from langflow.services.database.models.folder.save_context import LangflowProjectSaveContext, project_error_http


async def resolve_skill_pack(session, user, project_id: UUID, *, action=FlowAction.READ):
    try:
        return await resolve_sources(
            LangflowProjectSaveContext(session, user),
            project_id,
            access="execute" if action == FlowAction.EXECUTE else "read",
        )
    except ProjectConfigError as exc:
        raise project_error_http(exc) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "Invalid Skill Pack. Review its skill definitions.") from exc

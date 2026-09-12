from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.projects import DEFAULT_PROJECT_TYPE, apply_project_config, get_project_type, registered_project_types
from sqlmodel import and_, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.database.models.deployment.orm_guards import ensure_flow_moves_allowed
from langflow.services.database.models.flow.guards import LockedFlowError, ensure_flow_unlocked
from langflow.services.database.models.flow.model import Flow

from .constants import DEFAULT_FOLDER_DESCRIPTION, DEFAULT_FOLDER_NAME
from .model import Folder


def validate_project_type(value: str | None) -> str:
    """Return a valid project type, or raise 422.

    ``None`` means the caller did not ask for a type, so it takes the default. An empty
    string is a value the caller did ask for, and it is not a valid one.
    """
    if value is None:
        return DEFAULT_PROJECT_TYPE
    if value not in registered_project_types():
        raise HTTPException(
            status_code=422,
            detail=f"Unknown project_type {value!r}. Valid types: {', '.join(registered_project_types())}.",
        )
    return value


async def write_project_config_to_flows(session: AsyncSession, project: Folder) -> list[Flow]:
    """Write the project's saved form through to its flows. Returns the flows that changed.

    ``project_config`` records what the user picked, and a folder is not something either
    runtime consults at run time. So the values a run needs are copied onto the components of
    the project's own flows, which is the artifact both langflow and lfx load.

    Scoped to the project owner, like the other flow work in this module: a non-owner editing a
    shared project must touch the owner's flows, not their own flows of the same name.
    """
    if not project.project_config:
        return []

    try:
        project_type = get_project_type(project.project_type or DEFAULT_PROJECT_TYPE)
    except ValueError:
        # A project carrying a type this instance does not know is left alone rather than
        # failing the save; the config is still recorded on the row.
        await logger.awarning(
            "Project %s has unknown project_type %r; not writing through.", project.id, project.project_type
        )
        return []

    flows = (
        await session.exec(select(Flow).where(Flow.folder_id == project.id, Flow.user_id == project.user_id))
    ).all()

    changed: list[Flow] = []
    for flow in flows:
        try:
            # A locked flow is deliberately frozen, and PATCHing one answers 423. Saving the
            # project's form is not a reason to overrule that, and it is not a reason to fail
            # the save either, so the flow is left as it is.
            ensure_flow_unlocked(flow)
        except LockedFlowError:
            await logger.ainfo("Flow %s is locked; the project's form was not written into it.", flow.id)
            continue

        write = apply_project_config(flow.data, project_type, project.project_config)
        if not write.changed:
            continue
        flow.data = write.data
        # Nothing bumps this for us: the column has a default but no onupdate, so the normal
        # flow PATCH sets it by hand too.
        flow.updated_at = datetime.now(timezone.utc)
        session.add(flow)
        changed.append(flow)

    return changed


async def create_default_folder_if_it_doesnt_exist(session: AsyncSession, user_id: UUID):
    stmt = select(Folder).where(Folder.user_id == user_id)
    folder = (await session.exec(stmt)).first()
    if not folder:
        folder = Folder(
            name=DEFAULT_FOLDER_NAME,
            user_id=user_id,
            description=DEFAULT_FOLDER_DESCRIPTION,
        )
        session.add(folder)
        await session.flush()
        await session.refresh(folder)
        flow_folder_pairs = [
            (flow_id, old_folder_id)
            for flow_id, old_folder_id in (
                await session.exec(
                    select(Flow.id, Flow.folder_id).where(
                        and_(
                            Flow.folder_id.is_(None),
                            Flow.user_id == user_id,
                        )
                    ),
                )
            ).all()
        ]
        await ensure_flow_moves_allowed(
            db=session,
            flow_folder_pairs=flow_folder_pairs,
            new_folder_id=folder.id,
        )
        await session.exec(
            update(Flow)
            .where(
                and_(
                    Flow.folder_id.is_(None),
                    Flow.user_id == user_id,
                )
            )
            .values(folder_id=folder.id, workspace_id=folder.workspace_id)
        )
    return folder


async def get_default_folder_id(session: AsyncSession, user_id: UUID):
    folder = (
        await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME, Folder.user_id == user_id))
    ).first()
    if not folder:
        folder = await get_or_create_default_folder(session, user_id)
    return folder.id

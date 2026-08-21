from uuid import UUID

from fastapi import HTTPException
from sqlmodel import and_, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.database.models.deployment.orm_guards import ensure_flow_moves_allowed
from langflow.services.database.models.flow.model import Flow

from .constants import DEFAULT_FOLDER_DESCRIPTION, DEFAULT_FOLDER_NAME
from .model import Folder

DEFAULT_PROJECT_TYPE = "flows"

# The set of valid project types belongs to the registry that lands with the lfx project-type
# work, not to this module. Until that registry exists this tuple stands in for it, so the
# public API cannot persist a value nothing will ever recognise. Replacing this with
# ``from lfx.projects import registered_project_types`` is a one-line swap, on purpose.
_REGISTERED_PROJECT_TYPES = (DEFAULT_PROJECT_TYPE, "agent-harness")


def registered_project_types() -> tuple[str, ...]:
    """Return the project types a folder may be set to."""
    return _REGISTERED_PROJECT_TYPES


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

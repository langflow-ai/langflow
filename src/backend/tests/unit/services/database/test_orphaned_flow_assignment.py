from types import SimpleNamespace
from uuid import uuid4

from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.services.database import service as database_service_module
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_db_service, session_scope
from sqlmodel import select


async def test_orphan_assignment_reserves_only_the_ownerless_starter_project(active_user, monkeypatch) -> None:
    """A user-owned same-name project remains ordinary during orphan adoption."""
    async with session_scope() as session:
        system_starter = (
            await session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME, Folder.user_id.is_(None)))
        ).first()
        assert system_starter is not None

        user_starter = Folder(name=STARTER_FOLDER_NAME, user_id=active_user.id)
        session.add(user_starter)
        await session.flush()

        system_flow = Flow(name=f"system-{uuid4()}", folder_id=system_starter.id, user_id=None)
        user_project_flow = Flow(name=f"user-project-{uuid4()}", folder_id=user_starter.id, user_id=None)
        session.add_all([system_flow, user_project_flow])
        await session.commit()

    settings = SimpleNamespace(auth_settings=SimpleNamespace(AUTO_LOGIN=True, SUPERUSER="test-superuser"))

    async def get_test_superuser(_session, _username):
        return SimpleNamespace(id=active_user.id)

    monkeypatch.setattr(database_service_module, "get_settings_service", lambda: settings)
    monkeypatch.setattr(database_service_module, "get_user_by_username", get_test_superuser)

    await get_db_service().assign_orphaned_flows_to_superuser()

    async with session_scope() as session:
        reloaded_system_flow = await session.get(Flow, system_flow.id)
        reloaded_user_project_flow = await session.get(Flow, user_project_flow.id)

    assert reloaded_system_flow is not None
    assert reloaded_system_flow.user_id is None
    assert reloaded_user_project_flow is not None
    assert reloaded_user_project_flow.user_id == active_user.id

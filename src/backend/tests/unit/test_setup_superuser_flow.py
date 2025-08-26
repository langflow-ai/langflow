import pytest
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_db_service, get_settings_service
from langflow.services.settings.constants import DEFAULT_SUPERUSER
from langflow.services.utils import initialize_services, teardown_superuser
from sqlmodel import select


@pytest.mark.asyncio
async def test_initialize_services_creates_default_superuser_when_auto_login_true(monkeypatch):
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = True

    await initialize_services()

    async with get_db_service().with_session() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True


@pytest.mark.asyncio
async def test_teardown_superuser_removes_default_if_never_logged(monkeypatch):
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False

    # Ensure default exists and has never logged in
    await initialize_services()

    async with get_db_service().with_session() as session:
        # Create default manually if missing
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        if not user:
            user = User(username=DEFAULT_SUPERUSER, password="x", is_superuser=True, is_active=True)
            session.add(user)
            await session.commit()
            await session.refresh(user)

    # Run teardown and verify removal
    async with get_db_service().with_session() as session:
        await teardown_superuser(settings, session)

    async with get_db_service().with_session() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is None

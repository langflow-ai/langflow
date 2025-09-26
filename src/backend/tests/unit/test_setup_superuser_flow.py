import pytest
from langflow.services.auth.utils import verify_password
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service
from langflow.services.utils import initialize_services, setup_superuser, teardown_superuser
from lfx.services.settings.constants import DEFAULT_SUPERUSER, DEFAULT_SUPERUSER_PASSWORD
from sqlmodel import select


@pytest.mark.asyncio
async def test_initialize_services_creates_default_superuser_when_auto_login_true(client):  # noqa: ARG001
    from langflow.services.deps import session_scope

    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = True

    await initialize_services()

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True


@pytest.mark.asyncio
async def test_teardown_superuser_removes_default_if_never_logged(client):  # noqa: ARG001
    from langflow.services.deps import session_scope

    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False

    # Ensure default exists and has never logged in
    await initialize_services()

    async with session_scope() as session:
        # Create default manually if missing
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        if not user:
            user = User(
                username=DEFAULT_SUPERUSER,
                password=DEFAULT_SUPERUSER_PASSWORD.get_secret_value(),
                is_superuser=True,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        # Ensure the user is treated as "never logged in" so teardown removes it
        user.last_login_at = None
        user.is_superuser = True
        await session.commit()

    # Run teardown and verify removal
    async with session_scope() as session:
        await teardown_superuser(settings, session)

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is None


@pytest.mark.asyncio
async def test_teardown_superuser_preserves_logged_in_default(client):  # noqa: ARG001
    """Test that teardown preserves default superuser if they have logged in."""
    from datetime import datetime, timezone

    from langflow.services.deps import session_scope

    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False

    # Ensure default exists
    await initialize_services()

    async with session_scope() as session:
        # Create default manually if missing and mark as logged in
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        if not user:
            user = User(
                username=DEFAULT_SUPERUSER,
                password=DEFAULT_SUPERUSER_PASSWORD.get_secret_value(),
                is_superuser=True,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # Mark user as having logged in
        user.last_login_at = datetime.now(timezone.utc)
        user.is_superuser = True
        await session.commit()

    # Run teardown and verify user is preserved
    async with session_scope() as session:
        await teardown_superuser(settings, session)

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True


@pytest.mark.asyncio
async def test_setup_superuser_with_no_configured_credentials(client):  # noqa: ARG001
    """Test setup_superuser behavior when no superuser credentials are configured."""
    from langflow.services.deps import session_scope

    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = ""
    # Reset password to empty
    settings.auth_settings.SUPERUSER_PASSWORD = ""

    async with session_scope() as session:
        # This should create a default superuser since no credentials are provided
        await setup_superuser(settings, session)

        # Verify default superuser was created
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True


@pytest.mark.asyncio
async def test_setup_superuser_with_custom_credentials(client):  # noqa: ARG001
    """Test setup_superuser behavior with custom superuser credentials."""
    from langflow.services.deps import session_scope
    from pydantic import SecretStr

    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = "custom_admin"
    settings.auth_settings.SUPERUSER_PASSWORD = SecretStr("custom_password")

    # Clean DB state to avoid interference from previous tests
    async with session_scope() as session:
        # Ensure default can be removed by teardown (last_login_at must be None)
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        default_user = (await session.exec(stmt)).first()
        if default_user:
            default_user.last_login_at = None
            await session.commit()
            await teardown_superuser(settings, session)

        # Remove any pre-existing custom_admin user
        stmt = select(User).where(User.username == "custom_admin")
        existing_custom = (await session.exec(stmt)).first()
        if existing_custom:
            await session.delete(existing_custom)
            await session.commit()

    async with session_scope() as session:
        await setup_superuser(settings, session)

        # Verify custom superuser was created
        stmt = select(User).where(User.username == "custom_admin")
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True
        # Password should be hashed (not equal to the raw) and verify correctly
        assert user.password != "custom_password"  # noqa: S105
        assert verify_password("custom_password", user.password) is True

        # Verify default superuser was not created
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        default_user = (await session.exec(stmt)).first()
        assert default_user is None

        # Settings credentials should be scrubbed after setup
        assert settings.auth_settings.SUPERUSER_PASSWORD.get_secret_value() == ""

    # Cleanup: remove custom_admin to not leak state across tests
    async with session_scope() as session:
        stmt = select(User).where(User.username == "custom_admin")
        created_custom = (await session.exec(stmt)).first()
        if created_custom:
            await session.delete(created_custom)
            await session.commit()

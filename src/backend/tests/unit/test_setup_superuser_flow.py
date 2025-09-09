from pydantic import SecretStr
import pytest
from langflow.services.auth.utils import verify_password
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_db_service, get_settings_service
from langflow.services.settings.constants import DEFAULT_SUPERUSER, DEFAULT_SUPERUSER_PASSWORD
from langflow.services.utils import initialize_services, setup_superuser, teardown_superuser
from sqlmodel import select


@pytest.mark.asyncio
async def test_initialize_services_creates_default_superuser_when_auto_login_true(async_session):
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = True

    # Test setup_superuser directly with our session
    await setup_superuser(settings, async_session)

    stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
    user = (await async_session.exec(stmt)).first()
    assert user is not None
    assert user.is_superuser is True


@pytest.mark.asyncio
async def test_teardown_superuser_removes_default_if_never_logged(async_session):
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False

    # Create default user with never logged in status
    user = User(
        username=DEFAULT_SUPERUSER,
        password=DEFAULT_SUPERUSER_PASSWORD.get_secret_value(),
        is_superuser=True,
        is_active=True,
        last_login_at=None,  # Never logged in
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    # Run teardown and verify removal
    await teardown_superuser(settings, async_session)

    stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
    user = (await async_session.exec(stmt)).first()
    assert user is None


@pytest.mark.asyncio
async def test_teardown_superuser_preserves_logged_in_default(async_session):
    """Test that teardown preserves default superuser if they have logged in."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False

    from datetime import datetime, timezone

    # Create default user marked as having logged in
    user = User(
        username=DEFAULT_SUPERUSER,
        password=DEFAULT_SUPERUSER_PASSWORD.get_secret_value(),
        is_superuser=True,
        is_active=True,
        last_login_at=datetime.now(timezone.utc),  # Has logged in
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    # Run teardown and verify user is preserved
    await teardown_superuser(settings, async_session)

    stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
    user = (await async_session.exec(stmt)).first()
    assert user is not None
    assert user.is_superuser is True


@pytest.mark.asyncio
async def test_setup_superuser_with_no_configured_credentials(async_session):
    """Test setup_superuser behavior when no superuser credentials are configured."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = ""
    # Reset password to empty
    settings.auth_settings.SUPERUSER_PASSWORD = SecretStr("")

    # This should create a default superuser since no credentials are provided
    await setup_superuser(settings, async_session)

    # Verify default superuser was created
    stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
    user = (await async_session.exec(stmt)).first()
    assert user is not None
    assert user.is_superuser is True


@pytest.mark.asyncio
async def test_setup_superuser_with_custom_credentials(async_session):
    """Test setup_superuser behavior with custom superuser credentials."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = "custom_admin"
    from pydantic import SecretStr

    settings.auth_settings.SUPERUSER_PASSWORD = SecretStr("custom_password")

    # Clean DB state to avoid interference from previous tests
    # Remove any pre-existing custom_admin user
    stmt = select(User).where(User.username == "custom_admin")
    existing_custom = (await async_session.exec(stmt)).first()
    if existing_custom:
        await async_session.delete(existing_custom)
        await async_session.commit()

    await setup_superuser(settings, async_session)

    # Verify custom superuser was created
    stmt = select(User).where(User.username == "custom_admin")
    user = (await async_session.exec(stmt)).first()
    assert user is not None
    assert user.is_superuser is True
    # Password should be hashed (not equal to the raw) and verify correctly
    assert user.password != "custom_password"  # noqa: S105
    assert verify_password("custom_password", user.password) is True

    # Verify default superuser was not created
    stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
    default_user = (await async_session.exec(stmt)).first()
    assert default_user is None

    # Settings credentials should be scrubbed after setup
    assert settings.auth_settings.SUPERUSER_PASSWORD.get_secret_value() == ""

    # Cleanup: remove custom_admin to not leak state across tests
    stmt = select(User).where(User.username == "custom_admin")
    created_custom = (await async_session.exec(stmt)).first()
    if created_custom:
        await async_session.delete(created_custom)
        await async_session.commit()

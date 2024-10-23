from loguru import logger
from sqlmodel import Session, select

from langflow.services.auth.utils import create_super_user, verify_password
from langflow.services.cache.factory import CacheServiceFactory
from langflow.services.database.utils import initialize_database
from langflow.services.schema import ServiceType
from langflow.services.settings.constants import DEFAULT_SUPERUSER, DEFAULT_SUPERUSER_PASSWORD

from .deps import get_db_service, get_service, get_session, get_settings_service


def get_or_create_super_user(session: Session, username, password, is_default):
    from langflow.services.database.models.user.model import User

    user = session.exec(select(User).where(User.username == username)).first()

    if user and user.is_superuser:
        return None  # Superuser already exists

    if user and is_default:
        if user.is_superuser:
            if verify_password(password, user.password):
                return None
            # Superuser exists but password is incorrect
            # which means that the user has changed the
            # base superuser credentials.
            # This means that the user has already created
            # a superuser and changed the password in the UI
            # so we don't need to do anything.
            logger.debug(
                "Superuser exists but password is incorrect. "
                "This means that the user has changed the "
                "base superuser credentials."
            )
            return None
        logger.debug("User with superuser credentials exists but is not a superuser.")
        return None

    if user:
        if verify_password(password, user.password):
            msg = "User with superuser credentials exists but is not a superuser."
            raise ValueError(msg)
        msg = "Incorrect superuser credentials"
        raise ValueError(msg)

    if is_default:
        logger.debug("Creating default superuser.")
    else:
        logger.debug("Creating superuser.")
    try:
        return create_super_user(username, password, db=session)
    except Exception as exc:  # noqa: BLE001
        if "UNIQUE constraint failed: user.username" in str(exc):
            # This is to deal with workers running this
            # at startup and trying to create the superuser
            # at the same time.
            logger.opt(exception=True).debug("Superuser already exists.")
            return None
        logger.opt(exception=True).debug("Error creating superuser.")


def setup_superuser(settings_service, session: Session) -> None:
    if settings_service.auth_settings.AUTO_LOGIN:
        logger.debug("AUTO_LOGIN is set to True. Creating default superuser.")
    else:
        # Remove the default superuser if it exists
        teardown_superuser(settings_service, session)

    username = settings_service.auth_settings.SUPERUSER
    password = settings_service.auth_settings.SUPERUSER_PASSWORD

    is_default = (username == DEFAULT_SUPERUSER) and (password == DEFAULT_SUPERUSER_PASSWORD)

    try:
        user = get_or_create_super_user(session=session, username=username, password=password, is_default=is_default)
        if user is not None:
            logger.debug("Superuser created successfully.")
    except Exception as exc:
        logger.exception(exc)
        msg = "Could not create superuser. Please create a superuser manually."
        raise RuntimeError(msg) from exc
    finally:
        settings_service.auth_settings.reset_credentials()


def teardown_superuser(settings_service, session) -> None:
    """Teardown the superuser."""
    # If AUTO_LOGIN is True, we will remove the default superuser
    # from the database.

    if not settings_service.auth_settings.AUTO_LOGIN:
        try:
            logger.debug("AUTO_LOGIN is set to False. Removing default superuser if exists.")
            username = DEFAULT_SUPERUSER
            from langflow.services.database.models.user.model import User

            user = session.exec(select(User).where(User.username == username)).first()
            # Check if super was ever logged in, if not delete it
            # if it has logged in, it means the user is using it to login
            if user and user.is_superuser is True and not user.last_login_at:
                session.delete(user)
                session.commit()
                logger.debug("Default superuser removed successfully.")

        except Exception as exc:
            logger.exception(exc)
            session.rollback()
            msg = "Could not remove default superuser."
            raise RuntimeError(msg) from exc


async def teardown_services() -> None:
    """Teardown all the services."""
    try:
        teardown_superuser(get_settings_service(), next(get_session()))
    except Exception as exc:  # noqa: BLE001
        logger.exception(exc)
    try:
        from langflow.services.manager import service_manager

        await service_manager.teardown()
    except Exception as exc:  # noqa: BLE001
        logger.exception(exc)


def initialize_settings_service() -> None:
    """Initialize the settings manager."""
    from langflow.services.settings import factory as settings_factory

    get_service(ServiceType.SETTINGS_SERVICE, settings_factory.SettingsServiceFactory())


def initialize_session_service() -> None:
    """Initialize the session manager."""
    from langflow.services.cache import factory as cache_factory
    from langflow.services.session import factory as session_service_factory

    initialize_settings_service()

    get_service(
        ServiceType.CACHE_SERVICE,
        cache_factory.CacheServiceFactory(),
    )

    get_service(
        ServiceType.SESSION_SERVICE,
        session_service_factory.SessionServiceFactory(),
    )


def initialize_services(*, fix_migration: bool = False) -> None:
    """Initialize all the services needed."""
    # Test cache connection
    get_service(ServiceType.CACHE_SERVICE, default=CacheServiceFactory())
    # Setup the superuser
    initialize_database(fix_migration=fix_migration)
    setup_superuser(get_service(ServiceType.SETTINGS_SERVICE), next(get_session()))
    try:
        get_db_service().migrate_flows_if_auto_login()
    except Exception as exc:
        msg = "Error migrating flows"
        logger.exception(msg)
        raise RuntimeError(msg) from exc

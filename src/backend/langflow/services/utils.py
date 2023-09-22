from langflow.services.auth.utils import create_super_user
from langflow.services.database.utils import initialize_database
from langflow.services.manager import service_manager
from langflow.services.schema import ServiceType
from langflow.services.settings.constants import (
    DEFAULT_SUPERUSER,
    DEFAULT_SUPERUSER_PASSWORD,
)
from .getters import get_session, get_settings_service
from loguru import logger


def setup_superuser(settings_service, session):
    """
    Setup the superuser.
    """
    # We will use the SUPERUSER and SUPERUSER_PASSWORD
    # vars on settings_manager.auth_settings to create the superuser
    # if it does not exist.
    if settings_service.auth_settings.AUTO_LOGIN:
        logger.debug("AUTO_LOGIN is set to True. Creating default superuser.")

    username = settings_service.auth_settings.SUPERUSER
    password = settings_service.auth_settings.SUPERUSER_PASSWORD
    if username == DEFAULT_SUPERUSER and password == DEFAULT_SUPERUSER_PASSWORD:
        logger.debug("Default superuser credentials detected.")
        logger.debug("Creating default superuser.")
    else:
        logger.debug("Creating superuser.")

    try:
        from langflow.services.database.models.user.user import User

        user = session.query(User).filter(User.username == username).first()
        if user and user.is_superuser is True:
            return
    except Exception as exc:
        logger.exception(exc)
        raise RuntimeError(
            "Could not create superuser. Please create a superuser manually."
        ) from exc
    try:
        # create superuser
        create_super_user(db=session, username=username, password=password)
    except Exception as exc:
        logger.exception(exc)
        raise RuntimeError(
            "Could not create superuser. Please create a superuser manually."
        ) from exc
    # reset superuser credentials
    settings_service.auth_settings.reset_credentials()
    logger.debug("Superuser created successfully.")


def teardown_superuser(settings_service, session):
    """
    Teardown the superuser.
    """
    # If AUTO_LOGIN is True, we will remove the default superuser
    # from the database.

    if settings_service.auth_settings.AUTO_LOGIN:
        logger.debug("AUTO_LOGIN is set to True. Removing default superuser.")
        username = settings_service.auth_settings.SUPERUSER
        from langflow.services.database.models.user.user import User

        user = session.query(User).filter(User.username == username).first()
        if user and user.is_superuser:
            session.delete(user)
            session.commit()
            logger.debug("Default superuser removed successfully.")
        else:
            logger.debug("Default superuser not found.")


def teardown_services():
    """
    Teardown all the services.
    """
    try:
        teardown_superuser(get_settings_service(), next(get_session()))
        service_manager.teardown()
    except Exception as exc:
        logger.exception(exc)


def initialize_settings_service():
    """
    Initialize the settings manager.
    """
    from langflow.services.settings import factory as settings_factory

    service_manager.register_factory(settings_factory.SettingsServiceFactory())


def initialize_session_service():
    """
    Initialize the session manager.
    """
    from langflow.services.session import factory as session_service_factory  # type: ignore
    from langflow.services.cache import factory as cache_factory

    initialize_settings_service()

    service_manager.register_factory(
        cache_factory.CacheServiceFactory(), dependencies=[ServiceType.SETTINGS_SERVICE]
    )

    service_manager.register_factory(
        session_service_factory.SessionServiceFactory(),
        dependencies=[ServiceType.CACHE_SERVICE],
    )


def initialize_services():
    """
    Initialize all the services needed.
    """
    from langflow.services.database import factory as database_factory
    from langflow.services.cache import factory as cache_factory
    from langflow.services.chat import factory as chat_factory
    from langflow.services.settings import factory as settings_factory
    from langflow.services.auth import factory as auth_factory
    from langflow.services.task import factory as task_factory
    from langflow.services.session import factory as session_service_factory  # type: ignore

    service_manager.register_factory(settings_factory.SettingsServiceFactory())
    service_manager.register_factory(
        auth_factory.AuthServiceFactory(), dependencies=[ServiceType.SETTINGS_SERVICE]
    )
    service_manager.register_factory(
        database_factory.DatabaseServiceFactory(),
        dependencies=[ServiceType.SETTINGS_SERVICE],
    )
    service_manager.register_factory(
        cache_factory.CacheServiceFactory(), dependencies=[ServiceType.SETTINGS_SERVICE]
    )
    service_manager.register_factory(chat_factory.ChatServiceFactory())

    service_manager.register_factory(task_factory.TaskServiceFactory())

    service_manager.register_factory(
        session_service_factory.SessionServiceFactory(),
        dependencies=[ServiceType.CACHE_SERVICE],
    )
    # Test cache connection
    service_manager.get(ServiceType.CACHE_SERVICE)
    # Test database connection
    service_manager.get(ServiceType.DATABASE_SERVICE)
    # Setup the superuser
    initialize_database()
    session = next(get_session())
    setup_superuser(service_manager.get(ServiceType.SETTINGS_SERVICE), session)

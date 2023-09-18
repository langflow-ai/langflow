from langflow.services.auth.utils import create_super_user
from langflow.services.settings.constants import (
    DEFAULT_SUPERUSER,
    DEFAULT_SUPERUSER_PASSWORD,
)
from .getters import get_session, get_settings_manager
from loguru import logger


def setup_superuser():
    """
    Setup the superuser.
    """
    # We will use the FIRST_SUPERUSER and FIRST_SUPERUSER_PASSWORD
    # vars on settings_manager.auth_settings to create the superuser
    # if it does not exist.
    settings_manager = get_settings_manager()
    session = next(get_session())
    username = settings_manager.auth_settings.SUPERUSER
    password = settings_manager.auth_settings.SUPERUSER_PASSWORD
    if username == DEFAULT_SUPERUSER and password == DEFAULT_SUPERUSER_PASSWORD:
        logger.debug(
            "Using default superuser credentials. Please change them in production."
        )
        return

    try:
        from langflow.services.database.models.user.user import User

        user = session.query(User).filter(User.username == username).first()
        if user and user.is_superuser:
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
    settings_manager.auth_settings.reset_credentials()
    logger.debug("Superuser created successfully.")

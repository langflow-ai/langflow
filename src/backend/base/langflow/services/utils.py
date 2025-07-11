from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import delete
from sqlalchemy import exc as sqlalchemy_exc
from sqlmodel import col, select

from langflow.services.auth.utils import create_super_user, verify_password
from langflow.services.cache.base import ExternalAsyncBaseCacheService
from langflow.services.cache.factory import CacheServiceFactory
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.database.utils import initialize_database
from langflow.services.schema import ServiceType
from langflow.services.settings.constants import DEFAULT_SUPERUSER, DEFAULT_SUPERUSER_PASSWORD

from .deps import get_db_service, get_service, get_settings_service

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.settings.manager import SettingsService


async def get_or_create_super_user(session: AsyncSession, username, password, is_default):
    from langflow.services.database.models.user.model import User

    stmt = select(User).where(User.username == username)
    user = (await session.exec(stmt)).first()

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
    return await create_super_user(username, password, db=session)


async def setup_superuser(settings_service, session: AsyncSession) -> None:
    if settings_service.auth_settings.AUTO_LOGIN:
        logger.debug("AUTO_LOGIN is set to True. Creating default superuser.")
    else:
        # Remove the default superuser if it exists
        await teardown_superuser(settings_service, session)

    username = settings_service.auth_settings.SUPERUSER
    password = settings_service.auth_settings.SUPERUSER_PASSWORD

    is_default = (username == DEFAULT_SUPERUSER) and (password == DEFAULT_SUPERUSER_PASSWORD)

    try:
        user = await get_or_create_super_user(
            session=session, username=username, password=password, is_default=is_default
        )
        if user is not None:
            logger.debug("Superuser created successfully.")
    except Exception as exc:
        logger.exception(exc)
        msg = "Could not create superuser. Please create a superuser manually."
        raise RuntimeError(msg) from exc
    finally:
        settings_service.auth_settings.reset_credentials()


async def teardown_superuser(settings_service, session: AsyncSession) -> None:
    """Teardown the superuser."""
    # If AUTO_LOGIN is True, we will remove the default superuser
    # from the database.

    if not settings_service.auth_settings.AUTO_LOGIN:
        try:
            logger.debug("AUTO_LOGIN is set to False. Removing default superuser if exists.")
            username = DEFAULT_SUPERUSER
            from langflow.services.database.models.user.model import User

            stmt = select(User).where(User.username == username)
            user = (await session.exec(stmt)).first()
            # Check if super was ever logged in, if not delete it
            # if it has logged in, it means the user is using it to login
            if user and user.is_superuser is True and not user.last_login_at:
                await session.delete(user)
                await session.commit()
                logger.debug("Default superuser removed successfully.")

        except Exception as exc:
            logger.exception(exc)
            await session.rollback()
            msg = "Could not remove default superuser."
            raise RuntimeError(msg) from exc


async def teardown_services() -> None:
    """Teardown all the services."""
    async with get_db_service().with_session() as session:
        await teardown_superuser(get_settings_service(), session)

    from langflow.services.manager import service_manager

    await service_manager.teardown()


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


async def clean_transactions(settings_service: SettingsService, session: AsyncSession) -> None:
    """Clean up old transactions from the database.

    This function deletes transactions that exceed the maximum number to keep (configured in settings).
    It orders transactions by timestamp descending and removes the oldest ones beyond the limit.

    Args:
        settings_service: The settings service containing configuration like max_transactions_to_keep
        session: The database session to use for the deletion
    """
    try:
        # Delete transactions using bulk delete
        delete_stmt = delete(TransactionTable).where(
            col(TransactionTable.id).in_(
                select(TransactionTable.id)
                .order_by(col(TransactionTable.timestamp).desc())
                .offset(settings_service.settings.max_transactions_to_keep)
            )
        )

        await session.exec(delete_stmt)
        await session.commit()
        logger.debug("Successfully cleaned up old transactions")
    except (sqlalchemy_exc.SQLAlchemyError, asyncio.TimeoutError) as exc:
        logger.error(f"Error cleaning up transactions: {exc!s}")
        await session.rollback()
        # Don't re-raise since this is a cleanup task


async def clean_vertex_builds(settings_service: SettingsService, session: AsyncSession) -> None:
    """Clean up old vertex builds from the database.

    This function deletes vertex builds that exceed the maximum number to keep (configured in settings).
    It orders vertex builds by timestamp descending and removes the oldest ones beyond the limit.

    Args:
        settings_service: The settings service containing configuration like max_vertex_builds_to_keep
        session: The database session to use for the deletion
    """
    try:
        # Delete vertex builds using bulk delete
        delete_stmt = delete(VertexBuildTable).where(
            col(VertexBuildTable.id).in_(
                select(VertexBuildTable.id)
                .order_by(col(VertexBuildTable.timestamp).desc())
                .offset(settings_service.settings.max_vertex_builds_to_keep)
            )
        )

        await session.exec(delete_stmt)
        await session.commit()
        logger.debug("Successfully cleaned up old vertex builds")
    except (sqlalchemy_exc.SQLAlchemyError, asyncio.TimeoutError) as exc:
        logger.error(f"Error cleaning up vertex builds: {exc!s}")
        await session.rollback()
        # Don't re-raise since this is a cleanup task


async def initialize_services(*, fix_migration: bool = False) -> None:
    """Initialize all the services needed."""
    cache_service = get_service(ServiceType.CACHE_SERVICE, default=CacheServiceFactory())
    # Test external cache connection
    if isinstance(cache_service, ExternalAsyncBaseCacheService) and not (await cache_service.is_connected()):
        msg = "Cache service failed to connect to external database"
        raise ConnectionError(msg)

    # Setup the superuser
    await initialize_database(fix_migration=fix_migration)
    db_service = get_db_service()
    await db_service.initialize_alembic_log_file()
    async with db_service.with_session() as session:
        settings_service = get_service(ServiceType.SETTINGS_SERVICE)
        await setup_superuser(settings_service, session)
    try:
        await get_db_service().assign_orphaned_flows_to_superuser()
    except sqlalchemy_exc.IntegrityError as exc:
        logger.warning(f"Error assigning orphaned flows to the superuser: {exc!s}")
    await clean_transactions(settings_service, session)
    await clean_vertex_builds(settings_service, session)

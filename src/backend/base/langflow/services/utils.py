from __future__ import annotations

import asyncio
from enum import Enum
from importlib import import_module
from pathlib import Path
from secrets import token_urlsafe
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.settings.constants import (
    DEFAULT_SUPERUSER,
    LEGACY_DEFAULT_SUPERUSER_PASSWORD,
)
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlalchemy import delete
from sqlalchemy import exc as sqlalchemy_exc
from sqlmodel import col, select

from langflow.services.cache.base import ExternalAsyncBaseCacheService
from langflow.services.cache.factory import CacheServiceFactory
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.database.utils import initialize_database
from langflow.services.schema import ServiceType

from .deps import get_auth_service, get_db_service, get_service, get_settings_service, session_scope

if TYPE_CHECKING:
    from lfx.services.settings.manager import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession


class SetupSuperuserResult(str, Enum):
    """Distinct outcomes from ``setup_superuser`` (AUTO_LOGIN and credential paths)."""

    AUTO_LOGIN_INITIALIZED = "auto_login_initialized"
    AUTO_LOGIN_ALREADY_SATISFIED = "auto_login_already_satisfied"
    AUTO_LOGIN_LOCK_TIMEOUT_SUPERUSER_PRESENT = "auto_login_lock_timeout_superuser_present"
    SUPERUSER_CREATED = "superuser_created"
    SUPERUSER_UNCHANGED = "superuser_unchanged"


def _secret_value(secret) -> str:
    if not secret:
        return ""
    if hasattr(secret, "get_secret_value"):
        return secret.get_secret_value()
    return str(secret)


def get_auto_login_superuser_password(auth_settings) -> str:
    configured_password = _secret_value(auth_settings.SUPERUSER_PASSWORD)
    legacy_password = LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value()
    if configured_password and configured_password != legacy_password:
        return configured_password
    return token_urlsafe(32)


async def _get_superuser_by_username(session: AsyncSession, username: str):
    from langflow.services.database.models.user.model import User

    stmt = select(User).where(
        User.username == username,
        User.is_superuser == True,  # noqa: E712
    )
    result = await session.exec(stmt)
    return result.first()


async def _rotate_legacy_default_superuser_password(session: AsyncSession, user, replacement_password: str) -> bool:
    legacy_password = LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value()
    if not legacy_password or not user.password:
        return False

    auth = get_auth_service()
    if not auth.verify_password(legacy_password, user.password):
        return False

    user.password = auth.get_password_hash(replacement_password)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    await logger.awarning("Rotated legacy default superuser password.")
    return True


async def get_or_create_super_user(
    session: AsyncSession,
    username,
    password,
    is_default,
    *,
    rotate_legacy_default_password: bool = False,
):
    from langflow.services.database.models.user.model import User

    stmt = select(User).where(User.username == username)
    result = await session.exec(stmt)
    user = result.first()

    auth = get_auth_service()
    if user and user.is_superuser:
        if rotate_legacy_default_password:
            await _rotate_legacy_default_superuser_password(session, user, password)
        return None  # Superuser already exists

    if user and is_default:
        if user.is_superuser:
            if auth.verify_password(password, user.password):
                return None
            # Superuser exists but password is incorrect
            # which means that the user has changed the
            # base superuser credentials.
            # This means that the user has already created
            # a superuser and changed the password in the UI
            # so we don't need to do anything.
            await logger.adebug(
                "Superuser exists but password is incorrect. "
                "This means that the user has changed the "
                "base superuser credentials."
            )
            return None
        logger.debug("User with superuser credentials exists but is not a superuser.")
        return None

    if user:
        if auth.verify_password(password, user.password):
            msg = "User with superuser credentials exists but is not a superuser."
            raise ValueError(msg)
        msg = "Incorrect superuser credentials"
        raise ValueError(msg)

    if is_default:
        logger.debug("Creating default superuser.")
    else:
        logger.debug("Creating superuser.")
    return await auth.create_super_user(username, password, db=session)


async def setup_superuser(settings_service: SettingsService, session: AsyncSession) -> SetupSuperuserResult:
    if settings_service.auth_settings.AUTO_LOGIN:
        await logger.adebug("AUTO_LOGIN is set to True. Creating default superuser with full initialization.")
        # Use file lock to prevent race conditions in multi-worker environments
        from tempfile import gettempdir

        from filelock import FileLock

        username = settings_service.auth_settings.SUPERUSER or DEFAULT_SUPERUSER
        configured_password = _secret_value(settings_service.auth_settings.SUPERUSER_PASSWORD)
        if configured_password == LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value():
            await logger.awarning(
                "Ignoring legacy default LANGFLOW_SUPERUSER_PASSWORD in AUTO_LOGIN mode; "
                "generated a random bootstrap password instead."
            )
        password = get_auto_login_superuser_password(settings_service.auth_settings)

        # Use file lock similar to starter projects
        lock_file = Path(gettempdir()) / "langflow_auto_login_superuser.lock"
        lock = FileLock(lock_file, timeout=5)

        try:
            with lock:
                # Create user and initialize all related resources
                super_user = await get_or_create_super_user(
                    session,
                    username,
                    password,
                    is_default=True,
                    rotate_legacy_default_password=True,
                )
                if super_user:  # Only initialize if user was created
                    from langflow.initial_setup.setup import get_or_create_default_folder
                    from langflow.services.deps import get_variable_service

                    # Recover MCP server config files orphaned when DB was reset but LANGFLOW_CONFIG_DIR was kept.
                    await migrate_orphaned_mcp_servers_config(session, settings_service, super_user)

                    await get_variable_service().initialize_user_variables(super_user.id, session)

                    # NOTE: Agentic variables are initialized separately in preload or main lifespan
                    # via initialize_agentic_global_variables() which handles all users at once.
                    # Do NOT initialize them here to avoid conflicts during preload.

                    _ = await get_or_create_default_folder(session, super_user.id)
                    await logger.adebug("Auto-login superuser initialized successfully")
                    return SetupSuperuserResult.AUTO_LOGIN_INITIALIZED
                existing_superuser = await _get_superuser_by_username(session, username)
                if existing_superuser is None:
                    msg = "AUTO_LOGIN is enabled but the configured bootstrap user is not a superuser."
                    await logger.aerror(msg)
                    raise RuntimeError(msg)
                return SetupSuperuserResult.AUTO_LOGIN_ALREADY_SATISFIED
        except TimeoutError as exc:
            # Another worker may be handling it - but a stale/abandoned lock or dead holder
            # yields the same timeout with no initialization.
            await logger.awarning(
                "Timed out waiting for AUTO_LOGIN superuser initialization lock "
                "(another worker may hold it, or the lock file may be stale). "
                "Verifying whether the default superuser exists.",
            )
            exists = (await _get_superuser_by_username(session, username)) is not None
            if not exists:
                msg = (
                    "AUTO_LOGIN is enabled but the default superuser was not initialized: "
                    "could not acquire the initialization lock within the timeout and no matching "
                    "superuser exists in the database. Retry startup or create a superuser manually."
                )
                await logger.aerror(msg)
                raise RuntimeError(msg) from exc
            return SetupSuperuserResult.AUTO_LOGIN_LOCK_TIMEOUT_SUPERUSER_PRESENT
        finally:
            settings_service.auth_settings.reset_credentials()
    # Remove the default superuser if it exists
    await teardown_superuser(settings_service, session)
    # If AUTO_LOGIN is disabled, require configured credentials.
    username = settings_service.auth_settings.SUPERUSER or DEFAULT_SUPERUSER
    password = _secret_value(settings_service.auth_settings.SUPERUSER_PASSWORD)

    await logger.adebug(f"Setup superuser: username={username}, has_password={bool(password)}")

    if not username or not password:
        msg = "Username and password must be set"
        await logger.aerror(f"Missing credentials: username={username}, password={'set' if password else 'not set'}")
        raise ValueError(msg)

    if password == LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value():
        msg = "LANGFLOW_SUPERUSER_PASSWORD cannot use the legacy default password"
        await logger.aerror(msg)
        raise ValueError(msg)

    is_default = (username == DEFAULT_SUPERUSER) and (password == LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value())

    try:
        await logger.adebug(f"Creating/getting superuser: username={username}, is_default={is_default}")
        user = await get_or_create_super_user(
            session=session,
            username=username,
            password=password,
            is_default=is_default,
            rotate_legacy_default_password=True,
        )
        if user is not None:
            await logger.adebug("Superuser created successfully.")
            outcome = SetupSuperuserResult.SUPERUSER_CREATED
            # When the default superuser is recreated (e.g. after a DB reset in
            # AUTO_LOGIN mode) the per-user MCP servers config file saved under the
            # previous UUID becomes orphaned on disk. Best-effort recover it so
            # users don't lose their MCP server configuration across restarts.
            if is_default and settings_service.auth_settings.AUTO_LOGIN:
                await migrate_orphaned_mcp_servers_config(session, settings_service, user)
        else:
            outcome = SetupSuperuserResult.SUPERUSER_UNCHANGED
    except Exception as exc:
        await logger.aexception(f"Failed to create superuser: {exc}")
        msg = "Could not create superuser. Please create a superuser manually."
        raise RuntimeError(msg) from exc
    else:
        return outcome
    finally:
        # Scrub credentials from in-memory settings after setup
        settings_service.auth_settings.reset_credentials()


async def migrate_orphaned_mcp_servers_config(
    session: AsyncSession,
    settings_service: SettingsService,
    current_user,
) -> bool:
    """Best-effort recovery of MCP servers config files orphaned by a DB reset.

    The MCP servers config is persisted on disk at
    ``{config_dir}/{user_id}/_mcp_servers_{user_id}.json`` and tracked in the DB
    via a ``File`` row. When Langflow starts with a fresh database but the same
    config directory (common in containerized deployments without a persisted DB
    volume), the default superuser is recreated with a new UUID and the
    previously saved MCP config files become unreachable.

    Recovery rules (intentionally conservative to avoid importing another user's
    config — MCP server entries can contain ``env`` and ``headers`` auth material):

    * If the new user already has an MCP config file on disk without a matching
      ``File`` row, re-register the row (self-heal a partial previous migration).
    * If exactly one orphaned ``_mcp_servers_{uuid}.json`` is found in the config
      directory, migrate it.
    * If multiple orphans are found, skip and log — we can't safely identify the
      previous default superuser's file without extra metadata, so leave manual
      recovery to the operator.

    Returns True when a file was migrated or a missing DB row was restored.
    """
    from uuid import UUID

    import aiofiles
    import anyio

    from langflow.services.database.models.file.model import File as UserFile

    try:
        config_dir_value = settings_service.settings.config_dir
        if not config_dir_value:
            return False

        config_dir = Path(config_dir_value)
        if not config_dir.exists() or not config_dir.is_dir():
            return False

        name_without_ext = f"_mcp_servers_{current_user.id}"
        existing_stmt = (
            select(UserFile).where(UserFile.user_id == current_user.id).where(UserFile.name == name_without_ext)
        )
        if (await session.exec(existing_stmt)).first() is not None:
            return False

        current_user_dir = str(current_user.id)
        new_dir = config_dir / current_user_dir
        new_filename = f"_mcp_servers_{current_user.id}.json"
        new_file_path = new_dir / new_filename
        db_path = f"{current_user.id}/{new_filename}"

        # Case 1: a previous migration attempt copied the file but failed before
        # committing the DB row. Re-register the existing file instead of
        # returning early and leaving the user with an invisible config.
        if new_file_path.exists():
            try:
                size = new_file_path.stat().st_size
            except OSError as exc:
                await logger.awarning(
                    "Cannot stat existing MCP config %s while self-healing DB row: %s",
                    new_file_path,
                    exc,
                )
                return False
            session.add(UserFile(user_id=current_user.id, name=name_without_ext, path=db_path, size=size))
            await session.commit()
            await logger.ainfo(
                "Restored missing MCP servers config DB row for user %s from existing file %s",
                current_user.id,
                new_file_path,
            )
            return True

        def _find_orphans() -> list[tuple[float, Path]]:
            orphans: list[tuple[float, Path]] = []
            for entry in config_dir.iterdir():
                if not entry.is_dir() or entry.name == current_user_dir:
                    continue
                try:
                    UUID(entry.name)
                except ValueError:
                    continue
                mcp_path = entry / f"_mcp_servers_{entry.name}.json"
                if mcp_path.is_file():
                    try:
                        mtime = mcp_path.stat().st_mtime
                    except OSError:
                        continue
                    orphans.append((mtime, mcp_path))
            return orphans

        orphans = await anyio.to_thread.run_sync(_find_orphans)
        if not orphans:
            return False

        if len(orphans) > 1:
            orphan_paths = ", ".join(str(p) for _, p in sorted(orphans, key=lambda i: i[0], reverse=True))
            await logger.awarning(
                "Found %d orphaned MCP servers config files in %s; skipping automatic "
                "migration to avoid restoring the wrong one. Move the intended file to "
                "%s to recover. Candidates: %s",
                len(orphans),
                config_dir,
                new_file_path,
                orphan_paths,
            )
            return False

        _, orphan_path = orphans[0]

        async with aiofiles.open(str(orphan_path), "rb") as src:
            data = await src.read()

        await anyio.to_thread.run_sync(lambda: new_dir.mkdir(parents=True, exist_ok=True))
        async with aiofiles.open(str(new_file_path), "wb") as dst:
            await dst.write(data)

        session.add(UserFile(user_id=current_user.id, name=name_without_ext, path=db_path, size=len(data)))
        await session.commit()

        await logger.ainfo(
            "Migrated orphaned MCP servers config from %s to user %s",
            orphan_path,
            current_user.id,
        )
    except Exception as exc:  # noqa: BLE001
        await logger.awarning("Failed to migrate orphaned MCP servers config: %s", exc)
        return False
    else:
        return True


async def teardown_superuser(settings_service: SettingsService, session: AsyncSession) -> None:
    """Remove the default superuser when AUTO_LOGIN is disabled and it was never used to sign in.

    If the default account has ``last_login_at`` set, it is kept. Deletion can still fail with
    an integrity error when the user owns rows (e.g. flows) without ORM cascade — callers see
    ``RuntimeError`` so startup or shutdown does not silently ignore the problem.
    """
    if not settings_service.auth_settings.AUTO_LOGIN:
        await logger.adebug("AUTO_LOGIN is set to False. Removing default superuser if unused.")
        try:
            username = DEFAULT_SUPERUSER
            from langflow.services.database.models.user.model import User

            stmt = select(User).where(User.username == username)
            result = await session.exec(stmt)
            user = result.first()

            if user and user.is_superuser is True and not user.last_login_at:
                await session.delete(user)
                await logger.adebug("Default superuser removed successfully.")
        except Exception as exc:
            await logger.aexception("Could not remove default superuser.")
            msg = "Could not remove default superuser."
            raise RuntimeError(msg) from exc


async def teardown_services() -> None:
    """Teardown all the services."""
    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    from lfx.services.manager import get_service_manager

    service_manager = get_service_manager()
    await service_manager.teardown()


def initialize_settings_service() -> None:
    """Initialize the settings manager."""
    from lfx.services.settings import factory as settings_factory

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
        logger.debug("Successfully cleaned up old transactions")
    except (sqlalchemy_exc.SQLAlchemyError, asyncio.TimeoutError) as exc:
        logger.error(f"Error cleaning up transactions: {exc!s}")
        # Don't re-raise since this is a cleanup task


async def clean_authz_audit_log(settings_service: SettingsService, session: AsyncSession) -> int:
    """Delete authz_audit_log rows older than ``AUTHZ_AUDIT_RETENTION_DAYS``.

    Retention is configured via ``AuthSettings.AUTHZ_AUDIT_RETENTION_DAYS``;
    setting it to ``0`` disables pruning so operators relying on an external
    archival pipeline (Postgres partitioning, SIEM export) can opt out without
    losing rows here. The function is intentionally best-effort: failures are
    logged and swallowed so startup never fails because the audit table is
    transiently unreachable.

    Returns the number of rows deleted (best-effort; ``-1`` when the rowcount
    is unavailable from the driver).
    """
    try:
        retention_days = int(getattr(settings_service.auth_settings, "AUTHZ_AUDIT_RETENTION_DAYS", 90))
    except Exception:  # noqa: BLE001 — settings shape can vary in tests/stubs
        retention_days = 90
    if retention_days <= 0:
        logger.debug("authz_audit_log retention disabled (AUTHZ_AUDIT_RETENTION_DAYS=%d)", retention_days)
        return 0

    from datetime import datetime, timedelta, timezone

    from langflow.services.database.models.auth import AuthzAuditLog

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    try:
        delete_stmt = delete(AuthzAuditLog).where(col(AuthzAuditLog.timestamp) < cutoff)
        result = await session.exec(delete_stmt)
        deleted = getattr(result, "rowcount", None)
        deleted_count = int(deleted) if deleted is not None and deleted >= 0 else -1
        logger.debug(
            "authz_audit_log cleanup removed %s rows older than %d days",
            deleted_count if deleted_count >= 0 else "?",
            retention_days,
        )
    except (sqlalchemy_exc.SQLAlchemyError, asyncio.TimeoutError) as exc:
        logger.warning("authz_audit_log cleanup failed: %s", exc)
        return -1
    else:
        return deleted_count


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
        logger.debug("Successfully cleaned up old vertex builds")
    except (sqlalchemy_exc.SQLAlchemyError, asyncio.TimeoutError) as exc:
        logger.error(f"Error cleaning up vertex builds: {exc!s}")
        # Don't re-raise since this is a cleanup task


def register_all_service_factories() -> None:
    """Register all available service factories with the service manager."""
    # Import all service factories
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    service_manager = get_service_manager()
    from lfx.services.executor import factory as executor_factory
    from lfx.services.mcp_composer import factory as mcp_composer_factory
    from lfx.services.settings import factory as settings_factory

    from langflow.services.auth import factory as auth_factory
    from langflow.services.auth.service import AuthService
    from langflow.services.authorization import factory as authorization_factory
    from langflow.services.authorization.service import LangflowAuthorizationService
    from langflow.services.cache import factory as cache_factory
    from langflow.services.chat import factory as chat_factory
    from langflow.services.database import factory as database_factory
    from langflow.services.job_queue import factory as job_queue_factory
    from langflow.services.session import factory as session_factory
    from langflow.services.shared_component_cache import factory as shared_component_cache_factory
    from langflow.services.state import factory as state_factory
    from langflow.services.storage import factory as storage_factory
    from langflow.services.store import factory as store_factory
    from langflow.services.task import factory as task_factory
    from langflow.services.telemetry import factory as telemetry_factory
    from langflow.services.telemetry_writer import factory as telemetry_writer_factory
    from langflow.services.tracing import factory as tracing_factory
    from langflow.services.transaction import factory as transaction_factory
    from langflow.services.variable import factory as variable_factory

    # Register all factories
    service_manager.register_factory(settings_factory.SettingsServiceFactory())
    service_manager.register_factory(cache_factory.CacheServiceFactory())
    service_manager.register_factory(chat_factory.ChatServiceFactory())
    service_manager.register_factory(database_factory.DatabaseServiceFactory())
    service_manager.register_factory(session_factory.SessionServiceFactory())
    service_manager.register_factory(storage_factory.StorageServiceFactory())
    service_manager.register_factory(variable_factory.VariableServiceFactory())
    service_manager.register_factory(telemetry_factory.TelemetryServiceFactory())
    service_manager.register_factory(tracing_factory.TracingServiceFactory())
    service_manager.register_factory(transaction_factory.TransactionServiceFactory())
    service_manager.register_factory(telemetry_writer_factory.TelemetryWriterServiceFactory())
    service_manager.register_factory(state_factory.StateServiceFactory())
    service_manager.register_factory(job_queue_factory.JobQueueServiceFactory())
    service_manager.register_factory(task_factory.TaskServiceFactory())
    service_manager.register_factory(store_factory.StoreServiceFactory())
    service_manager.register_factory(shared_component_cache_factory.SharedComponentCacheServiceFactory())
    # Override LFX's no-op auth service with Langflow's full JWT implementation
    service_manager.register_service_class(ServiceType.AUTH_SERVICE, AuthService, override=True)
    service_manager.register_factory(auth_factory.AuthServiceFactory())
    # Same pattern as ``auth_service``: register the OSS pass-through here with
    # ``override=True`` so Langflow always has a default. A registered
    # authorization plugin replaces it by listing its class in
    # ``LANGFLOW_CONFIG_DIR/lfx.toml`` (config files use ``override=True`` via
    # ``_discover_from_config``). Plain entry-point discovery uses
    # ``override=False`` and would lose to this default — the supported
    # override path is the ``lfx.toml`` config, matching SSO.
    service_manager.register_service_class(
        ServiceType.AUTHORIZATION_SERVICE, LangflowAuthorizationService, override=True
    )
    service_manager.register_factory(authorization_factory.AuthorizationServiceFactory())
    service_manager.register_factory(mcp_composer_factory.MCPComposerServiceFactory())
    service_manager.register_factory(executor_factory.ExecutorServiceFactory())
    service_manager.set_factory_registered()


def register_builtin_adapters() -> None:
    """Import built-in adapter registration modules.

    Mirrors ``register_all_service_factories()`` for the adapter registry system.
    Each import registers the adapter class on the AdapterRegistry singleton.

    TODO: Watsonx risks are documented here because registration is runtime-optional:
    missing ``ibm_*`` modules should skip adapter registration, but broad
    ``ModuleNotFoundError`` handling can also hide internal import regressions.
    Future deployment API routing must treat "provider exists but adapter is not
    registered in this runtime" as an explicit, deterministic error path.
    Keep direct adapter imports limited to guarded paths and maintain CI
    coverage that confirms Watsonx tests run (not skip) in eligible environments.
    """
    if not FEATURE_FLAGS.wxo_deployments:
        logger.debug("Skipping deployment adapter registration: wxo_deployments feature flag disabled")
        return

    try:
        import_module("langflow.services.adapters.deployment.watsonx_orchestrate.register")
    except ModuleNotFoundError as exc:
        logger.info("Skipping Watsonx Orchestrate adapter registration: %s", exc)


def register_builtin_deployment_mappers() -> None:
    """Import built-in deployment mapper modules so registration side effects fire."""
    if not FEATURE_FLAGS.wxo_deployments:
        logger.debug("Skipping deployment mapper registration: wxo_deployments feature flag disabled")
        return

    try:
        import_module("langflow.api.v1.mappers.deployments.watsonx_orchestrate")
    except ModuleNotFoundError as exc:
        logger.info("Skipping Watsonx Orchestrate deployment mapper registration: %s", exc)


async def initialize_services(*, fix_migration: bool = False, skip_superuser_setup: bool = False) -> None:
    """Initialize all the services needed."""
    from langflow.helpers.windows_postgres_helper import configure_windows_postgres_event_loop

    configure_windows_postgres_event_loop(source="initialize_services")

    # Register all service factories first
    register_all_service_factories()
    register_builtin_adapters()
    register_builtin_deployment_mappers()

    cache_service = get_service(ServiceType.CACHE_SERVICE, default=CacheServiceFactory())
    # Test external cache connection
    if isinstance(cache_service, ExternalAsyncBaseCacheService) and not (await cache_service.is_connected()):
        msg = "Cache service failed to connect to external database"
        raise ConnectionError(msg)

    # Fail fast if the Redis-backed job queue is selected but Redis is unreachable.
    # Otherwise Langflow boots "fine" and emits confusing connection errors only
    # when a flow is executed. Only probes when the redis backend is selected, so
    # the default asyncio backend is unaffected.
    if get_settings_service().settings.job_queue_type == "redis":
        from langflow.services.job_queue.factory import JobQueueServiceFactory
        from langflow.services.job_queue.service import RedisJobQueueService

        queue_service = get_service(ServiceType.JOB_QUEUE_SERVICE, default=JobQueueServiceFactory())
        if isinstance(queue_service, RedisJobQueueService) and not (await queue_service.is_connected()):
            msg = (
                f"Job queue backend 'redis' is selected (LANGFLOW_JOB_QUEUE_TYPE=redis) but Redis is "
                f"not reachable at {queue_service.connection_target}. Start Redis, fix the "
                "LANGFLOW_REDIS_QUEUE_* settings, or set LANGFLOW_JOB_QUEUE_TYPE=asyncio."
            )
            raise ConnectionError(msg)

    # Setup the superuser
    await initialize_database(fix_migration=fix_migration)
    db_service = get_db_service()
    await db_service.initialize_alembic_log_file()
    settings_service = get_service(ServiceType.SETTINGS_SERVICE)
    if not skip_superuser_setup:
        async with session_scope() as session:
            await setup_superuser(settings_service, session)
        try:
            await get_db_service().assign_orphaned_flows_to_superuser()
        except sqlalchemy_exc.IntegrityError as exc:
            await logger.awarning(f"Error assigning orphaned flows to the superuser: {exc!s}")

    async with session_scope() as session:
        await clean_transactions(settings_service, session)
        await clean_vertex_builds(settings_service, session)
        await clean_authz_audit_log(settings_service, session)

"""Service dependency functions for lfx package."""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, cast

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lfx.log.logger import logger
from lfx.services.config_discovery import resolve_config_dir
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from lfx.services.adapters.registry import AdapterRegistry
    from lfx.services.catalog_policy.base import BaseCatalogPolicyService
    from lfx.services.interfaces import (
        AuthServiceProtocol,
        CacheServiceProtocol,
        ChatServiceProtocol,
        ConnectionResolverProtocol,
        DatabaseServiceProtocol,
        DeploymentServiceProtocol,
        SettingsServiceProtocol,
        StorageServiceProtocol,
        TracingServiceProtocol,
        TransactionServiceProtocol,
        VariableServiceProtocol,
    )
    from lfx.services.policy_bundle.base import BasePolicyBundleService


def get_service(service_type: ServiceType, default=None):
    """Retrieves the service instance for the given service type.

    Args:
        service_type: The type of service to retrieve.
        default: The default ServiceFactory to use if the service is not found.

    Returns:
        The service instance or None if not available.
    """
    from lfx.services.manager import get_service_manager

    service_manager = get_service_manager()

    if not service_manager.are_factories_registered():
        # ! This is a workaround to ensure that the service manager is initialized
        # ! Not optimal, but it works for now

        service_manager.register_factories(service_manager.get_factories())

    if ServiceType.SETTINGS_SERVICE not in service_manager.factories:
        from lfx.services.settings.factory import SettingsServiceFactory

        service_manager.register_factory(service_factory=SettingsServiceFactory())

    try:
        return service_manager.get(service_type, default)
    except Exception:  # noqa: BLE001
        # Preserve the traceback in logs so callers seeing a None return have something to grep
        # for. Returning None remains the contract because several callers (e.g. get_db_service)
        # treat absence as "not configured" and substitute a noop implementation.
        logger.exception("Failed to resolve service %s", service_type)
        return None


def get_model_provider_policy_service():
    """Return the configured model-provider policy service or fail closed."""
    from lfx.services.model_provider_policy.base import BaseModelProviderPolicyService
    from lfx.services.model_provider_policy.service import ModelProviderPolicyService  # noqa: F401

    service = get_service(ServiceType.MODEL_PROVIDER_POLICY_SERVICE)
    if not isinstance(service, BaseModelProviderPolicyService) or not service.ready:
        msg = "A valid, ready model_provider_policy_service is required"
        raise TypeError(msg)
    return service


def get_integration_policy_service():
    """Return the configured integration policy service or fail closed."""
    from lfx.services.integration_policy.base import BaseIntegrationPolicyService
    from lfx.services.integration_policy.service import IntegrationPolicyService  # noqa: F401

    service = get_service(ServiceType.INTEGRATION_POLICY_SERVICE)
    if not isinstance(service, BaseIntegrationPolicyService) or not service.ready:
        msg = "A valid, ready integration_policy_service is required"
        raise TypeError(msg)
    return service


def get_policy_bundle_service() -> BasePolicyBundleService:
    """Return the ready process-local shared policy bundle coordinator."""
    from lfx.services.policy_bundle import BasePolicyBundleService, PolicyBundleService  # noqa: F401

    service = get_service(ServiceType.POLICY_BUNDLE_SERVICE)
    if not isinstance(service, BasePolicyBundleService) or not service.ready:
        msg = "A valid, ready policy_bundle_service is required"
        raise TypeError(msg)
    return service


_catalog_policy_fallback: BaseCatalogPolicyService | None = None
_catalog_policy_fallback_lock = threading.Lock()


def get_catalog_policy_service():
    """Return the ready catalog-policy service.

    Standalone LFX resolves the built-in allow-all implementation. Langflow
    overrides it with the database-backed process-local snapshot service. A
    broken configured implementation is replaced with one stable built-in
    allow-all instance so later lookups remain fail-open instead of retrying a
    failing constructor.
    """
    from lfx.services.catalog_policy.base import BaseCatalogPolicyService
    from lfx.services.catalog_policy.service import CatalogPolicyService
    from lfx.services.manager import get_service_manager

    service_manager = get_service_manager()
    cached = service_manager.services.get(ServiceType.CATALOG_POLICY_SERVICE)
    if isinstance(cached, BaseCatalogPolicyService) and cached.ready:
        return cached

    service = get_service(ServiceType.CATALOG_POLICY_SERVICE)
    if isinstance(service, BaseCatalogPolicyService) and service.ready:
        return service

    global _catalog_policy_fallback  # noqa: PLW0603
    with _catalog_policy_fallback_lock:
        cached = service_manager.services.get(ServiceType.CATALOG_POLICY_SERVICE)
        if isinstance(cached, BaseCatalogPolicyService) and cached.ready:
            return cached
        fallback = _catalog_policy_fallback
        if fallback is None:
            fallback = CatalogPolicyService()
            _catalog_policy_fallback = fallback
        service_manager.services[ServiceType.CATALOG_POLICY_SERVICE] = fallback

    logger.warning(
        "Configured catalog_policy_service is unavailable or invalid; "
        "using the built-in allow-all policy for this process"
    )
    return fallback


def get_db_service() -> DatabaseServiceProtocol:
    """Retrieves the database service instance.

    Returns a NoopDatabaseService if no real database service is available,
    ensuring that session_scope() always has a valid database service to work with.
    """
    from lfx.services.database.service import NoopDatabaseService
    from lfx.services.schema import ServiceType

    db_service = get_service(ServiceType.DATABASE_SERVICE)
    if db_service is None:
        # Return noop database service when no real database service is available
        # This allows lfx to work in standalone mode without requiring database setup
        return NoopDatabaseService()
    return db_service


def get_storage_service() -> StorageServiceProtocol | None:
    """Retrieves the storage service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.STORAGE_SERVICE)


def get_settings_service() -> SettingsServiceProtocol | None:
    """Retrieves the settings service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.SETTINGS_SERVICE)


def get_variable_service() -> VariableServiceProtocol | None:
    """Retrieves the variable service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.VARIABLE_SERVICE)


_connection_resolver_fallback_lock = threading.Lock()


def get_connection_resolver() -> ConnectionResolverProtocol:
    """Return the configured resolver or the stable headless environment fallback.

    Only a genuinely absent plugin selects the fallback. Import, construction,
    type, and readiness failures remain operator-visible so a broken connection
    plugin cannot silently change credential sources.
    """
    from lfx.services.connection.base import BaseConnectionResolverService
    from lfx.services.connection.env_resolver import EnvConnectionResolver
    from lfx.services.manager import NoFactoryRegisteredError, get_service_manager

    service_manager = get_service_manager()
    cached = service_manager.services.get(ServiceType.CONNECTION_RESOLVER_SERVICE)
    if cached is not None:
        if not isinstance(cached, BaseConnectionResolverService) or not cached.ready:
            msg = "A configured connection_resolver_service must be valid and ready"
            raise RuntimeError(msg)
        return cast("ConnectionResolverProtocol", cached)

    try:
        service = service_manager.get(ServiceType.CONNECTION_RESOLVER_SERVICE)
    except NoFactoryRegisteredError:
        if (
            ServiceType.CONNECTION_RESOLVER_SERVICE in service_manager.service_classes
            or ServiceType.CONNECTION_RESOLVER_SERVICE in service_manager.factories
        ):
            raise  # A configured resolver can fail because one of its dependencies is absent.
        service = None

    if service is not None:
        if not isinstance(service, BaseConnectionResolverService) or not service.ready:
            msg = "A configured connection_resolver_service must be valid and ready"
            raise RuntimeError(msg)
        return cast("ConnectionResolverProtocol", service)

    with _connection_resolver_fallback_lock:
        cached = service_manager.services.get(ServiceType.CONNECTION_RESOLVER_SERVICE)
        if cached is not None:
            if not isinstance(cached, BaseConnectionResolverService) or not cached.ready:
                msg = "A configured connection_resolver_service must be valid and ready"
                raise RuntimeError(msg)
            return cast("ConnectionResolverProtocol", cached)
        if service_manager.connection_resolver_fallback is None:
            service_manager.connection_resolver_fallback = EnvConnectionResolver()
        return service_manager.connection_resolver_fallback


def get_shared_component_cache_service() -> CacheServiceProtocol | None:
    """Retrieves the shared component cache service instance."""
    from lfx.services.shared_component_cache.factory import SharedComponentCacheServiceFactory

    return get_service(ServiceType.SHARED_COMPONENT_CACHE_SERVICE, SharedComponentCacheServiceFactory())


def get_extension_events_service():
    """Retrieves the ExtensionEventsService instance.

    Returns None if the service manager is not initialised (e.g. in unit-test
    environments that don't boot the full service stack).  Callers must guard
    against None and fall back to structured logging.
    """
    from lfx.services.extension_events.factory import ExtensionEventsServiceFactory

    return get_service(ServiceType.EXTENSION_EVENTS_SERVICE, ExtensionEventsServiceFactory())


def get_chat_service() -> ChatServiceProtocol | None:
    """Retrieves the chat service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.CHAT_SERVICE)


def get_checkpoint_service():
    """Checkpoint store: registered service, or the in-memory standalone fallback."""
    from lfx.graph.checkpoint.store import default_checkpoint_store
    from lfx.services.schema import ServiceType

    service = get_service(ServiceType.CHECKPOINT_SERVICE)
    if service is not None:
        return service
    return default_checkpoint_store()


def get_tracing_service() -> TracingServiceProtocol | None:
    """Retrieves the tracing service instance."""
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.TRACING_SERVICE)


def get_transaction_service() -> TransactionServiceProtocol | None:
    """Retrieves the transaction service instance.

    Returns the transaction service for logging component executions.
    Returns None if no transaction service is registered.
    """
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.TRANSACTION_SERVICE)


def get_auth_service() -> AuthServiceProtocol | None:
    """Retrieves the auth service instance.

    Returns the pluggable auth service (minimal LFX or full Langflow when configured).
    """
    from lfx.services.schema import ServiceType

    return get_service(ServiceType.AUTH_SERVICE)


def _get_deployment_registry() -> AdapterRegistry[DeploymentServiceProtocol]:
    """Retrieve the deployment adapter registry singleton.

    Discovery still needs to be triggered separately via
    ``registry.discover(config_dir=...)``.
    """
    from lfx.services.adapters.registry import get_adapter_registry
    from lfx.services.adapters.schema import AdapterType

    return cast(
        "AdapterRegistry[DeploymentServiceProtocol]",
        get_adapter_registry(adapter_type=AdapterType.DEPLOYMENT),
    )


_deployment_discovery_lock = threading.Lock()


def get_deployment_adapter(
    adapter_key: str,
) -> DeploymentServiceProtocol | None:
    """Resolve a singleton deployment adapter instance by key.

    Args:
        adapter_key: Deployment adapter registry key (for example ``"local"``).
    """
    registry = _get_deployment_registry()
    if not registry.is_discovered:
        with _deployment_discovery_lock:
            # Double-check after acquiring lock to avoid redundant discovery.
            if not registry.is_discovered:
                registry.discover(config_dir=_resolve_adapter_config_dir())
    instance = registry.get_instance(adapter_key, factory=lambda adapter_class: adapter_class())
    if instance is None:
        logger.warning(
            f"No deployment adapter found for key='{adapter_key}'. "
            f"Available keys: {registry.list_keys()}. "
            f"Check your lfx.toml or adapter registration."
        )
    return instance


def _resolve_adapter_config_dir() -> Path:
    """Resolve config directory for adapter discovery."""
    return resolve_config_dir(None, settings_service=get_settings_service())


async def get_session():
    msg = "get_session is deprecated, use session_scope instead"
    logger.warning(msg)
    raise NotImplementedError(msg)


async def injectable_session_scope():
    async with session_scope() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for managing an async session scope with auto-commit for write operations.

    This is used with `async with session_scope() as session:` for direct session management.
    It ensures that the session is properly committed if no exceptions occur,
    and rolled back if an exception is raised.
    Use session_scope_readonly() for read-only operations to avoid unnecessary commits and locks.

    Yields:
        AsyncSession: The async session object.

    Raises:
        Exception: If an error occurs during the session scope.
    """
    db_service = get_db_service()
    async with db_service._with_session() as session:  # noqa: SLF001
        try:
            yield session
            await session.commit()
        except (HTTPException, RequestValidationError, WebSocketRequestValidationError):
            # HTTPExceptions are control flow in FastAPI (returning 4xx/5xx responses),
            # not actual errors. Don't log them - FastAPI's exception handlers will
            # take care of the HTTP response. Just rollback any uncommitted changes.
            # A request that fails validation is the same: FastAPI validates after this
            # dependency is open and throws the error in here on its way to the 422
            # (or the websocket close). Its text and traceback quote the submitted
            # values, so logging it would put the request body in the server log.
            if session.is_active:
                from sqlalchemy.exc import InvalidRequestError

                with suppress(InvalidRequestError):
                    await session.rollback()
            raise
        except Exception as e:
            # Actual application/database errors - log at error level
            await logger.aexception("An error occurred during the session scope.", exception=e)

            # Only rollback if session is still in a valid state
            if session.is_active:
                from sqlalchemy.exc import InvalidRequestError

                with suppress(InvalidRequestError):
                    # Session was already rolled back by SQLAlchemy
                    await session.rollback()
            raise
        # No explicit close needed - _with_session() handles it


async def injectable_session_scope_readonly():
    async with session_scope_readonly() as session:
        yield session


@asynccontextmanager
async def session_scope_readonly() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for managing a read-only async session scope.

    This is used with `async with session_scope_readonly() as session:` for direct session management
    when only reading data. No auto-commit or rollback - the session is simply closed after use.

    Yields:
        AsyncSession: The async session object.
    """
    db_service = get_db_service()
    async with db_service._with_session() as session:  # noqa: SLF001
        yield session
        # No commit - read-only
        # No clean up - client is responsible (plus, read only sessions are not committed)
        # No explicit close needed - _with_session() handles it


_AUTOCOMMIT_GUARD_FLAG = "autocommit_read_guard"
_AUTOCOMMIT_ALLOWED_KEYWORDS = {"SELECT", "SHOW", "VALUES", "WITH"}


class AutocommitReadGuardError(SQLAlchemyError):
    """Raised when a write is attempted inside an autocommit read scope.

    A SQLAlchemyError subclass so fail-closed handlers catching SQLAlchemyError
    (e.g. migration_pause) treat it like any other database failure.
    """


def _first_sql_keyword(statement: str) -> str:
    """Return the leading alphabetic run after stripping whitespace, parens and comments.

    Not SQL parsing: exotic prefixes can still mask the verb. This is a tripwire for
    audited call sites, not a sandbox.
    """
    s = statement.lstrip()
    while True:
        if s.startswith("("):
            s = s[1:].lstrip()
            continue
        if s.startswith("--"):
            nl = s.find("\n")
            if nl < 0:
                return ""
            s = s[nl + 1 :].lstrip()
            continue
        if s.startswith("/*"):
            end = s.find("*/")
            if end < 0:
                return ""
            s = s[end + 2 :].lstrip()
            continue
        break
    keyword = ""
    for ch in s:
        if ch.isalpha():
            keyword += ch
        else:
            break
    return keyword.upper()


def _guard_blocked(statement: str) -> bool:
    """Deliberately conservative: ANY semicolon blocks (fail-closed).

    A parameterless multi-statement string is sent by psycopg3 over the simple
    protocol, so "SELECT 1; INSERT ..." would execute the write past a first-keyword
    check. False positive by design: a read with ';' inside a string literal is
    blocked too. None of the audited call sites use literals.
    """
    if ";" in statement:
        return True
    return _first_sql_keyword(statement) not in _AUTOCOMMIT_ALLOWED_KEYWORDS


def ensure_autocommit_guard(sync_engine) -> None:
    """Install ONE permanent flag-predicated listener pair on a sync engine.

    Synchronous check-and-set with no suspension point: atomic within one event loop.
    A rebuilt engine (new instance) gets its own pair on first arm; the discarded
    engine's listeners die with it. The checkout listener bounds the flag's lifetime
    to the checkout, so an orphaned flag can never poison a later borrower.
    """
    if getattr(sync_engine, "_ac_guard_installed", False):
        return

    def guard(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        if not conn.info.get(_AUTOCOMMIT_GUARD_FLAG):
            return
        if _guard_blocked(statement):
            msg = "autocommit read scope: only single-statement reads are allowed"
            raise AutocommitReadGuardError(msg)

    def clear_on_checkout(dbapi_connection, connection_record, connection_proxy):  # noqa: ARG001
        connection_record.info.pop(_AUTOCOMMIT_GUARD_FLAG, None)

    event.listen(sync_engine, "before_cursor_execute", guard)
    event.listen(sync_engine.pool, "checkout", clear_on_checkout)
    sync_engine._ac_guard_installed = True  # noqa: SLF001


@asynccontextmanager
async def session_scope_autocommit() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for AUDITED single-statement read scopes without a transaction.

    Same lifecycle as session_scope_readonly (via _with_session), but on PostgreSQL
    with the default READ COMMITTED isolation the connection is switched to driver
    AUTOCOMMIT for the scope, saving the BEGIN/COMMIT round trips per read.

    Supported contract (anything else degrades to a plain session or raises):
    - fresh session per scope (this helper creates it; do NOT reuse a session across
      scopes - a degraded scope on a reused session is not transactional),
    - single statement per execute; any semicolon is rejected (fail-closed),
    - pure reads: SELECT/SHOW/VALUES/WITH-led statements only,
    - no commit/rollback inside the scope (a mid-scope commit releases the armed
      checkout; subsequent statements run plain and unguarded).

    Known limitations (the per-caller audit, not the guard, is the safety mechanism):
    WITH-led statements can still write (data-modifying CTEs or top-level DML after
    the WITH clause), FOR UPDATE/SHARE passes, volatile SELECT can side-effect,
    SELECT INTO passes. On any other configuration (SQLite, non-default isolation,
    cold engine before first connect) the scope degrades to a plain session.
    """
    db_service = get_db_service()
    async with db_service._with_session() as session:  # noqa: SLF001
        if not isinstance(session, AsyncSession):
            # NoopDatabaseService has no engine; NoopSession.connection() takes no
            # execution_options. The isinstance check is the detection.
            yield session
            return
        bind = session.get_bind()
        dialect = bind.dialect
        # Engine-level execution_options isolation is NOT reflected in dialect
        # attributes (it is applied per checkout). Resolve it first so a
        # SERIALIZABLE-configured engine degrades instead of being silently
        # switched to AUTOCOMMIT. Bind may be an AsyncEngine (options live on
        # .sync_engine), an AsyncConnection (via .engine), or a sync Engine.
        sync_engine = getattr(bind, "sync_engine", None) or getattr(getattr(bind, "engine", None), "sync_engine", None)
        engine_options = (
            getattr(bind, "_execution_options", None) or getattr(sync_engine, "_execution_options", None) or {}
        )
        effective = (
            engine_options.get("isolation_level")
            or getattr(dialect, "_on_connect_isolation_level", None)
            or getattr(dialect, "default_isolation_level", None)
        )
        if effective != "READ COMMITTED":
            yield session
            return
        ensure_autocommit_guard(bind)
        if session.in_transaction():
            # Connection already acquired before entry.
            conn = await session.connection()
            fairy = conn.sync_connection.connection
            if fairy.info.get(_AUTOCOMMIT_GUARD_FLAG):
                # Nested armed scope on one connection: fail closed BEFORE any
                # try/finally exists, so the outer scope's flag is never touched.
                msg = "nested autocommit read scope on one connection rejected"
                raise AutocommitReadGuardError(msg)
            yield session  # pre-acquired by other means: degrade, no AUTOCOMMIT claim
            return
        conn = await session.connection(execution_options={"isolation_level": "AUTOCOMMIT"})
        fairy = conn.sync_connection.connection
        # Ownership token: only this scope may clear its flag. After a
        # mid-scope invalidation the pooled record can be re-checked-out and
        # re-armed by another scope; an unconditional pop would disarm that
        # scope while its statements still run in AUTOCOMMIT.
        token = object()
        fairy.info[_AUTOCOMMIT_GUARD_FLAG] = token
        try:
            yield session
        finally:
            # Pure dict get/pop on the captured fairy: cannot raise, even after
            # mid-statement cancellation (conn.info would revalidate an invalidated
            # connection and raise, masking the propagating CancelledError).
            if fairy.info.get(_AUTOCOMMIT_GUARD_FLAG) is token:
                fairy.info.pop(_AUTOCOMMIT_GUARD_FLAG, None)


async def injectable_session_scope_autocommit():
    async with session_scope_autocommit() as session:
        yield session

from __future__ import annotations

import asyncio
import re
from collections import OrderedDict
from pathlib import Path

import anyio
import sqlalchemy as sa
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine

from langflow.logging.logger import logger
from langflow.services.auth.clerk_utils import auth_header_ctx
from langflow.services.database.service import DatabaseService
from langflow.services.deps import get_settings_service
from langflow.services.settings.service import SettingsService
from langflow.services.utils import setup_superuser


class OrganizationService:
    _MAX_CACHE_SIZE = 128
    _db_service_cache: OrderedDict[str, DatabaseService] = OrderedDict()
    _cleanup_tasks: list[asyncio.Task] = []

    @classmethod
    def _remember_org(cls, org_id: str, service: DatabaseService) -> None:
        cls._db_service_cache.pop(org_id, None)
        cls._db_service_cache[org_id] = service
        if len(cls._db_service_cache) > cls._MAX_CACHE_SIZE:
            _, old_service = cls._db_service_cache.popitem(last=False)
            cls._cleanup_tasks.append(asyncio.create_task(old_service.teardown()))

    @classmethod
    def get_db_service_for_request(cls) -> DatabaseService:
        """Return a DatabaseService for the organisation in the auth context."""
        payload: dict | None = auth_header_ctx.get()
        org_id = payload.get("org_id") if payload else None
        if not org_id:
            msg = "Missing organisation id"
            raise RuntimeError(msg)

        service = cls._db_service_cache.get(org_id)
        if service:
            cls._db_service_cache.move_to_end(org_id)
            return service

        settings_service = get_settings_service()
        base_url = settings_service.settings.database_url
        new_url = cls._build_database_url_for_org(base_url, org_id)
        new_settings = settings_service.settings.model_copy()
        new_settings.database_url = new_url
        new_settings_service = SettingsService(new_settings, settings_service.auth_settings)
        service = DatabaseService(new_settings_service)
        cls._remember_org(org_id, service)
        return service

    @staticmethod
    def _build_database_url_for_org(base_url: str, org_id: str) -> str:
        """Return a database URL for the given organisation."""

        if base_url.startswith("sqlite"):
            # Use aiosqlite for async DB access
            driver_prefix = "sqlite+aiosqlite"

            if "///" in base_url:
                # Handles sqlite:///absolute/path/to/langflow.db
                db_path = base_url.split("///", 1)[1]
                db_dir = str(Path(db_path).parent)
                org_db_path = Path(db_dir) / f"{org_id}.db"
                new_url = f"{driver_prefix}:///{org_db_path.as_posix()}"
            else:
                # fallback for relative paths
                org_db_path = Path(f"{org_id}.db")
                new_url = f"{driver_prefix}:///{org_db_path.as_posix()}"

        else:
            # For Postgres/MySQL or other URLs → just replace dbname with org_id
            match = re.match(
                r"^(?P<prefix>.+/)(?P<dbname>[^/?]+)(?P<suffix>.*)$",
                base_url,
            )
            if match:
                new_url = f"{match.group('prefix')}{org_id}{match.group('suffix')}"
            else:
                logger.warning("Could not construct organisation DB url; using base url")
                new_url = base_url

        logger.debug(f"Derived organisation database URL: {new_url}")
        return new_url

    async def create_database_and_tables_other_initializations_with_org(self) -> None:
        logger.info("[OrgInit] Starting organization DB initialization process")
        settings_service = get_settings_service()

        # Check Clerk auth
        if not settings_service.auth_settings.CLERK_AUTH_ENABLED:
            raise RuntimeError("Clerk authentication disabled")

        payload: dict | None = auth_header_ctx.get()
        if not payload:
            raise RuntimeError("Missing Clerk payload")

        org_id = payload.get("org_id")
        if not org_id:
            raise RuntimeError("Missing organisation id")

        # If already cached → skip
        if org_id in self._db_service_cache:
            logger.info(f"[OrgInit] Organisation database already cached for org_id={org_id}")
            self._remember_org(org_id, self._db_service_cache[org_id])
            return

        # Build per-org DB URL
        base_url = settings_service.settings.database_url
        new_url = self._build_database_url_for_org(base_url, org_id)
        logger.info(f"[OrgInit] Using DB URL for org_id={org_id}: {new_url}")

        # --- Ensure SQLite file exists BEFORE creating DatabaseService ---
        if new_url.startswith("sqlite+aiosqlite:///"):
            db_path = Path(new_url.split("///", 1)[1])
            db_path.parent.mkdir(parents=True, exist_ok=True)

            if not db_path.exists():
                logger.info(f"[OrgInit] Creating database for org_id={org_id}")
                async_engine = create_async_engine(new_url, connect_args={"check_same_thread": False})
                async with async_engine.begin() as conn:
                    await conn.run_sync(SQLModel.metadata.create_all)
                await async_engine.dispose()

        # Create a dedicated DatabaseService for this org
        new_settings = settings_service.settings.model_copy()
        new_settings.database_url = new_url
        new_settings_service = SettingsService(new_settings, settings_service.auth_settings)
        new_db_service = DatabaseService(new_settings_service)

        try:
            # If tables already exist → reuse DB
            if await self._organisation_db_exists(new_db_service):
                logger.info(f"[OrgInit] DB already initialized for org_id={org_id}")
                self._remember_org(org_id, new_db_service)
                return

            logger.info(f"[OrgInit] Running first-time DB init for org_id={org_id}")
            if new_db_service.settings_service.settings.database_connection_retry:
                await new_db_service.create_db_and_tables_with_retry()
            else:
                await new_db_service.create_db_and_tables()

            logger.info(f"[OrgInit] Running migrations for org_id={org_id}")
            await new_db_service.run_migrations()

            logger.info(f"[OrgInit] Setting up superuser for org_id={org_id}")
            async with new_db_service.with_session() as session:
                await setup_superuser(new_settings_service, session)

            self._remember_org(org_id, new_db_service)
            logger.info(f"[OrgInit] Organisation DB initialization complete for org_id={org_id}")

        except Exception as exc:
            logger.exception(f"[OrgInit] Failed to initialise DB for org_id: {org_id}")
            await self._cleanup_failed_initialization(org_id, new_db_service, new_url)
            await new_db_service.teardown()
            raise RuntimeError("Failed to initialise organisation database") from exc

    @classmethod
    async def _cleanup_failed_initialization(cls, org_id: str, db_service: DatabaseService, database_url: str) -> None:
        """Attempt to clean up any artefacts from a failed organisation setup."""
        cls._db_service_cache.pop(org_id, None)
        try:
            async with db_service.with_session() as session, session.bind.connect() as conn:
                await conn.run_sync(SQLModel.metadata.drop_all)
        except Exception:  # noqa: BLE001
            logger.exception("Error dropping organisation tables during cleanup")

        if database_url.startswith("sqlite"):
            try:
                db_path = Path(database_url.split("///", 1)[1])
            except IndexError:
                logger.warning("Could not parse database path from url %s", database_url)
                return
            try:
                await anyio.Path(db_path).unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                logger.exception("Error removing database file %s during cleanup", db_path)

    @staticmethod
    async def _organisation_db_exists(db_service: DatabaseService) -> bool:
        """Return True if the organisation database already has required tables."""
        try:
            async with db_service.with_session() as session, session.bind.connect() as conn:
                def check_tables(sync_conn):
                    inspector = sa.inspect(sync_conn)
                    required_tables = [
                        "flow",
                        "user",
                        "apikey",
                        "folder",
                        "message",
                        "variable",
                        "transaction",
                        "vertex_build",
                    ]
                    table_names = inspector.get_table_names()
                    return all(table in table_names for table in required_tables)

                return await conn.run_sync(check_tables)
        except Exception:  # noqa: BLE001
            logger.exception("Error checking organisation database existence")
            return False


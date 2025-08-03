from __future__ import annotations

import asyncio
import re
from collections import OrderedDict
from pathlib import Path

import anyio
import sqlalchemy as sa
from sqlmodel import SQLModel

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
            if "/" in base_url:
                prefix = base_url.rsplit("/", 1)[0]
                new_url = f"{prefix}/{org_id}.db"
            else:
                new_url = f"{org_id}.db"
        else:
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
        """Create and initialise a database for the organisation from auth context."""
        settings_service = get_settings_service()
        if not settings_service.auth_settings.CLERK_AUTH_ENABLED:
            msg = "Clerk authentication disabled"
            raise RuntimeError(msg)

        payload: dict | None = auth_header_ctx.get()
        if not payload:
            msg = "Missing Clerk payload"
            raise RuntimeError(msg)
        org_id = payload.get("org_id")
        if not org_id:
            msg = "Missing organisation id"
            raise RuntimeError(msg)

        if org_id in self._db_service_cache:
            logger.debug("Organisation database already initialised (cached)")
            self._remember_org(org_id, self._db_service_cache[org_id])
            return

        base_url = settings_service.settings.database_url
        new_url = self._build_database_url_for_org(base_url, org_id)

        new_settings = settings_service.settings.model_copy()
        new_settings.database_url = new_url
        new_settings_service = SettingsService(new_settings, settings_service.auth_settings)

        new_db_service = DatabaseService(new_settings_service)
        try:
            if await self._organisation_db_exists(new_db_service):
                logger.debug("Organisation database already initialised")
                self._remember_org(org_id, new_db_service)
                return
            if new_db_service.settings_service.settings.database_connection_retry:
                await new_db_service.create_db_and_tables_with_retry()
            else:
                await new_db_service.create_db_and_tables()

            await new_db_service.check_schema_health()
            await new_db_service.run_migrations()

            async with new_db_service.with_session() as session:
                await setup_superuser(new_settings_service, session)
            self._remember_org(org_id, new_db_service)
        except Exception as exc:
            logger.exception("Failed to initialise organisation database")
            await self._cleanup_failed_initialization(org_id, new_db_service, new_url)
            await new_db_service.teardown()
            msg = "Failed to initialise organisation database"
            raise RuntimeError(msg) from exc

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
                inspector = sa.inspect(conn)
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
        except Exception:  # noqa: BLE001
            logger.exception("Error checking organisation database existence")
            return False

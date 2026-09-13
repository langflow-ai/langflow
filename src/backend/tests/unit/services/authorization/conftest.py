"""Shared fixtures for the split authorization-helper tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest


@pytest.fixture
def fake_user():
    """Build a non-superuser user object compatible with ensure_permission."""
    return SimpleNamespace(id=uuid4(), is_superuser=False)


@pytest.fixture
def fake_superuser():
    """Build a superuser user object compatible with ensure_permission."""
    return SimpleNamespace(id=uuid4(), is_superuser=True)


@pytest.fixture
async def policy_db(tmp_path):
    """Real scratch database for selected-engine policy contracts."""
    import os

    from langflow.services.database.models.api_key.model import ApiKey
    from langflow.services.database.models.auth import (
        AuthzAuditLog,
        AuthzRole,
        AuthzRoleAssignment,
        AuthzRoleAssignmentGrant,
        AuthzShare,
        AuthzTeam,
        AuthzTeamMember,
        CasbinRule,
    )
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.file.model import File
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.flow_version_deployment_attachment.model import (
        FlowVersionDeploymentAttachment,
    )
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
    from langflow.services.database.models.memory_base.model import MemoryBase, MemoryBaseSession
    from langflow.services.database.models.user.model import User
    from langflow.services.database.models.variable.model import Variable
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import SQLModel

    url = os.getenv("LANGFLOW_AUTHZ_TEST_DATABASE_URI", f"sqlite+aiosqlite:///{tmp_path / 'policy.db'}")
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_async_engine(url)
    tables = [
        model.__table__
        for model in (
            User,
            ApiKey,
            Variable,
            Folder,
            Flow,
            File,
            DeploymentProviderAccount,
            Deployment,
            FlowVersion,
            FlowVersionDeploymentAttachment,
            KnowledgeBaseRecord,
            MemoryBase,
            MemoryBaseSession,
            AuthzRole,
            AuthzRoleAssignment,
            AuthzRoleAssignmentGrant,
            AuthzTeam,
            AuthzTeamMember,
            AuthzShare,
            AuthzAuditLog,
            CasbinRule,
        )
    ]
    async with engine.begin() as connection:
        if engine.dialect.name == "sqlite":
            await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        await connection.run_sync(lambda conn: SQLModel.metadata.create_all(conn, tables=tables))
    try:
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(lambda conn: SQLModel.metadata.drop_all(conn, tables=tables))
        await engine.dispose()

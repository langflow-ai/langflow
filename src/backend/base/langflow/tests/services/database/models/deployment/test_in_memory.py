"""Deployment and DeploymentProviderAccount tests against in-memory SQLite.

Uses a real database with foreign keys enabled to verify CASCADE deletes,
unique constraints, relationships, and CRUD operations.
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from langflow.services.database.models.base import LangflowBaseModel
from langflow.services.database.models.deployment.crud import (
    count_deployments_by_provider,
    create_deployment,
    delete_deployment_by_id,
    delete_deployment_by_resource_key,
    get_deployment,
    get_deployment_by_resource_key,
    list_deployments_page,
    update_deployment,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.crud import (
    create_provider_account,
    delete_provider_account,
    get_provider_account_by_id,
    list_provider_accounts,
    update_provider_account,
)
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret
_ENCRYPT_TARGET = "langflow.services.database.models.deployment_provider_account.crud.auth_utils"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(name="db")
async def db_fixture(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(LangflowBaseModel.metadata.create_all)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session
    async with db_engine.begin() as conn:
        await conn.run_sync(LangflowBaseModel.metadata.drop_all)
    await db_engine.dispose()


@pytest.fixture
async def user(db: AsyncSession) -> User:
    u = User(username="testuser", password=_TEST_PASSWORD, is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def folder(db: AsyncSession, user: User) -> Folder:
    f = Folder(name="test-project", user_id=user.id)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f


@pytest.fixture
async def provider_account(db: AsyncSession, user: User) -> DeploymentProviderAccount:
    acct = DeploymentProviderAccount(
        user_id=user.id,
        provider_tenant_id="tenant-1",
        provider_key="test-provider",
        provider_url="https://provider.example.com",
        api_key="encrypted-value",  # pragma: allowlist secret
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    return acct


@pytest.fixture
async def deployment(
    db: AsyncSession,
    user: User,
    folder: Folder,
    provider_account: DeploymentProviderAccount,
) -> Deployment:
    d = Deployment(
        user_id=user.id,
        project_id=folder.id,
        deployment_provider_account_id=provider_account.id,
        resource_key="rk-1",
        name="my-deployment",
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


# ===========================================================================
# DeploymentProviderAccount — model-level integration
# ===========================================================================


@pytest.mark.asyncio
class TestProviderAccountModel:
    async def test_create_and_read(self, db: AsyncSession, provider_account: DeploymentProviderAccount):
        stmt = select(DeploymentProviderAccount).where(DeploymentProviderAccount.id == provider_account.id)
        row = (await db.exec(stmt)).one()
        assert row.provider_key == "test-provider"
        assert row.provider_url == "https://provider.example.com"
        assert row.provider_tenant_id == "tenant-1"
        assert row.created_at is not None
        assert row.updated_at is not None

    async def test_unique_constraint_user_url_tenant(
        self, db: AsyncSession, user: User, provider_account: DeploymentProviderAccount
    ):
        dup = DeploymentProviderAccount(
            user_id=user.id,
            provider_tenant_id=provider_account.provider_tenant_id,
            provider_key="another-key",
            provider_url=provider_account.provider_url,
            api_key="other-encrypted",  # pragma: allowlist secret
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_null_tenant_allows_multiple_rows(self, db: AsyncSession, user: User):
        """SQL NULL != NULL in unique constraints, so two rows with tenant=NULL are allowed."""
        for i in range(2):
            acct = DeploymentProviderAccount(
                user_id=user.id,
                provider_tenant_id=None,
                provider_key=f"key-{i}",
                provider_url="https://same-url.example.com",
                api_key=f"enc-{i}",
            )
            db.add(acct)
        await db.commit()

        stmt = select(DeploymentProviderAccount).where(
            DeploymentProviderAccount.user_id == user.id,
            DeploymentProviderAccount.provider_tenant_id.is_(None),  # type: ignore[union-attr]
        )
        rows = (await db.exec(stmt)).all()
        assert len(rows) == 2

    async def test_cascade_delete_on_user(
        self, db: AsyncSession, user: User, provider_account: DeploymentProviderAccount
    ):
        acct_id = provider_account.id
        await db.delete(user)
        await db.commit()

        stmt = select(DeploymentProviderAccount).where(DeploymentProviderAccount.id == acct_id)
        assert (await db.exec(stmt)).first() is None

    async def test_user_relationship(self, db: AsyncSession, provider_account: DeploymentProviderAccount):
        await db.refresh(provider_account, attribute_names=["user"])
        assert provider_account.user is not None
        assert provider_account.user.username == "testuser"


# ===========================================================================
# Deployment — model-level integration
# ===========================================================================


@pytest.mark.asyncio
class TestDeploymentModel:
    async def test_create_and_read(self, db: AsyncSession, deployment: Deployment):
        stmt = select(Deployment).where(Deployment.id == deployment.id)
        row = (await db.exec(stmt)).one()
        assert row.name == "my-deployment"
        assert row.resource_key == "rk-1"
        assert row.created_at is not None
        assert row.updated_at is not None

    async def test_unique_name_per_provider(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
        deployment: Deployment,
    ):
        dup = Deployment(
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-different",
            name=deployment.name,
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_unique_resource_key_per_provider(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
        deployment: Deployment,
    ):
        dup = Deployment(
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key=deployment.resource_key,
            name="different-name",
        )
        db.add(dup)
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_same_name_allowed_across_providers(
        self, db: AsyncSession, user: User, folder: Folder, deployment: Deployment
    ):
        other_acct = DeploymentProviderAccount(
            user_id=user.id,
            provider_key="other-provider",
            provider_url="https://other.example.com",
            api_key="enc-other",  # pragma: allowlist secret
        )
        db.add(other_acct)
        await db.commit()
        await db.refresh(other_acct)

        d2 = Deployment(
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=other_acct.id,
            resource_key=deployment.resource_key,
            name=deployment.name,
        )
        db.add(d2)
        await db.commit()
        await db.refresh(d2)
        assert d2.id is not None

    async def test_cascade_delete_on_user(self, db: AsyncSession, user: User, deployment: Deployment):
        dep_id = deployment.id
        await db.delete(user)
        await db.commit()

        stmt = select(Deployment).where(Deployment.id == dep_id)
        assert (await db.exec(stmt)).first() is None

    async def test_cascade_delete_on_folder(self, db: AsyncSession, folder: Folder, deployment: Deployment):
        dep_id = deployment.id
        await db.delete(folder)
        await db.commit()

        stmt = select(Deployment).where(Deployment.id == dep_id)
        assert (await db.exec(stmt)).first() is None

    async def test_cascade_delete_on_provider_account(
        self, db: AsyncSession, provider_account: DeploymentProviderAccount, deployment: Deployment
    ):
        dep_id = deployment.id
        await db.delete(provider_account)
        await db.commit()

        stmt = select(Deployment).where(Deployment.id == dep_id)
        assert (await db.exec(stmt)).first() is None

    async def test_relationships_load(self, db: AsyncSession, deployment: Deployment):
        await db.refresh(deployment, attribute_names=["user", "folder", "deployment_provider_account"])
        assert deployment.user.username == "testuser"
        assert deployment.folder.name == "test-project"
        assert deployment.deployment_provider_account.provider_key == "test-provider"

    async def test_fk_rejects_nonexistent_folder(self, db: AsyncSession, user: User, provider_account):
        d = Deployment(
            user_id=user.id,
            project_id=uuid4(),
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-orphan",
            name="orphan",
        )
        db.add(d)
        with pytest.raises(IntegrityError):
            await db.commit()


# ===========================================================================
# DeploymentProviderAccount — CRUD integration
# ===========================================================================


@pytest.mark.asyncio
class TestProviderAccountCRUD:
    async def test_create_and_get(self, db: AsyncSession, user: User):
        with patch(_ENCRYPT_TARGET) as mock_auth:
            mock_auth.encrypt_api_key.return_value = "enc-token"
            acct = await create_provider_account(
                db,
                user_id=user.id,
                provider_tenant_id="t1",
                provider_key="watsonx",
                provider_url="https://api.example.com",
                api_key="raw-key",  # pragma: allowlist secret
            )
            await db.commit()

        assert acct.id is not None
        assert acct.api_key == "enc-token"  # pragma: allowlist secret

        fetched = await get_provider_account_by_id(db, provider_id=acct.id, user_id=user.id)
        assert fetched is not None
        assert fetched.provider_key == "watsonx"

    async def test_list(self, db: AsyncSession, user: User):
        with patch(_ENCRYPT_TARGET) as mock_auth:
            mock_auth.encrypt_api_key.return_value = "enc"
            for i in range(3):
                await create_provider_account(
                    db,
                    user_id=user.id,
                    provider_tenant_id=f"t-{i}",
                    provider_key="k",
                    provider_url=f"https://p{i}.example.com",
                    api_key="key",  # pragma: allowlist secret
                )
            await db.commit()

        accounts = await list_provider_accounts(db, user_id=user.id)
        assert len(accounts) == 3

    async def test_update(self, db: AsyncSession, user: User):
        with patch(_ENCRYPT_TARGET) as mock_auth:
            mock_auth.encrypt_api_key.return_value = "enc"
            acct = await create_provider_account(
                db,
                user_id=user.id,
                provider_tenant_id=None,
                provider_key="k1",
                provider_url="https://p.example.com",
                api_key="key",  # pragma: allowlist secret
            )
            await db.commit()

        updated = await update_provider_account(
            db,
            provider_account=acct,
            provider_key="k2",
            provider_tenant_id="new-tenant",
        )
        await db.commit()

        assert updated.provider_key == "k2"
        assert updated.provider_tenant_id == "new-tenant"

    async def test_delete(self, db: AsyncSession, user: User):
        with patch(_ENCRYPT_TARGET) as mock_auth:
            mock_auth.encrypt_api_key.return_value = "enc"
            acct = await create_provider_account(
                db,
                user_id=user.id,
                provider_tenant_id=None,
                provider_key="k",
                provider_url="https://p.example.com",
                api_key="key",  # pragma: allowlist secret
            )
            await db.commit()

        acct_id = acct.id
        assert acct_id is not None
        await delete_provider_account(db, provider_account=acct)
        await db.commit()

        assert await get_provider_account_by_id(db, provider_id=acct_id, user_id=user.id) is None

    async def test_create_duplicate_raises(self, db: AsyncSession, user: User):
        with patch(_ENCRYPT_TARGET) as mock_auth:
            mock_auth.encrypt_api_key.return_value = "enc"
            await create_provider_account(
                db,
                user_id=user.id,
                provider_tenant_id="t1",
                provider_key="k",
                provider_url="https://p.example.com",
                api_key="key",  # pragma: allowlist secret
            )
            await db.commit()

            with pytest.raises(ValueError, match="Provider account already exists"):
                await create_provider_account(
                    db,
                    user_id=user.id,
                    provider_tenant_id="t1",
                    provider_key="other",
                    provider_url="https://p.example.com",
                    api_key="key2",  # pragma: allowlist secret
                )


# ===========================================================================
# Deployment — CRUD integration
# ===========================================================================


@pytest.mark.asyncio
class TestDeploymentCRUD:
    async def test_create_and_get(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        assert folder.id is not None
        assert provider_account.id is not None

        dep = await create_deployment(
            db,
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-crud",
            name="crud-deploy",
        )
        await db.commit()

        assert dep.id is not None
        fetched = await get_deployment(db, user_id=user.id, deployment_id=dep.id)
        assert fetched is not None
        assert fetched.name == "crud-deploy"

    async def test_get_by_resource_key(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        assert folder.id is not None
        assert provider_account.id is not None

        await create_deployment(
            db,
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-lookup",
            name="lookup-deploy",
        )
        await db.commit()

        found = await get_deployment_by_resource_key(
            db,
            user_id=user.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-lookup",
        )
        assert found is not None
        assert found.name == "lookup-deploy"

    async def test_list_page_and_count(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        assert folder.id is not None
        assert provider_account.id is not None

        for i in range(5):
            await create_deployment(
                db,
                user_id=user.id,
                project_id=folder.id,
                deployment_provider_account_id=provider_account.id,
                resource_key=f"rk-{i}",
                name=f"deploy-{i}",
            )
        await db.commit()

        total = await count_deployments_by_provider(
            db, user_id=user.id, deployment_provider_account_id=provider_account.id
        )
        assert total == 5

        page = await list_deployments_page(
            db,
            user_id=user.id,
            deployment_provider_account_id=provider_account.id,
            offset=0,
            limit=3,
        )
        assert len(page) == 3

        page2 = await list_deployments_page(
            db,
            user_id=user.id,
            deployment_provider_account_id=provider_account.id,
            offset=3,
            limit=3,
        )
        assert len(page2) == 2

    async def test_update(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        assert folder.id is not None
        assert provider_account.id is not None

        dep = await create_deployment(
            db,
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-upd",
            name="original",
        )
        await db.commit()

        updated = await update_deployment(db, deployment=dep, name="renamed")
        await db.commit()

        assert updated.name == "renamed"

        assert dep.id is not None
        fetched = await get_deployment(db, user_id=user.id, deployment_id=dep.id)
        assert fetched is not None
        assert fetched.name == "renamed"

    async def test_delete_by_id(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        assert folder.id is not None
        assert provider_account.id is not None

        dep = await create_deployment(
            db,
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-del",
            name="to-delete",
        )
        await db.commit()

        assert dep.id is not None
        count = await delete_deployment_by_id(db, user_id=user.id, deployment_id=dep.id)
        await db.commit()
        assert count == 1

        assert await get_deployment(db, user_id=user.id, deployment_id=dep.id) is None

    async def test_delete_by_resource_key(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        assert folder.id is not None
        assert provider_account.id is not None

        await create_deployment(
            db,
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-delrk",
            name="to-delete-rk",
        )
        await db.commit()

        count = await delete_deployment_by_resource_key(
            db,
            user_id=user.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-delrk",
        )
        await db.commit()
        assert count == 1

    async def test_create_duplicate_name_raises(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        assert folder.id is not None
        assert provider_account.id is not None

        await create_deployment(
            db,
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-a",
            name="same-name",
        )
        await db.commit()

        with pytest.raises(ValueError, match="conflicts with an existing record"):
            await create_deployment(
                db,
                user_id=user.id,
                project_id=folder.id,
                deployment_provider_account_id=provider_account.id,
                resource_key="rk-b",
                name="same-name",
            )

    async def test_create_duplicate_resource_key_raises(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        assert folder.id is not None
        assert provider_account.id is not None

        await create_deployment(
            db,
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-dup",
            name="name-a",
        )
        await db.commit()

        with pytest.raises(ValueError, match="conflicts with an existing record"):
            await create_deployment(
                db,
                user_id=user.id,
                project_id=folder.id,
                deployment_provider_account_id=provider_account.id,
                resource_key="rk-dup",
                name="name-b",
            )

    async def test_user_scoping(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        """Deployments are scoped to user_id — another user cannot see them."""
        assert folder.id is not None
        assert provider_account.id is not None

        dep = await create_deployment(
            db,
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-scoped",
            name="scoped",
        )
        await db.commit()

        other_user = User(username="other", password=_TEST_PASSWORD, is_active=True)
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        assert dep.id is not None
        assert await get_deployment(db, user_id=other_user.id, deployment_id=dep.id) is None

    async def test_cascade_delete_via_provider_crud(
        self,
        db: AsyncSession,
        user: User,
        folder: Folder,
        provider_account: DeploymentProviderAccount,
    ):
        """Deleting a provider account via CRUD cascades to its deployments."""
        assert folder.id is not None
        assert provider_account.id is not None

        dep = await create_deployment(
            db,
            user_id=user.id,
            project_id=folder.id,
            deployment_provider_account_id=provider_account.id,
            resource_key="rk-cascade",
            name="cascade-test",
        )
        await db.commit()
        dep_id = dep.id

        await delete_provider_account(db, provider_account=provider_account)
        await db.commit()

        stmt = select(Deployment).where(Deployment.id == dep_id)
        assert (await db.exec(stmt)).first() is None

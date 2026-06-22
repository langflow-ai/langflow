"""DB-layer tests for the deployment authz prefilter (``allowed_ids``).

``list_deployments_page`` / ``count_deployments_by_provider`` gain an
``allowed_ids`` parameter so a registered authorization plugin can widen the
owner-scoped listing to the union of owner rows and the ids it reports visible —
all in one SQL statement (no per-row enforce, so no N+1). ``None`` preserves the
owner-only behavior exactly.

The rows here deliberately seed foreign-owned deployments under the requester's
provider account so the union semantics are observable at the DB layer (the
route layer additionally scopes by provider ownership).
"""

from uuid import uuid4

import pytest
from langflow.services.database.models.deployment.crud import (
    count_deployments_by_provider,
    list_deployments_page,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services.adapters.deployment.schema import DeploymentType
from sqlalchemy.ext.asyncio import AsyncSession


async def _seed(async_session: AsyncSession):
    """Seed one provider account (owned by ``owner``) plus owned + foreign rows."""
    owner = User(username=f"owner-{uuid4()}", password=f"hashed-{uuid4()}", is_active=True)
    other = User(username=f"other-{uuid4()}", password=f"hashed-{uuid4()}", is_active=True)
    project = Folder(name=f"project-{uuid4()}", user_id=owner.id)
    provider = DeploymentProviderAccount(
        user_id=owner.id,
        name=f"provider-{uuid4()}",
        provider_tenant_id=None,
        provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
        provider_url="https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
        api_key="encrypted-api-key",  # pragma: allowlist secret
    )
    async_session.add_all([owner, other, project, provider])
    await async_session.commit()

    def _mk(user_id):
        return Deployment(
            user_id=user_id,
            project_id=project.id,
            deployment_provider_account_id=provider.id,
            resource_key=f"rk-{uuid4()}",
            display_name=f"dep-{uuid4()}",
            deployment_type=DeploymentType.AGENT,
        )

    owned = _mk(owner.id)
    foreign_visible = _mk(other.id)
    foreign_hidden = _mk(other.id)
    async_session.add_all([owned, foreign_visible, foreign_hidden])
    await async_session.commit()
    return owner, provider, owned, foreign_visible, foreign_hidden


@pytest.mark.asyncio
async def test_list_deployments_page_none_allowed_ids_is_owner_only(async_session: AsyncSession):
    """allowed_ids=None (OSS default) returns owner rows only — unchanged behavior."""
    owner, provider, owned, foreign_visible, foreign_hidden = await _seed(async_session)

    rows = await list_deployments_page(
        async_session,
        user_id=owner.id,
        deployment_provider_account_id=provider.id,
        offset=0,
        limit=20,
    )

    returned = {deployment.id for deployment, _count, _matched in rows}
    assert returned == {owned.id}
    assert foreign_visible.id not in returned
    assert foreign_hidden.id not in returned


@pytest.mark.asyncio
async def test_list_deployments_page_allowed_ids_unions_owner_and_visible(async_session: AsyncSession):
    """A concrete allowed_ids list widens the page to (owner ⊕ visible) — and no further."""
    owner, provider, owned, foreign_visible, foreign_hidden = await _seed(async_session)

    rows = await list_deployments_page(
        async_session,
        user_id=owner.id,
        deployment_provider_account_id=provider.id,
        offset=0,
        limit=20,
        allowed_ids=[foreign_visible.id],
    )

    returned = {deployment.id for deployment, _count, _matched in rows}
    # Owner row is always present (owner-override); the explicitly-visible
    # foreign row is added; the non-listed foreign row stays hidden.
    assert returned == {owned.id, foreign_visible.id}
    assert foreign_hidden.id not in returned


@pytest.mark.asyncio
async def test_get_provider_account_by_id_unscoped_loads_foreign_account(async_session: AsyncSession):
    """The unscoped fetch resolves a provider account by id regardless of owner.

    This is the gate relaxation behind the deployment-list authz prefilter: a
    caller granted READ on a shared deployment under another user's provider
    account must resolve that account's ``provider_key`` even though the
    owner-scoped fetch hides it from them.
    """
    from langflow.services.database.models.deployment_provider_account.crud import (
        get_provider_account_by_id,
        get_provider_account_by_id_unscoped,
    )

    owner, provider, *_ = await _seed(async_session)
    non_owner = uuid4()

    # Owner-scoped fetch hides the account from a non-owner ...
    assert await get_provider_account_by_id(async_session, provider_id=provider.id, user_id=non_owner) is None
    # ... but the unscoped fetch resolves it by id alone.
    loaded = await get_provider_account_by_id_unscoped(async_session, provider_id=provider.id)
    assert loaded is not None
    assert loaded.id == provider.id
    # The owner can still load their own account via the scoped fetch.
    assert await get_provider_account_by_id(async_session, provider_id=provider.id, user_id=owner.id) is not None
    # A non-existent id returns None (the helper raises no error; the route maps
    # None → 404).
    assert await get_provider_account_by_id_unscoped(async_session, provider_id=uuid4()) is None


@pytest.mark.asyncio
async def test_count_deployments_by_provider_reflects_allowed_ids(async_session: AsyncSession):
    """The total count uses the same predicate as the page, so pagination stays consistent."""
    owner, provider, _owned, foreign_visible, _foreign_hidden = await _seed(async_session)

    owner_only = await count_deployments_by_provider(
        async_session,
        user_id=owner.id,
        deployment_provider_account_id=provider.id,
    )
    widened = await count_deployments_by_provider(
        async_session,
        user_id=owner.id,
        deployment_provider_account_id=provider.id,
        allowed_ids=[foreign_visible.id],
    )
    empty_allowed = await count_deployments_by_provider(
        async_session,
        user_id=owner.id,
        deployment_provider_account_id=provider.id,
        allowed_ids=[],
    )

    assert owner_only == 1
    assert widened == 2
    # An empty visible set degrades to owner-only (owner-override invariant),
    # never to zero.
    assert empty_allowed == 1

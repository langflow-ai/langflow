"""Salesforce consent stays bound to the personal connection owner."""

from uuid import uuid4

import pytest
from langflow.services.connection.oauth import broker
from langflow.services.connection.oauth.config import OAuthError
from langflow.services.database.models.connection import Connection, ConnectionSecret
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.deps import session_scope

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("ownership", ["instance", "another-user"])
async def test_salesforce_consent_rejects_nonpersonal_or_foreign_connections(trigger_owner, ownership):
    async with session_scope() as session:
        row = Connection(
            provider_key="salesforce",
            name=f"blocked-{uuid4().hex[:8]}",
            display_name="Blocked",
            ownership_mode="user" if ownership == "another-user" else "instance",
            owner_id=trigger_owner if ownership != "instance" else None,
            executing_identity={"identity": "user_delegated"},
        )
        session.add(row)
        await session.flush()

        with pytest.raises(OAuthError, match="Only the owner may authorize a personal Salesforce connection"):
            await broker.start(
                session,
                row=row,
                user_id=uuid4() if ownership == "another-user" else trigger_owner,
                registration_id="salesforce-work",
                scopes=["api", "id", "refresh_token"],
            )

        assert await session.get(ConnectionOAuth, row.id) is None
        assert await session.get(ConnectionSecret, row.id) is None

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KeycloakGroupMapping(SQLModel, table=True):
    """Maps a Keycloak group path to a shared Langflow username.

    Multiple Keycloak groups can map to the same Langflow account.
    The first matching group found in a user's token is used.
    """

    __tablename__ = "keycloak_group_mapping"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Keycloak group path as it appears in the JWT claim, e.g. "/project-a"
    keycloak_group: str = Field(unique=True, index=True)

    # The shared Langflow username that members of this group log in as
    langflow_username: str = Field(index=True)

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class KeycloakGroupMappingCreate(SQLModel):
    keycloak_group: str
    langflow_username: str


class KeycloakGroupMappingRead(SQLModel):
    id: UUID
    keycloak_group: str
    langflow_username: str
    created_at: datetime
    updated_at: datetime

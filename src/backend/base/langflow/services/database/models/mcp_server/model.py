from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlmodel import JSON, Column, Field, SQLModel, UniqueConstraint

from langflow.schema.serialize import UUIDstr


class MCPServer(SQLModel, table=True):  # type: ignore[call-arg]
    """A single MCP client server entry for a user.

    Replaces the per-user ``_mcp_servers_<user_id>.json`` file: one row per
    server, keyed uniquely by ``(user_id, name)`` so concurrent edits to a user's
    server list cannot lose updates. The full ``mcpServers`` entry (command/args/
    env/headers/url plus any extra fields) is kept in the ``config`` JSON column;
    secret-bearing values inside it are encrypted at rest.
    """

    __tablename__ = "mcp_server"
    # (user_id, name) ordering: unique per user AND the composite index's leading
    # user_id column serves get_server_list's `WHERE user_id = ?` lookup.
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_mcp_server_name_user"),)

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False))
    name: str = Field(nullable=False)
    transport: str | None = Field(default=None)
    config: dict | None = Field(default=None, sa_column=Column(JSON))
    enabled: bool = Field(default=True)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

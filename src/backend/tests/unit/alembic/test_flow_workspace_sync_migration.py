"""Data-repair contract for project-scoped flow workspace ids."""

from __future__ import annotations

import importlib
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = importlib.import_module("langflow.alembic.versions.b7d5f9a3c2e4_sync_flow_workspace_from_project")


def test_workspace_sync_uses_folder_for_project_scoped_rows_and_preserves_unscoped_rows(monkeypatch):
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    folder = sa.Table(
        "folder",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
    )
    flow = sa.Table(
        "flow",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("folder_id", sa.Uuid(), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
    )
    metadata.create_all(engine)
    project_id = uuid4()
    canonical_workspace = uuid4()
    spoofed_workspace = uuid4()
    project_flow_id = uuid4()
    unscoped_flow_id = uuid4()

    with engine.begin() as connection:
        connection.execute(folder.insert(), {"id": project_id, "workspace_id": canonical_workspace})
        connection.execute(
            flow.insert(),
            [
                {
                    "id": project_flow_id,
                    "folder_id": project_id,
                    "workspace_id": spoofed_workspace,
                },
                {
                    "id": unscoped_flow_id,
                    "folder_id": None,
                    "workspace_id": spoofed_workspace,
                },
            ],
        )
        monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(connection)))

        _MIGRATION.upgrade()

        rows = dict(connection.execute(sa.select(flow.c.id, flow.c.workspace_id)).all())
        assert rows[project_flow_id] == canonical_workspace
        assert rows[unscoped_flow_id] == spoofed_workspace

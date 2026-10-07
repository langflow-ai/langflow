"""Keep existing per-user default projects private during schema upgrade."""

from __future__ import annotations

import importlib
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = importlib.import_module("langflow.alembic.versions.d8f2c3a4b5e6_mark_personal_default_projects")


def test_upgrade_marks_named_and_renamed_defaults_without_marking_team_projects(monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_FOLDER_NAME", "Configured starter")
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    folder = sa.Table(
        "folder",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
    )
    metadata.create_all(engine)
    owner_id = uuid4()
    rows = [
        {"id": uuid4(), "user_id": owner_id, "name": "Starter Project", "description": None},
        {
            "id": uuid4(),
            "user_id": owner_id,
            "name": "Renamed starter",
            "description": "Manage your own flows. Download and upload projects.",
        },
        {"id": uuid4(), "user_id": owner_id, "name": "Configured starter", "description": None},
        {"id": uuid4(), "user_id": owner_id, "name": "Team project", "description": None},
        {"id": uuid4(), "user_id": None, "name": "Starter Project", "description": None},
    ]
    with engine.begin() as connection:
        connection.execute(folder.insert(), rows)
        monkeypatch.setattr(_MIGRATION, "op", Operations(MigrationContext.configure(connection)))
        _MIGRATION.upgrade()
        migrated = sa.Table("folder", sa.MetaData(), autoload_with=connection)
        flags = {
            UUID(str(project_id)): is_personal
            for project_id, is_personal in connection.execute(sa.select(migrated.c.id, migrated.c.is_personal))
        }
        assert [flags[row["id"]] for row in rows] == [True, True, True, False, False]

        _MIGRATION.downgrade()
        assert "is_personal" not in {column["name"] for column in sa.inspect(connection).get_columns("folder")}

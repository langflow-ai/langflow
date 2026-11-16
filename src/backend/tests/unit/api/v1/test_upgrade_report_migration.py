"""Report history migration matches its models on SQLite and PostgreSQL."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from langflow.services.database.models.upgrade_report import UpgradeReport, UpgradeReportRepair
from sqlmodel import SQLModel


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
def test_report_migration_matches_metadata_and_is_reversible(dialect, tmp_path):
    url = f"sqlite:///{tmp_path / 'report.db'}" if dialect == "sqlite" else os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("LANGFLOW_TEST_POSTGRES_URL is not set")
    path = Path(__file__).parents[4] / "base/langflow/alembic/versions/8f1a2b3c4d5e_upgrade_report_history.py"
    spec = importlib.util.spec_from_file_location("report_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine(url)
    schema = f"report_{uuid4().hex}"
    try:
        with engine.connect() as connection:
            if dialect == "postgresql":
                connection.execute(sa.schema.CreateSchema(schema))
                connection.exec_driver_sql(f'SET search_path TO "{schema}"')
                connection.commit()
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                module.upgrade()
                module.upgrade()
            metadata = sa.MetaData(naming_convention=SQLModel.metadata.naming_convention)
            UpgradeReport.__table__.to_metadata(metadata)
            UpgradeReportRepair.__table__.to_metadata(metadata)
            assert compare_metadata(context, metadata) == []
            with Operations.context(context):
                module.downgrade()
            assert not sa.inspect(connection).has_table("upgrade_report")
            assert not sa.inspect(connection).has_table("upgrade_report_repair")
            connection.commit()
    finally:
        if dialect == "postgresql":
            with engine.begin() as connection:
                connection.execute(sa.schema.DropSchema(schema, cascade=True))
        engine.dispose()

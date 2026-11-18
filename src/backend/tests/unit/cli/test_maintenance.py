"""Offline controls change only the maintenance row and never bootstrap the app."""

import json

import pytest
from langflow.cli.maintenance import maintenance_app
from langflow.services.database.models.jobs.model import Job
from langflow.services.database.models.maintenance import MaintenanceState
from sqlalchemy import create_engine, inspect, select
from typer.testing import CliRunner


@pytest.fixture
def offline_database(tmp_path, monkeypatch):
    path = tmp_path / "offline.db"
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    MaintenanceState.__table__.create(engine)
    Job.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(MaintenanceState.__table__.insert().values(id=1, enabled=False))
    monkeypatch.setenv("MAINTENANCE_TEST_DATABASE", url)
    yield engine
    engine.dispose()


def test_offline_commands_persist_the_flag_without_schema_changes(offline_database):
    runner = CliRunner()
    before = inspect(offline_database).get_table_names()
    on = runner.invoke(
        maintenance_app,
        ["on", "--database-url-env", "MAINTENANCE_TEST_DATABASE", "--reason", "rehearsal"],
    )
    assert on.exit_code == 0, on.output
    assert json.loads(on.output)["maintenance"] is True
    status = runner.invoke(maintenance_app, ["status", "--database-url-env", "MAINTENANCE_TEST_DATABASE"])
    assert status.exit_code == 0, status.output
    assert json.loads(status.output)["reason"] == "rehearsal"
    off = runner.invoke(maintenance_app, ["off", "--database-url-env", "MAINTENANCE_TEST_DATABASE"])
    assert off.exit_code == 0, off.output
    assert json.loads(off.output)["maintenance"] is False
    assert inspect(offline_database).get_table_names() == before
    with offline_database.connect() as connection:
        assert connection.execute(select(MaintenanceState.enabled)).scalar_one() is False


def test_offline_controls_refuse_an_unmigrated_database(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    monkeypatch.setenv("MAINTENANCE_TEST_DATABASE", f"sqlite:///{path}")
    result = CliRunner().invoke(maintenance_app, ["on", "--database-url-env", "MAINTENANCE_TEST_DATABASE"])
    assert result.exit_code == 1
    assert "apply the required migrations" in result.output
    with create_engine(f"sqlite:///{path}").connect() as connection:
        assert inspect(connection).get_table_names() == []

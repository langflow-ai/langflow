"""The upgrade check reads a database saved by an older release, and never changes it.

Each fixture is a ``sqlite3 .dump`` of a database that a published release created through
its own API: one user besides the auto-login one, one project, a flow whose group holds
another group, a saved component, and a saved flow version. On 1.13.0 a webhook trigger
pins that version, so it is the only release where a version still runs.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.upgrade_check import SourceDatabaseError, read_only_connection, read_source

FIXTURES = Path(__file__).parents[2] / "data" / "upgrade_check"

# Release: (alembic revision, has the trigger table)
RELEASES = {
    "1.10.0": ("b7c4d8e9f012", False),  # pragma: allowlist secret
    "1.10.3": ("d49cbced8696", False),  # pragma: allowlist secret
    "1.11.6": ("d19e7b3c5a42", False),  # pragma: allowlist secret
    "1.12.6": ("386662af02e9", False),  # pragma: allowlist secret
    "1.13.0": ("e5a7c9b1d3f2", True),  # pragma: allowlist secret
}
REVISION = RELEASES["1.13.0"][0]


def _load(release: str, folder: Path) -> Path:
    """Restore a release's dump into a new SQLite file, in rollback-journal mode like any restore."""
    database = folder / f"langflow-{release}.db"
    connection = sqlite3.connect(database)
    connection.executescript((FIXTURES / f"langflow-{release}.sql").read_text(encoding="utf-8"))
    connection.close()
    return database


def _url(database: Path) -> str:
    return f"sqlite:///{database}"


def _side_files(database: Path) -> list[Path]:
    return [path for path in (Path(f"{database}-wal"), Path(f"{database}-shm")) if path.exists()]


def _group_nodes(nodes: list[dict]) -> list[dict]:
    return [node for node in nodes if node["data"].get("node", {}).get("flow")]


@pytest.mark.parametrize("release", RELEASES)
def test_reads_a_database_each_release_saved(release, tmp_path):
    revision, has_triggers = RELEASES[release]
    database = _load(release, tmp_path)
    before = database.read_bytes()

    source = read_source(_url(database))

    assert source.dialect == "sqlite"
    assert source.alembic_revisions == [revision]
    users = {user.username: user for user in source.users}
    assert set(users) == {"langflow", "fixture-user"}
    project = next(project for project in source.projects if project.name == "Fixture project")

    flows = {flow.name: flow for flow in source.flows}
    assert set(flows) == {"Fixture nested groups", "Fixture saved component"}
    flow, component = flows["Fixture nested groups"], flows["Fixture saved component"]
    assert (flow.is_component, component.is_component) == (False, True)
    assert flow.folder_id == component.folder_id == project.id
    # The auto-login superuser made them through the API.
    assert flow.user_id == component.user_id == users["langflow"].id
    assert flow.updated_at
    assert flow.data_error is None
    [outer] = _group_nodes(flow.data["nodes"])
    [inner] = _group_nodes(outer["data"]["node"]["flow"]["data"]["nodes"])
    assert {node["data"]["type"] for node in inner["data"]["node"]["flow"]["data"]["nodes"]} == {
        "TextInput",
        "ChatOutput",
    }
    assert [node["data"]["type"] for node in component.data["nodes"]] == ["ChatInput"]

    assert source.has_flow_versions
    assert source.has_deployments
    assert source.has_triggers is has_triggers
    if has_triggers:
        [version] = source.flow_versions
        assert version.flow_id == flow.id
        assert version.version_number == 1
        assert len(version.pinned_by_triggers) == 1
        assert version.attached_to_deployments == ()
        assert version.data["nodes"] == flow.data["nodes"]
    else:
        # Versions exist, but nothing pins them or has them attached, so none still runs.
        assert source.flow_versions == []

    assert database.read_bytes() == before
    assert _side_files(database) == []


def test_the_reader_connection_refuses_writes(tmp_path):
    database = _load("1.13.0", tmp_path)
    before = database.read_bytes()

    with read_only_connection(_url(database)) as connection, pytest.raises(sa.exc.OperationalError, match="readonly"):
        connection.execute(sa.text("DELETE FROM flow"))

    assert database.read_bytes() == before


def test_wal_mode_database_keeps_its_bytes(tmp_path):
    """Langflow's own databases are in WAL mode; reading one may add -wal and -shm, never change the file."""
    database = _load("1.13.0", tmp_path)
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.close()
    before = database.read_bytes()

    source = read_source(_url(database))

    assert {flow.name for flow in source.flows} == {"Fixture nested groups", "Fixture saved component"}
    assert database.read_bytes() == before


def test_wal_mode_database_in_a_read_only_folder(tmp_path):
    """SQLite needs the -shm file next to a WAL database even to read it; a read-only mount refuses that."""
    folder = tmp_path / "data"
    folder.mkdir()
    database = folder / "langflow.db"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    connection.execute("INSERT INTO alembic_version VALUES (?)", (REVISION,))
    connection.commit()
    connection.close()
    folder.chmod(0o555)
    try:
        try:
            source = read_source(_url(database))
        except SourceDatabaseError as exc:
            assert "Mount the folder writable for the check" in str(exc)  # noqa: PT017
            assert "copy the database into a writable folder" in str(exc)  # noqa: PT017
        else:
            # A user the folder permissions do not bind, such as root in a container, reads normally.
            assert source.alembic_revisions == [REVISION]
    finally:
        folder.chmod(0o755)


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:", "mysql://user@localhost/langflow"])
def test_refuses_what_it_cannot_read(url):
    with pytest.raises(ValueError, match=r"SQLite|PostgreSQL"):
        read_source(url)


def test_missing_sqlite_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="no SQLite database"):
        read_source(_url(tmp_path / "missing.db"))


def test_reading_starts_no_service_and_writes_no_secret_key(tmp_path):
    """The check reads with this release's code but must not build its settings, which save a secret key."""
    database = _load("1.12.6", tmp_path)
    config = tmp_path / "config"
    config.mkdir()
    script = (
        "import json, sys\n"
        "from langflow.upgrade_check import read_source\n"
        "from lfx.services.manager import get_service_manager\n"
        "source = read_source(sys.argv[1])\n"
        "print(json.dumps({'flows': len(source.flows), 'services': sorted(get_service_manager().services)}))\n"
    )
    env = {**os.environ, "LANGFLOW_CONFIG_DIR": str(config), "DO_NOT_TRACK": "true"}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, _url(database)], env=env, capture_output=True, text=True, check=True
    )

    assert json.loads(result.stdout.strip().splitlines()[-1]) == {"flows": 2, "services": []}
    assert list(config.iterdir()) == []


def test_postgres_source_is_read_in_a_read_only_transaction():
    admin_url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL") or os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not admin_url:
        pytest.skip("LANGFLOW_TEST_POSTGRES_URL or LANGFLOW_TEST_DATABASE_URI is not set")
    schema = f"upgrade_check_{uuid4().hex}"
    url = sa.make_url(admin_url).update_query_dict({"options": f"-csearch_path={schema}"})
    admin = sa.create_engine(admin_url)
    user_id, folder_id, flow_id, version_id, trigger_id = (uuid4() for _ in range(5))
    flow_data = {"nodes": [{"id": "ChatInput-1", "data": {"type": "ChatInput"}}], "edges": []}
    with admin.begin() as connection:
        connection.execute(sa.schema.CreateSchema(schema))
    try:
        writer = sa.create_engine(url)
        with writer.begin() as connection:
            for statement in (
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)",
                'CREATE TABLE "user" (id UUID PRIMARY KEY, username VARCHAR NOT NULL)',
                "CREATE TABLE folder (id UUID PRIMARY KEY, name VARCHAR NOT NULL)",
                "CREATE TABLE flow (id UUID PRIMARY KEY, name VARCHAR, data JSON, user_id UUID, folder_id UUID,"
                " is_component BOOLEAN, updated_at TIMESTAMP WITH TIME ZONE)",
                "CREATE TABLE flow_version (id UUID PRIMARY KEY, flow_id UUID, user_id UUID, data JSON,"
                " version_number INTEGER, created_at TIMESTAMP)",
                'CREATE TABLE "trigger" (id UUID PRIMARY KEY, flow_version_id UUID)',
            ):
                connection.execute(sa.text(statement))
            connection.execute(sa.text("INSERT INTO alembic_version VALUES (:revision)"), {"revision": REVISION})
            connection.execute(
                sa.text('INSERT INTO "user" VALUES (:id, :name)'), {"id": user_id, "name": "fixture-user"}
            )
            connection.execute(sa.text("INSERT INTO folder VALUES (:id, 'Fixture project')"), {"id": folder_id})
            connection.execute(
                sa.text("INSERT INTO flow VALUES (:id, 'Fixture flow', :data, :user_id, :folder_id, false, now())"),
                {"id": flow_id, "data": json.dumps(flow_data), "user_id": user_id, "folder_id": folder_id},
            )
            connection.execute(
                sa.text("INSERT INTO flow_version VALUES (:id, :flow_id, :user_id, :data, 1, now())"),
                {"id": version_id, "flow_id": flow_id, "user_id": user_id, "data": json.dumps(flow_data)},
            )
            connection.execute(
                sa.text('INSERT INTO "trigger" VALUES (:id, :version_id)'), {"id": trigger_id, "version_id": version_id}
            )
        writer.dispose()

        source = read_source(url.render_as_string(hide_password=False))

        assert source.dialect == "postgresql"
        assert source.alembic_revisions == [REVISION]
        assert [(user.id, user.username) for user in source.users] == [(str(user_id), "fixture-user")]
        [flow] = source.flows
        assert (flow.id, flow.folder_id, flow.is_component, flow.data) == (
            str(flow_id),
            str(folder_id),
            False,
            flow_data,
        )
        assert (source.has_triggers, source.has_deployments) == (True, False)
        [version] = source.flow_versions
        assert (version.id, version.pinned_by_triggers) == (str(version_id), (str(trigger_id),))
        with (
            read_only_connection(url.render_as_string(hide_password=False)) as connection,
            pytest.raises(sa.exc.InternalError, match="read-only transaction"),
        ):
            connection.execute(sa.text("DELETE FROM flow"))
    finally:
        with admin.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()

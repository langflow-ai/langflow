"""The upgrade check reads a database saved by an older release, and never changes it.

Each fixture is a ``sqlite3 .dump`` of a database that a published release created through
its own API: one user besides the auto-login one, one project, a flow whose group holds
another group, a saved component, and a saved flow version. On 1.13.0 a webhook trigger
pins that version, so it is the only release where a version still runs. From 1.12 on, a
release keeps catalog rules, and none of the fixtures has any.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.upgrade_check import SourceCatalogPolicy, SourceDatabaseError, open_source, read_only_connection
from lfx.services.catalog_policy import CatalogPolicySnapshot
from lfx.services.policy_bundle import policy_bundle_content_hash

FIXTURES = Path(__file__).parents[2] / "data" / "upgrade_check"

# Release: (alembic revision, has the trigger table, has the policy bundle tables)
RELEASES = {
    "1.10.0": ("b7c4d8e9f012", False, False),  # pragma: allowlist secret
    "1.10.3": ("d49cbced8696", False, False),  # pragma: allowlist secret
    "1.11.6": ("d19e7b3c5a42", False, False),  # pragma: allowlist secret
    "1.12.6": ("386662af02e9", False, True),  # pragma: allowlist secret
    "1.13.0": ("e5a7c9b1d3f2", True, True),  # pragma: allowlist secret
}
REVISION = RELEASES["1.13.0"][0]


def _load(release: str, folder: Path) -> Path:
    """Restore a release's dump into a new SQLite file, in rollback-journal mode like any restore."""
    database = folder / f"langflow-{release}.db"
    connection = sqlite3.connect(database)
    connection.executescript((FIXTURES / f"langflow-{release}.sql").read_text(encoding="utf-8"))
    connection.close()
    return database


def _block_components(database: Path, release: str, *keys: str) -> None:
    """Write what the release writes when an admin replaces the blocked component keys.

    ``replace_policy_bundle_state`` activates a new bundle revision, then copies the global rules
    into ``model_provider_policy`` and ``catalog_policy_rule``, which the release keeps for downgrades.
    """
    connection = sqlite3.connect(database)
    [(revision,)] = connection.execute("SELECT revision FROM policy_bundle_active")
    [(admin,)] = connection.execute("SELECT id FROM user WHERE username = 'langflow'")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    bundle = {
        "revision": revision + 1,
        "initialized": 1,
        "approved_provider_ids": "[]",
        "blocked_component_keys": json.dumps(sorted(keys)),
        "blocked_template_keys": "[]",
        "blocked_model_keys": "[]",
        "content_hash": policy_bundle_content_hash(
            approved_provider_ids=(), blocked_component_keys=keys, blocked_template_keys=()
        ),
        "source": "api",
        "created_by": admin,
        "created_at": now,
        "reason": "Replace blocked component catalog keys",
        "rollback_of_revision": None,
    }
    if release == "1.13.0":
        bundle |= {"approved_integration_provider_ids": "[]", "blocked_integration_action_keys": "[]"}
    with connection:
        connection.execute(
            "UPDATE policy_bundle_active SET revision = ?, initialized = 1, updated_at = CURRENT_TIMESTAMP"
            " WHERE id = 1",
            (revision + 1,),
        )
        columns, placeholders = ", ".join(bundle), ", ".join("?" for _ in bundle)
        connection.execute(
            f"INSERT INTO policy_bundle_revision ({columns}) VALUES ({placeholders})",  # noqa: S608
            tuple(bundle.values()),
        )
        connection.execute(
            "UPDATE model_provider_policy SET approved_provider_ids = '[]', version = ? WHERE id = 1", (revision + 1,)
        )
        for key in keys:
            connection.execute(
                "INSERT INTO catalog_policy_rule (id, resource_kind, resource_key, mode, scope, domain_id, created_by,"
                " created_at, updated_at) VALUES (?, 'component', ?, 'block', 'global', NULL, ?, ?, ?)",
                (uuid4().hex, key, admin, now, now),
            )
    connection.close()


def _execute(database: Path, statement: str, parameters: tuple = ()) -> None:
    connection = sqlite3.connect(database)
    with connection:
        connection.execute(statement, parameters)
    connection.close()


def _url(database: Path) -> str:
    return f"sqlite:///{database}"


def _side_files(database: Path) -> list[Path]:
    return [path for path in (Path(f"{database}-wal"), Path(f"{database}-shm")) if path.exists()]


def _group_nodes(nodes: list[dict]) -> list[dict]:
    return [node for node in nodes if node["data"].get("node", {}).get("flow")]


@pytest.mark.parametrize("release", RELEASES)
def test_reads_a_database_each_release_saved(release, tmp_path):
    revision, has_triggers, has_policy_bundle = RELEASES[release]
    database = _load(release, tmp_path)
    before = database.read_bytes()

    with open_source(_url(database)) as source:
        flows = {flow.name: flow for flow in source.flows()}
        versions = list(source.flow_versions())
        policy = source.catalog_policy()

    assert source.dialect == "sqlite"
    assert source.alembic_revisions == [revision]
    users = {user.username: user for user in source.users}
    assert set(users) == {"langflow", "fixture-user"}
    project = next(project for project in source.projects if project.name == "Fixture project")

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
        [version] = versions
        assert version.flow_id == flow.id
        assert version.version_number == 1
        assert len(version.pinned_by_triggers) == 1
        assert version.attached_to_deployments == ()
        assert version.data["nodes"] == flow.data["nodes"]
    else:
        # Versions exist, but nothing pins them or has them attached, so none still runs.
        assert versions == []
    assert source.has_policy_bundle is has_policy_bundle
    assert policy == SourceCatalogPolicy(CatalogPolicySnapshot())

    assert database.read_bytes() == before
    assert _side_files(database) == []


@pytest.mark.parametrize("release", ["1.12.6", "1.13.0"])
def test_reads_the_catalog_rules_the_upgraded_server_loads(release, tmp_path):
    database = _load(release, tmp_path)
    _block_components(database, release, "ChatInput")
    # A rule only catalog_policy_rule holds, as a writer that skipped the bundle would leave it.
    _execute(
        database,
        "INSERT INTO catalog_policy_rule (id, resource_kind, resource_key) VALUES (?, 'component', 'TextInput')",
        (uuid4().hex,),
    )
    before = database.read_bytes()

    with open_source(_url(database)) as source:
        policy = source.catalog_policy()

    # The server loads the active bundle and never reads catalog_policy_rule, so TextInput stays allowed.
    assert policy == SourceCatalogPolicy(CatalogPolicySnapshot(blocked_component_keys={"ChatInput"}))
    assert database.read_bytes() == before


@pytest.mark.parametrize(
    ("statement", "blocked", "error"),
    [
        ("DELETE FROM policy_bundle_active", set(), "the active policy bundle is missing"),
        ("UPDATE policy_bundle_active SET revision = 7", set(), "policy bundle revision 7 is missing"),
        (
            "UPDATE policy_bundle_revision SET blocked_template_keys = 'not json' WHERE revision = 2",
            {"ChatInput"},
            "blocked_template_keys could not be read",
        ),
        (
            "UPDATE policy_bundle_revision SET blocked_component_keys = 'null' WHERE revision = 2",
            set(),
            "blocked_component_keys could not be read",
        ),
    ],
)
def test_catalog_rules_that_cannot_be_read_are_reported(statement, blocked, error, tmp_path):
    """The server's own read fails on each of these, and the check keeps what it can read."""
    database = _load("1.13.0", tmp_path)
    _block_components(database, "1.13.0", "ChatInput")
    _execute(database, statement)

    with open_source(_url(database)) as source:
        policy = source.catalog_policy()

    assert policy.snapshot == CatalogPolicySnapshot(blocked_component_keys=blocked)
    assert error in policy.data_error


@pytest.mark.usefixtures("client")
async def test_reads_while_langflow_runs_in_the_same_process(tmp_path):
    """Langflow's database service sets its SQLite pragmas on every connection in the process.

    The journal mode pragma cannot run on a read-only connection, and that must not stop the read.
    """
    database = _load("1.13.0", tmp_path)
    before = database.read_bytes()

    with open_source(_url(database)) as source:
        names = {flow.name for flow in source.flows()}

    assert names == {"Fixture nested groups", "Fixture saved component"}
    assert database.read_bytes() == before


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

    with open_source(_url(database)) as source:
        names = {flow.name for flow in source.flows()}

    assert names == {"Fixture nested groups", "Fixture saved component"}
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
            with open_source(_url(database)) as source:
                pass
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
    with pytest.raises(ValueError, match=r"SQLite|PostgreSQL"), open_source(url):
        pass


def test_missing_sqlite_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="no SQLite database"), open_source(_url(tmp_path / "missing.db")):
        pass


def test_reading_starts_no_service_and_writes_no_secret_key(tmp_path):
    """The check reads with this release's code but must not build its settings, which save a secret key."""
    database = _load("1.12.6", tmp_path)
    _block_components(database, "1.12.6", "ChatInput")
    config = tmp_path / "config"
    config.mkdir()
    script = (
        "import json, sys\n"
        "from langflow.upgrade_check import open_source\n"
        "from lfx.services.manager import get_service_manager\n"
        "with open_source(sys.argv[1]) as source:\n"
        "    flows = len(list(source.flows()))\n"
        "    blocked = sorted(source.catalog_policy().snapshot.blocked_component_keys)\n"
        "services = sorted(get_service_manager().services)\n"
        "print(json.dumps({'flows': flows, 'blocked': blocked, 'services': services}))\n"
    )
    env = {**os.environ, "LANGFLOW_CONFIG_DIR": str(config), "DO_NOT_TRACK": "true"}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, _url(database)], env=env, capture_output=True, text=True, check=True
    )

    assert json.loads(result.stdout.strip().splitlines()[-1]) == {"flows": 2, "blocked": ["ChatInput"], "services": []}
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
                "CREATE TABLE policy_bundle_active (id INTEGER PRIMARY KEY, revision INTEGER NOT NULL)",
                "CREATE TABLE policy_bundle_revision (revision INTEGER PRIMARY KEY, blocked_component_keys JSON,"
                " blocked_template_keys JSON)",
                "INSERT INTO policy_bundle_active VALUES (1, 2)",
                """INSERT INTO policy_bundle_revision VALUES (2, '["ChatInput"]', '["Basic Prompting"]')""",
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

        with open_source(url.render_as_string(hide_password=False)) as source:
            flows = list(source.flows())
            versions = list(source.flow_versions())
            policy = source.catalog_policy()

        assert source.dialect == "postgresql"
        assert source.alembic_revisions == [REVISION]
        assert [(user.id, user.username) for user in source.users] == [(str(user_id), "fixture-user")]
        [flow] = flows
        assert (flow.id, flow.folder_id, flow.is_component, flow.data) == (
            str(flow_id),
            str(folder_id),
            False,
            flow_data,
        )
        assert (source.has_triggers, source.has_deployments) == (True, False)
        [version] = versions
        assert (version.id, version.pinned_by_triggers) == (str(version_id), (str(trigger_id),))
        assert policy == SourceCatalogPolicy(CatalogPolicySnapshot({"ChatInput"}, {"Basic Prompting"}))
        with (
            read_only_connection(url.render_as_string(hide_password=False)) as connection,
            pytest.raises(sa.exc.InternalError, match="read-only transaction"),
        ):
            connection.execute(sa.text("DELETE FROM flow"))
    finally:
        with admin.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()

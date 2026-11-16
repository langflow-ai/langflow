"""Real-runner regression coverage for the transaction flow timeline index."""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from langflow.services.database.models.transactions.model import TransactionTable
from sqlalchemy import create_engine, inspect, text

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PREVIOUS = "7fd2c80e5a39"  # pragma: allowlist secret
_INDEX = "ix_transaction_flow_id_timestamp"


def test_transaction_metadata_index():
    indexes = {index.name: index for index in TransactionTable.__table__.indexes}
    assert _INDEX in indexes
    assert [column.name for column in indexes[_INDEX].columns] == ["flow_id", "timestamp"]
    assert not indexes[_INDEX].unique


def _indexes(connection):
    return {index["name"]: index for index in inspect(connection).get_indexes("transaction")}


def test_transaction_index_runner_roundtrip(db_url):  # noqa: F811
    cfg = _make_alembic_cfg(db_url)
    command.upgrade(cfg, _PREVIOUS)
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            identifier = uuid.uuid4()
            connection.execute(
                text(
                    'INSERT INTO "transaction" (id,flow_id,timestamp,vertex_id,status,inputs) '
                    "VALUES (:id,:flow,CURRENT_TIMESTAMP,'witness','success',:inputs)"
                ),
                {
                    "id": str(identifier) if engine.dialect.name == "postgresql" else identifier.hex,
                    "flow": str(uuid.uuid4()) if engine.dialect.name == "postgresql" else uuid.uuid4().hex,
                    "inputs": '{"keep":"value"}',
                },
            )
        for _ in range(2):
            command.upgrade(cfg, "head")
            with engine.connect() as connection:
                assert _indexes(connection)[_INDEX]["column_names"] == ["flow_id", "timestamp"]
                assert connection.scalar(text("SELECT count(*) FROM \"transaction\" WHERE vertex_id='witness'")) == 1
            command.stamp(cfg, _PREVIOUS)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, _PREVIOUS)
        with engine.connect() as connection:
            assert _INDEX not in _indexes(connection)
            assert connection.scalar(text("SELECT count(*) FROM \"transaction\" WHERE vertex_id='witness'")) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == _PREVIOUS
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        engine.dispose()


@pytest.fixture
def migration():
    import importlib

    return importlib.import_module("langflow.alembic.versions.9e7a4c2b1d60_index_transaction_flow_timeline")


def _invoke(connection, function):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    connection.commit()
    context = MigrationContext.configure(connection)
    with context.begin_transaction(), Operations.context(context):
        function()
    connection.commit()


@pytest.fixture
def minimal_engine(db_url):  # noqa: F811
    engine = create_engine(_engine_url(db_url))
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE "transaction" (id integer,flow_id uuid,timestamp timestamp)')
        connection.exec_driver_sql('INSERT INTO "transaction" (id) VALUES (42)')
    try:
        yield engine
    finally:
        engine.dispose()


def test_minimal_missing_and_roundtrip(minimal_engine, migration, caplog):
    with minimal_engine.connect() as connection:
        _invoke(connection, migration.downgrade)
        assert "absent" in caplog.text
        for _ in range(2):
            _invoke(connection, migration.upgrade)
            assert _indexes(connection)[_INDEX]["column_names"] == ["flow_id", "timestamp"]
        _invoke(connection, migration.downgrade)
        assert _INDEX not in _indexes(connection)
        connection.exec_driver_sql('DROP TABLE "transaction"')
        connection.commit()
        _invoke(connection, migration.upgrade)
        _invoke(connection, migration.downgrade)


@pytest.mark.parametrize("definition", ["wrong-column", "unique", "partial", "wrong-table", "expression", "desc"])
def test_conflicts_preserved(minimal_engine, migration, caplog, definition):
    with minimal_engine.connect() as connection:
        connection.exec_driver_sql("CREATE TABLE other (flow_id uuid,timestamp timestamp)")
        sql = {
            "wrong-column": f'CREATE INDEX {_INDEX} ON "transaction" (timestamp,flow_id)',
            "unique": f'CREATE UNIQUE INDEX {_INDEX} ON "transaction" (flow_id,timestamp)',
            "partial": f'CREATE INDEX {_INDEX} ON "transaction" (flow_id,timestamp) WHERE id>0',
            "wrong-table": f"CREATE INDEX {_INDEX} ON other (flow_id,timestamp)",
            "expression": f'CREATE INDEX {_INDEX} ON "transaction" ((id+1),timestamp)',
            "desc": f'CREATE INDEX {_INDEX} ON "transaction" (flow_id DESC,timestamp)',
        }[definition]
        connection.exec_driver_sql(sql)
        connection.commit()
        with pytest.raises(RuntimeError, match="conflicting non-owned"):
            _invoke(connection, migration.upgrade)
        connection.rollback()
        _invoke(connection, migration.downgrade)
        assert "Leaving conflicting" in caplog.text
        with pytest.raises(RuntimeError, match="conflicting non-owned"):
            _invoke(connection, migration.upgrade)
        connection.rollback()
        assert connection.scalar(text('SELECT id FROM "transaction"')) == 42
        query = (
            "SELECT count(*) FROM pg_class WHERE relname=:name"
            if connection.dialect.name == "postgresql"
            else "SELECT count(*) FROM sqlite_master WHERE name=:name"
        )
        assert connection.scalar(text(query), {"name": _INDEX}) == 1


@pytest.mark.parametrize("definition", ["relation", "brin", "include", "custom-opclass", "partitioned-target"])
def test_postgres_signature_conflicts(minimal_engine, migration, caplog, definition):
    if minimal_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL catalog definitions")
    with minimal_engine.connect() as connection:
        if definition == "relation":
            connection.exec_driver_sql(f"CREATE TABLE {_INDEX}(id integer)")
        elif definition == "partitioned-target":
            connection.exec_driver_sql('DROP TABLE "transaction"')
            connection.exec_driver_sql(
                'CREATE TABLE "transaction" (flow_id uuid,timestamp timestamp) PARTITION BY HASH(flow_id)'
            )
        else:
            if definition == "custom-opclass":
                connection.exec_driver_sql(
                    "CREATE OPERATOR CLASS probe_uuid_ops FOR TYPE uuid USING btree AS "
                    "OPERATOR 1 <(uuid,uuid), OPERATOR 2 <=(uuid,uuid), OPERATOR 3 =(uuid,uuid), "
                    "OPERATOR 4 >=(uuid,uuid), OPERATOR 5 >(uuid,uuid), FUNCTION 1 uuid_cmp(uuid,uuid)"
                )
            ddl = {
                "brin": f'CREATE INDEX {_INDEX} ON "transaction" USING brin (flow_id,timestamp)',
                "include": f'CREATE INDEX {_INDEX} ON "transaction" (flow_id,timestamp) INCLUDE(id)',
                "custom-opclass": f'CREATE INDEX {_INDEX} ON "transaction" (flow_id probe_uuid_ops,timestamp)',
            }[definition]
            connection.exec_driver_sql(ddl)
        connection.commit()
        with pytest.raises(RuntimeError, match=r"conflicting non-owned|ordinary table"):
            _invoke(connection, migration.upgrade)
        connection.rollback()
        _invoke(connection, migration.downgrade)
        if definition == "partitioned-target":
            assert "leaving non-owned relation unchanged" in caplog.text
        else:
            assert connection.scalar(text('SELECT id FROM "transaction"')) == 42


def test_postgres_schema_resolution(minimal_engine, migration):
    if minimal_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL search_path")
    with minimal_engine.connect() as connection:
        connection.exec_driver_sql("CREATE SCHEMA empty_first")
        connection.exec_driver_sql('CREATE SCHEMA "Later Schema"')
        connection.exec_driver_sql('ALTER TABLE "transaction" SET SCHEMA "Later Schema"')
        connection.exec_driver_sql("CREATE TABLE decoy(id integer)")
        connection.exec_driver_sql(f"CREATE INDEX {_INDEX} ON decoy(id)")
        connection.exec_driver_sql('SET search_path=empty_first,"Later Schema",public')
        connection.commit()
        _invoke(connection, migration.upgrade)
        state = migration._postgres_state(connection)
        assert state[1] == "Later Schema"
        assert state[2]["matches"]
        _invoke(connection, migration.downgrade)
        assert connection.scalar(text("SELECT to_regclass(:name)"), {"name": f"public.{_INDEX}"}) is not None
        assert connection.scalar(text("SELECT to_regclass(:name)"), {"name": f'"Later Schema".{_INDEX}'}) is None


def test_postgres_real_interruption_and_active_refusal(db_url, migration):  # noqa: F811
    """Cancel only our real Alembic backend after its catalog commit, then retry."""
    if not db_url.startswith("postgres"):
        pytest.skip("PostgreSQL concurrent build")
    import threading
    import time
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    cfg = _make_alembic_cfg(db_url)
    command.upgrade(cfg, _PREVIOUS)
    engine = create_engine(_engine_url(db_url))
    label = f"transaction-index-{uuid.uuid4().hex}"
    url = urlsplit(db_url)
    query = dict(parse_qsl(url.query))
    query["application_name"] = label
    query["options"] = "-c statement_timeout=20000"
    worker_cfg = _make_alembic_cfg(
        urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), url.fragment)).replace("%", "%%")
    )
    errors = []
    observer_role = "index_observer_" + uuid.uuid4().hex
    pid = None

    def build():
        try:
            command.upgrade(worker_cfg, "head")
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=build)
    blocker = engine.connect()
    admin = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        # An older writer makes CIC wait after creating its committed catalog row.
        blocker.exec_driver_sql(
            'INSERT INTO "transaction" (id,flow_id,timestamp,vertex_id,status) '
            "VALUES (gen_random_uuid(),gen_random_uuid(),CURRENT_TIMESTAMP,'blocker','success')"
        )
        worker.start()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            progress = admin.execute(
                text(
                    "SELECT a.pid,p.phase FROM pg_stat_activity a "
                    "JOIN pg_stat_progress_create_index p ON p.pid=a.pid "
                    "WHERE a.application_name=:label"
                ),
                {"label": label},
            ).first()
            if progress and progress[1] == "waiting for writers before build":
                pid = progress[0]
                break
            time.sleep(0.02)
        assert pid is not None, "owned runner did not reach the committed pre-build wait"
        flags = admin.execute(
            text("SELECT indisvalid,indisready,indislive FROM pg_index WHERE indexrelid=to_regclass(:name)"),
            {"name": _INDEX},
        ).one()
        assert tuple(flags) == (False, False, True)
        # A different writer commits while the build is demonstrably still active.
        admin.exec_driver_sql(
            'INSERT INTO "transaction" (id,flow_id,timestamp,vertex_id,status) '
            "VALUES (gen_random_uuid(),gen_random_uuid(),CURRENT_TIMESTAMP,'during','success')"
        )
        assert worker.is_alive()
        for direction in (migration.upgrade, migration.downgrade):
            with engine.connect() as connection, pytest.raises(RuntimeError, match="retry after"):
                _invoke(connection, direction)
        # A non-superuser unrelated role sees redacted progress and must refuse.
        admin.exec_driver_sql(f"CREATE ROLE {observer_role}")
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql(f"SET ROLE {observer_role}")
                redacted = connection.execute(
                    text("SELECT relid,phase FROM pg_stat_progress_create_index WHERE pid=:pid"), {"pid": pid}
                ).one()
                assert tuple(redacted) == (None, None)
                try:
                    # An unrelated OID has no matching lock: ONLY redacted
                    # progress can refuse this probe, isolating that branch.
                    decoy_oid = admin.scalar(text("SELECT 'pg_catalog.pg_class'::regclass::oid"))
                    with pytest.raises(RuntimeError, match="retry after"):
                        migration._require_idle(connection, decoy_oid, "public", 0)
                    with pytest.raises(RuntimeError, match="retry after"):
                        _invoke(connection, migration.upgrade)
                finally:
                    connection.rollback()
                    connection.exec_driver_sql("RESET ROLE")
                    connection.commit()
        finally:
            admin.exec_driver_sql(f"DROP ROLE {observer_role}")
        admin.execute(text("SELECT pg_cancel_backend(:pid)"), {"pid": pid})
        worker.join(8)
        assert not worker.is_alive()
        assert errors
        assert admin.scalar(text("SELECT version_num FROM alembic_version")) == _PREVIOUS
        assert tuple(
            admin.execute(
                text("SELECT indisvalid,indisready,indislive FROM pg_index WHERE indexrelid=to_regclass(:name)"),
                {"name": _INDEX},
            ).one()
        ) == (False, False, True)
        blocker.rollback()
        # No builder exists now, but a conservative unrelated table lock refuses.
        blocker.exec_driver_sql('LOCK TABLE "transaction" IN SHARE UPDATE EXCLUSIVE MODE')
        with engine.connect() as connection, pytest.raises(RuntimeError, match="retry after"):
            _invoke(connection, migration.upgrade)
        blocker.rollback()
        command.upgrade(cfg, "head")
        assert admin.scalar(text("SELECT count(*) FROM \"transaction\" WHERE vertex_id='during'")) == 1
        assert tuple(
            admin.execute(
                text("SELECT indisvalid,indisready FROM pg_index WHERE indexrelid=to_regclass(:name)"), {"name": _INDEX}
            ).one()
        ) == (True, True)
    finally:
        blocker.rollback()
        if worker.is_alive():
            owned_pids = (
                admin.execute(text("SELECT pid FROM pg_stat_activity WHERE application_name=:label"), {"label": label})
                .scalars()
                .all()
            )
            for owned_pid in owned_pids:
                admin.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": owned_pid})
        if worker.ident is not None:
            worker.join(8)
        blocker.close()
        admin.close()
        engine.dispose()
        assert not worker.is_alive()


def test_revision_graph_and_validator(migration):
    from pathlib import Path

    from alembic.script import ScriptDirectory
    from langflow.alembic.migration_validator import MigrationValidator

    scripts = ScriptDirectory.from_config(_make_alembic_cfg("sqlite+aiosqlite://"))
    heads = scripts.get_heads()
    assert len(heads) == 1
    assert migration.revision in {item.revision for item in scripts.iterate_revisions(heads[0], "base")}
    assert MigrationValidator().validate_migration_file(Path(migration.__file__))["valid"]


@pytest.mark.parametrize("release", ["1.12.6", "1.13.0"])
def test_release_dump_upgrades(release, tmp_path):
    from tests.unit.upgrade_check.test_reader import _load

    path = _load(release, tmp_path)
    cfg = _make_alembic_cfg(f"sqlite+aiosqlite:///{path}")
    command.upgrade(cfg, "head")
    command.check(cfg)
    engine = create_engine(f"sqlite:///{path}")
    try:
        with engine.connect() as connection:
            assert _INDEX in _indexes(connection)
    finally:
        engine.dispose()


def test_fresh_metadata_then_runner(db_url):  # noqa: F811
    from langflow.services.database.service import DatabaseService

    engine = create_engine(_engine_url(db_url))
    try:
        with engine.begin() as connection:
            DatabaseService._create_db_and_tables(connection)
        command.upgrade(_make_alembic_cfg(db_url), "head")
        command.check(_make_alembic_cfg(db_url))
        with engine.connect() as connection:
            assert _INDEX in _indexes(connection)
    finally:
        engine.dispose()


def test_database_service_check_upgrade_path(db_url, monkeypatch, tmp_path):  # noqa: F811
    from pathlib import Path

    from langflow.services.database.service import DatabaseService

    cfg = _make_alembic_cfg(db_url)
    command.upgrade(cfg, _PREVIOUS)
    monkeypatch.setenv("LANGFLOW_ALEMBIC_LOG_TO_STDOUT", "true")
    service = object.__new__(DatabaseService)
    service.database_url = db_url
    service.script_location = Path(cfg.get_main_option("script_location"))
    service.alembic_log_path = tmp_path / "alembic.log"
    service.alembic_log_to_stdout = True
    service._run_migrations(should_initialize_alembic=False, fix=False)
    command.check(cfg)
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            assert _INDEX in _indexes(connection)
    finally:
        engine.dispose()


def test_sqlite_case_insensitive_collision(minimal_engine, migration, caplog):
    if minimal_engine.dialect.name != "sqlite":
        pytest.skip("SQLite identifier comparison")
    with minimal_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE INDEX {_INDEX.upper()} ON "transaction" (timestamp,flow_id)')
        connection.commit()
        with pytest.raises(RuntimeError, match="conflicting non-owned"):
            _invoke(connection, migration.upgrade)
        connection.rollback()
        _invoke(connection, migration.downgrade)
        assert "Leaving conflicting" in caplog.text
        assert _INDEX.upper() in _indexes(connection)


def test_sqlite_non_index_collision(minimal_engine, migration, caplog):
    if minimal_engine.dialect.name != "sqlite":
        pytest.skip("SQLite relation collision")
    with minimal_engine.connect() as connection:
        connection.exec_driver_sql(f"CREATE TABLE {_INDEX}(id integer)")
        connection.commit()
        with pytest.raises(RuntimeError, match="conflicting non-owned"):
            _invoke(connection, migration.upgrade)
        connection.rollback()
        _invoke(connection, migration.downgrade)
        assert "Leaving conflicting" in caplog.text


def test_sqlite_same_named_trigger_is_not_an_index_conflict(minimal_engine, migration):
    if minimal_engine.dialect.name != "sqlite":
        pytest.skip("SQLite separate trigger namespace")
    with minimal_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE TRIGGER {_INDEX} AFTER INSERT ON "transaction" BEGIN SELECT 1; END')
        connection.commit()
        for _ in range(2):
            _invoke(connection, migration.upgrade)
            assert _INDEX in _indexes(connection)
        _invoke(connection, migration.downgrade)
        assert _INDEX not in _indexes(connection)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name=:name"), {"name": _INDEX}
            )
            == 1
        )

"""A deployment copy may have no flow; every other job type still must have one.

The column has to accept a null so a copy job can leave it empty, and relaxing it is exactly
what would otherwise let a workflow job be inserted with no flow at all. The check constraint
is what keeps that from happening, so these tests are about the constraint rather than the
nullability: the migration is only correct if the guard it removes is replaced.
"""

import importlib
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

pytestmark = pytest.mark.no_blockbuster

_MIGRATION = "langflow.alembic.versions.c14fe0b7508c_job_flow_id_nullable_and_deployment_"

_PRE_MIGRATION_JOB = """
CREATE TABLE job (
    job_id CHAR(32) NOT NULL PRIMARY KEY,
    flow_id CHAR(32) NOT NULL,
    status VARCHAR(11) NOT NULL,
    created_timestamp DATETIME NOT NULL,
    finished_timestamp DATETIME,
    -- VARCHAR(10) is the real pre-migration width, sized for 'evaluation'. The migration has
    -- to widen it: 'deployment_copy' is 15 characters.
    type VARCHAR(10),
    user_id CHAR(32),
    asset_id CHAR(32),
    asset_type VARCHAR,
    dedupe_key VARCHAR,
    job_metadata JSON,
    result JSON,
    error JSON
)
"""

_INSERT = (
    "INSERT INTO job (job_id, flow_id, status, created_timestamp, type) "
    "VALUES (:job_id, :flow_id, 'queued', '2026-10-22', :type)"
)


def _insert(connection, job_type, flow_id):
    connection.execute(sa.text(_INSERT), {"job_id": str(uuid4()), "flow_id": flow_id, "type": job_type})


def _flow_id_nullable(connection) -> bool:
    return next(c["nullable"] for c in sa.inspect(connection).get_columns("job") if c["name"] == "flow_id")


def _counts(connection) -> tuple[int, int]:
    return tuple(connection.execute(sa.text("SELECT count(*), count(flow_id) FROM job")).one())


@pytest.fixture
def migrated(tmp_path):
    """A ``job`` table at the pre-migration shape, with rows, upgraded."""
    migration = importlib.import_module(_MIGRATION)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'job.sqlite3'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(_PRE_MIGRATION_JOB)
        for _ in range(18):
            _insert(connection, "workflow", str(uuid4()))
        assert _flow_id_nullable(connection) is False
        operations = Operations(MigrationContext.configure(connection))
        migration.op = operations
        migration.upgrade()
        yield connection, migration


def test_should_keep_every_existing_row_when_upgrading(migrated):
    connection, _ = migrated

    assert _flow_id_nullable(connection) is True
    assert _counts(connection) == (18, 18)


def _type_width(connection) -> int:
    column = next(c for c in sa.inspect(connection).get_columns("job") if c["name"] == "type")
    return column["type"].length


def test_should_widen_the_type_column_to_fit_the_new_member(migrated):
    """``deployment_copy`` is 15 characters and the column was sized for ``evaluation`` at 10.

    SQLite does not enforce the width, so the value stores either way; what breaks is the
    declared type drifting from the model, which the phantom-migration check reports.
    """
    connection, _ = migrated

    assert _type_width(connection) == len("deployment_copy")


def test_should_accept_a_deployment_copy_with_no_flow(migrated):
    connection, _ = migrated

    _insert(connection, "deployment_copy", None)

    assert _counts(connection) == (19, 18)


@pytest.mark.parametrize("job_type", ["workflow", "ingestion", "evaluation", None])
def test_should_still_refuse_any_other_job_type_with_no_flow(migrated, job_type):
    connection, _ = migrated

    with pytest.raises(sa.exc.IntegrityError):
        _insert(connection, job_type, None)


def test_should_restore_the_not_null_and_drop_copy_rows_when_downgrading(migrated):
    connection, migration = migrated
    _insert(connection, "deployment_copy", None)

    migration.downgrade()

    assert _flow_id_nullable(connection) is False
    assert _counts(connection) == (18, 18)


def test_should_be_repeatable_when_upgraded_again_after_a_downgrade(migrated):
    connection, migration = migrated

    migration.downgrade()
    migration.upgrade()

    assert _flow_id_nullable(connection) is True
    assert _counts(connection) == (18, 18)
    _insert(connection, "deployment_copy", None)
    assert _counts(connection) == (19, 18)

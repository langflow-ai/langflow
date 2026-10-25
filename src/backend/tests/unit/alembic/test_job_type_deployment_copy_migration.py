"""The deployment_copy job type, added without loosening anything else on the job table.

A deployment copy is one job per flow, so it carries a flow like every other job, and this
migration must not relax ``flow_id``: a job inserted with no flow is refused before and after.
What it does change is the type, including on SQLite, where the column's declared width has
to grow for the new member to match the model.
"""

import importlib
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

pytestmark = pytest.mark.no_blockbuster

_MIGRATION = "langflow.alembic.versions.c14fe0b7508c_job_type_deployment_copy"

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


def _column(connection, name: str) -> dict:
    return next(c for c in sa.inspect(connection).get_columns("job") if c["name"] == name)


def _rows(connection) -> int:
    return connection.execute(sa.text("SELECT count(*) FROM job")).scalar_one()


@pytest.fixture
def migrated(tmp_path):
    """A ``job`` table at the pre-migration shape, with rows, upgraded."""
    migration = importlib.import_module(_MIGRATION)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'job.sqlite3'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(_PRE_MIGRATION_JOB)
        for _ in range(18):
            _insert(connection, "workflow", str(uuid4()))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        yield connection, migration


def test_should_keep_every_existing_row_when_upgrading(migrated):
    connection, _ = migrated

    assert _rows(connection) == 18


def test_should_widen_the_type_column_to_fit_the_new_member(migrated):
    connection, _ = migrated

    assert _column(connection, "type")["type"].length == len("deployment_copy")


def test_should_accept_a_deployment_copy_that_carries_its_flow(migrated):
    connection, _ = migrated

    _insert(connection, "deployment_copy", str(uuid4()))

    assert _rows(connection) == 19


@pytest.mark.parametrize("job_type", ["workflow", "ingestion", "evaluation", "deployment_copy", None])
def test_should_still_refuse_a_job_of_any_type_with_no_flow(migrated, job_type):
    connection, _ = migrated

    assert _column(connection, "flow_id")["nullable"] is False
    with pytest.raises(sa.exc.IntegrityError):
        _insert(connection, job_type, None)


def test_should_drop_copy_rows_and_narrow_the_column_when_downgrading(migrated):
    connection, migration = migrated
    _insert(connection, "deployment_copy", str(uuid4()))

    migration.downgrade()

    assert _rows(connection) == 18
    assert _column(connection, "type")["type"].length == len("evaluation")


def test_should_be_repeatable_when_upgraded_again_after_a_downgrade(migrated):
    connection, migration = migrated

    migration.downgrade()
    migration.upgrade()

    assert _rows(connection) == 18
    _insert(connection, "deployment_copy", str(uuid4()))
    assert _rows(connection) == 19

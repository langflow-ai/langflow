"""The existing Serving job schema is read under PostgreSQL's read-only transaction guard."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.upgrade_check.reader import read_only_connection
from langflow.upgrade_check.usage_reader import read_serving_usage


@pytest.mark.skipif(not os.environ.get("LANGFLOW_TEST_POSTGRES_URL"), reason="set LANGFLOW_TEST_POSTGRES_URL")
def test_postgres_serving_usage_preserves_source_and_normalizes_ids_and_period():
    admin_url = os.environ["LANGFLOW_TEST_POSTGRES_URL"]
    schema = f"upgrade_usage_{uuid4().hex}"
    url = sa.make_url(admin_url).update_query_dict({"options": f"-csearch_path={schema}"})
    admin = sa.create_engine(admin_url)
    engine = sa.create_engine(url)
    metadata = sa.MetaData(schema=schema)
    job = sa.Table(
        "job",
        metadata,
        sa.Column("flow_id", sa.Uuid),
        sa.Column("type", sa.Enum("workflow", "ingestion", "evaluation", name="job_type_enum", schema=schema)),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "in_progress",
                "completed",
                "failed",
                "timed_out",
                "cancelled",
                "suspended",
                name="job_status_enum",
                schema=schema,
            ),
        ),
        sa.Column("created_timestamp", sa.DateTime(timezone=True)),
    )
    flow_id = uuid4()
    try:
        with admin.begin() as connection:
            connection.execute(sa.schema.CreateSchema(schema))
        metadata.create_all(engine)
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        with engine.begin() as connection:
            connection.execute(
                job.insert(),
                [
                    {"flow_id": flow_id, "type": "workflow", "status": "completed", "created_timestamp": now},
                    {
                        "flow_id": flow_id,
                        "type": "workflow",
                        "status": "failed",
                        "created_timestamp": now.replace(microsecond=100000),
                    },
                    {"flow_id": flow_id, "type": "workflow", "status": "suspended", "created_timestamp": now},
                    {
                        "flow_id": flow_id,
                        "type": "workflow",
                        "status": "queued",
                        "created_timestamp": now.replace(day=2),
                    },
                    {
                        "flow_id": flow_id,
                        "type": "workflow",
                        "status": "cancelled",
                        "created_timestamp": now.replace(day=3),
                    },
                    {"flow_id": flow_id, "type": "ingestion", "status": "failed", "created_timestamp": now},
                ],
            )
        with engine.connect() as connection:
            before = connection.execute(sa.select(job)).all()

        usage = read_serving_usage(url.render_as_string(hide_password=False)).for_flow(str(flow_id))

        assert (usage.runs, usage.errors) == (3, 1)
        assert usage.last_run_at == "2026-10-01T12:00:00.100000Z"
        assert usage.coverage.oldest_retained_at == "2026-10-01T12:00:00Z"
        assert usage.coverage.newest_retained_at == "2026-10-03T12:00:00Z"
        assert usage.source_identity.kind == "postgresql"
        assert schema not in usage.model_dump_json()
        with read_only_connection(url.render_as_string(hide_password=False)) as connection:
            assert connection.exec_driver_sql("SHOW transaction_read_only").scalar() == "on"
            with pytest.raises(sa.exc.DBAPIError):
                connection.execute(job.delete())
        with engine.connect() as connection:
            assert connection.execute(sa.select(job)).all() == before
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True, if_exists=True))
        admin.dispose()

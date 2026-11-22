"""Report metadata preserves the source instant on both supported SQL dialects."""

import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.api.v1.upgrade_reports import entry
from langflow.services.database.models.upgrade_report import UpgradeReport, UpgradeReportRepair
from langflow.services.upgrade_reports.history import list_reports, store_report
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
@pytest.mark.parametrize(
    ("source_time", "expected_utc"),
    [
        ("2026-11-04T12:00:00-08:00", "2026-11-04T20:00:00+00:00"),
        ("2026-11-04T12:00:00+05:30", "2026-11-04T06:30:00+00:00"),
    ],
)
async def test_report_timestamp_round_trip_preserves_instant(dialect, source_time, expected_utc, tmp_path):
    url = (
        f"sqlite+aiosqlite:///{tmp_path / 'clock.db'}"
        if dialect == "sqlite"
        else os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
    )
    if not url:
        pytest.skip("LANGFLOW_TEST_POSTGRES_URL is not set")
    engine = create_async_engine(url)
    schema = f"report_clock_{uuid4().hex}"
    tables = [UpgradeReport.__table__, UpgradeReportRepair.__table__]
    document = json.loads((Path(__file__).parent / "fixtures/upgrade-report-v1.json").read_text())
    document["generated_at"] = source_time
    original = (json.dumps(document, indent=2) + "\n\n").encode()
    try:
        async with engine.connect() as connection:
            if dialect == "postgresql":
                await connection.execute(sa.schema.CreateSchema(schema))
                await connection.exec_driver_sql(f'SET search_path TO "{schema}"')
                await connection.commit()
            await connection.run_sync(lambda sync: SQLModel.metadata.create_all(sync, tables=tables))
            await connection.commit()
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                imported = await store_report(session, original, uuid4())
                report_id = imported.id
                session.expunge_all()
                reloaded = await session.get(UpgradeReport, report_id)
                history, total = await list_reports(session, offset=0, limit=10)
                assert total == 1
                for metadata in (entry(reloaded), entry(history[0])):
                    assert metadata.generated_at == datetime.fromisoformat(expected_utc)
                assert reloaded.document_json.encode() == original
                assert json.loads(reloaded.document_json)["generated_at"] == source_time
    finally:
        if dialect == "postgresql":
            async with engine.begin() as connection:
                await connection.execute(sa.schema.DropSchema(schema, cascade=True))
        await engine.dispose()

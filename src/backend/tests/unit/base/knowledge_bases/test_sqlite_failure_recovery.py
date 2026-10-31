"""Native process-death and SQLITE_FULL qualification on disposable databases.

The size failure uses SQLite's connection page quota, never the host disk.
Subprocesses are exact children created by these tests and killed after explicit
checkpoints. No service, model provider or existing user data is involved.
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import contextmanager
from dataclasses import asdict
from uuid import uuid4

import apsw
import pytest
from lfx.base.knowledge_bases.backends.base import IngestedDocument
from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext
from lfx.base.knowledge_bases.migration import ExportHeader, import_qualified_export, qualify_export, write_export

pytestmark = pytest.mark.no_blockbuster

_CHILD = """
import asyncio, json, sys, time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID
from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext
from lfx.base.knowledge_bases.migration import ExportHeader, qualify_export, import_qualified_export

config = json.loads(Path(sys.argv[1]).read_text())
marker = Path(config['marker'])
class PausedBackend(SQLiteBackend):
    @contextmanager
    def _connect(self, **kwargs):
        with super()._connect(**kwargs) as connection:
            document_write = False
            def before_statement(_cursor, statement, _bindings):
                nonlocal document_write
                if statement.startswith('INSERT INTO chunks'):
                    document_write = True
                if document_write and statement == 'COMMIT' and config['phase'] == 'open_transaction':
                    marker.write_text('uncommitted rows')
                    while True:
                        time.sleep(1)
                return True
            connection.set_exec_trace(before_statement)
            yield connection
    async def add_embedded_documents(self, documents):
        await super().add_embedded_documents(documents)
        if config['phase'] == 'committed_batch':
            marker.write_text('committed batch')
            await asyncio.Event().wait()
async def main():
    context = SQLiteStorageContext(Path(config['root']), UUID(config['owner']), UUID(config['kb']), generation=2)
    backend = PausedBackend('crash-test', storage_context=context, create=True)
    header = ExportHeader(**config['header'])
    with open(config['export'], 'rb') as stream, qualify_export(stream, expected_header=header) as source:
        await import_qualified_export(source, backend, migration_id=UUID(config['migration']), batch_size=2)
asyncio.run(main())
"""


def _source(tmp_path, *, large_last=False):
    documents = [
        IngestedDocument(
            id=f"native-{index}",
            content="x" * 128_000 if large_last and index == 3 else f"document {index}",
            embedding=[float(index), 1.0],
            metadata={"ordinal": index, "source_metadata": {"group": "retained"}},
        )
        for index in range(4)
    ]
    header = ExportHeader(
        source_id="synthetic-recovery",
        source_fingerprint="a" * 64,
        source_version="1.5.9",
        count=len(documents),
        dimensions=2,
        metric="l2",
        model_fingerprint=None,
    )
    export = tmp_path / "export.jsonl"
    with export.open("wb") as stream:
        write_export(stream, header, documents)
    return header, documents, export


async def _records(backend):
    return [record async for batch in backend.iter_documents(include_embeddings=True) for record in batch]


@pytest.mark.parametrize(("phase", "committed_rows"), [("committed_batch", 2), ("open_transaction", 0)])
async def test_killed_native_writer_reopens_and_completes_identical_migration(tmp_path, phase, committed_rows):
    header, documents, export = _source(tmp_path)
    context = SQLiteStorageContext(tmp_path / "vectors", uuid4(), uuid4(), generation=2)
    migration_id = uuid4()
    marker = tmp_path / "checkpoint"
    config = {
        "root": str(context.root),
        "owner": str(context.owner_id),
        "kb": str(context.kb_id),
        "migration": str(migration_id),
        "marker": str(marker),
        "phase": phase,
        "export": str(export),
        "header": asdict(header),
    }
    config_path = tmp_path / "child.json"
    config_path.write_text(json.dumps(config))
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", _CHILD, str(config_path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        deadline = asyncio.get_running_loop().time() + 20
        while not marker.exists():
            if process.returncode is not None:
                _, stderr = await process.communicate()
                pytest.fail(f"Synthetic writer exited before checkpoint: {stderr.decode()}")
            if asyncio.get_running_loop().time() >= deadline:
                pytest.fail("Synthetic writer did not reach its transaction checkpoint")
            await asyncio.sleep(0.025)
        process.kill()
        await process.wait()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    reopened = SQLiteBackend("crash-test", storage_context=context, create=False)
    assert await reopened.count() == committed_rows
    assert (await reopened.read_migration_manifest())["status"] == "importing"
    await reopened.integrity_check()
    with export.open("rb") as stream, qualify_export(stream, expected_header=header) as source:
        receipt = await import_qualified_export(source, reopened, migration_id=migration_id, batch_size=2)
    assert receipt.count == len(documents)
    assert await _records(reopened) == documents
    assert (await reopened.read_migration_manifest())["status"] == "complete"
    await reopened.integrity_check()
    await reopened.teardown()


class PageQuotaBackend(SQLiteBackend):
    """Allow the first batch, then make native SQLite unable to grow its file."""

    quota = None
    batches = 0

    @contextmanager
    def _connect(self, **kwargs):
        with super()._connect(**kwargs) as connection:
            if self.quota is not None:
                connection.execute(f"PRAGMA max_page_count={int(self.quota)}")
            yield connection

    async def add_embedded_documents(self, documents):
        await super().add_embedded_documents(documents)
        self.batches += 1
        if self.batches == 1:
            with super()._connect() as connection:
                self.quota = connection.execute("PRAGMA page_count").fetchone()[0]


async def test_actual_sqlite_full_preserves_committed_batch_and_resumes(tmp_path):
    header, documents, export = _source(tmp_path, large_last=True)
    context = SQLiteStorageContext(tmp_path / "vectors", uuid4(), uuid4(), generation=2)
    backend = PageQuotaBackend("quota-test", storage_context=context, create=True)
    migration_id = uuid4()
    with export.open("rb") as stream, qualify_export(stream, expected_header=header) as source:
        with pytest.raises(apsw.FullError, match="database or disk is full"):
            await import_qualified_export(source, backend, migration_id=migration_id, batch_size=2)
        assert await _records(backend) == documents[:2]
        assert (await backend.read_migration_manifest())["status"] == "importing"
        await backend.integrity_check()
        # Releasing this connection limit simulates restored capacity. No disk
        # filling, file truncation, or synthetic exception is used.
        backend.quota = None
        receipt = await import_qualified_export(source, backend, migration_id=migration_id, batch_size=2)
    assert receipt.count == len(documents)
    assert await _records(backend) == documents
    assert (await backend.read_migration_manifest())["status"] == "complete"
    await backend.integrity_check()
    await backend.teardown()

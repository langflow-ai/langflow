"""Seed the migration rehearsal fixture into a scratch SQLite instance and read its stores back."""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet
from lfx.base.knowledge_bases.backends import SQLiteBackend, SQLiteStorageContext

SCRIPT = Path(__file__).resolve().parents[5] / "scripts" / "migration_rehearsal" / "seed_instance.py"


async def _read_back(root: Path, name: str, entry: dict) -> tuple[int, int]:
    context = SQLiteStorageContext(root, UUID(entry["owner_id"]), UUID(entry["kb_id"]), entry["generation"])
    assert str(context.database_path) == entry["path"]
    backend = SQLiteBackend(name, storage_context=context)
    docs = [doc async for batch in backend.iter_documents(include_embeddings=True) for doc in batch]
    return await backend.count(), sum(doc.embedding is not None for doc in docs)


def test_seed_writes_sqlite_knowledge_bases(tmp_path):
    # A subprocess, because the script configures Langflow's services from the environment.
    manifest_path = tmp_path / "manifest.json"
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--chunks", "3", "--manifest", str(manifest_path)],
        env={
            **os.environ,
            "LANGFLOW_DATABASE_URL": f"sqlite:///{tmp_path / 'src.db'}",
            "LANGFLOW_CONFIG_DIR": str(tmp_path / "cfg"),
            "LANGFLOW_KNOWLEDGE_BASES_DIR": str(tmp_path / "kb"),
            "LANGFLOW_SECRET_KEY": Fernet.generate_key().decode(),
        },
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    manifest = json.loads(manifest_path.read_text())

    with sqlite3.connect(tmp_path / "src.db") as db:
        rows = {
            row[0]: row[1:]
            for row in db.execute(
                "select name, backend_type, storage_generation, storage_state, chunks from knowledge_base"
            )
        }
    assert rows == {
        "kb-ok": ("sqlite", 1, "ready", 3),
        "kb-no-model": ("sqlite", 1, "ready", 5),
        "kb-stubbed-backend": ("astra", 1, "ready", 0),
        "fixture_memory_00000001": ("sqlite", 1, "ready", 2),
    }

    root = Path(manifest["vector_store_root"])
    assert set(manifest["vectors"]) == {name for name, row in rows.items() if row[0] == "sqlite"}
    for name, entry in manifest["vectors"].items():
        assert entry["chunks"] == rows[name][3]
        assert asyncio.run(_read_back(root, name, entry)) == (entry["chunks"], entry["chunks"])

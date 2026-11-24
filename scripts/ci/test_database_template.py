"""The fixture database must preserve WAL data while isolating every test."""

import importlib.util
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("database_template", ROOT / "src/backend/tests/database_template.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DatabaseTemplate = module.DatabaseTemplate


def test_template_includes_wal_and_copies_have_independent_state(tmp_path):
    source = tmp_path / "source.db"
    connection = sqlite3.connect(source)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE seeded (value TEXT)")
        connection.execute("INSERT INTO seeded VALUES ('migration seed')")
        connection.commit()
        template = DatabaseTemplate(tmp_path / "template.db")
        template.capture(source)
        for index in range(2):
            destination = tmp_path / f"test-{index}.db"
            assert template.restore(destination)
            with sqlite3.connect(destination) as copy:
                assert copy.execute("SELECT value FROM seeded").fetchall() == [("migration seed",)]
                copy.execute("DELETE FROM seeded")
            copy.close()
        assert connection.execute("SELECT count(*) FROM seeded").fetchone() == (1,)
    finally:
        connection.close()


def test_missing_template_requires_real_initialization(tmp_path):
    template = DatabaseTemplate(tmp_path / "template.db")
    target = tmp_path / "new.db"
    assert template.restore(target) is False
    assert not target.exists()

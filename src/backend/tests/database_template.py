"""Copy a migrated, unseeded SQLite database without sharing mutable test state."""

import sqlite3
from contextlib import closing
from pathlib import Path


class DatabaseTemplate:
    def __init__(self, path: Path):
        self.path = path

    def restore(self, destination: Path) -> bool:
        if not self.path.exists():
            return False
        self._copy(self.path, destination)
        return True

    def capture(self, source: Path) -> None:
        # SQLite backup includes committed WAL pages. Copying just the .db file
        # can silently lose the migrations that this template is meant to retain.
        temporary = self.path.with_suffix(".tmp")
        try:
            self._copy(source, temporary)
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _copy(source: Path, destination: Path) -> None:
        with (
            closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as reader,
            closing(sqlite3.connect(destination)) as writer,
        ):
            reader.backup(writer)

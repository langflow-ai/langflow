"""Qualify the pinned private SQLite runtime without importing the application.

Run in a clean environment with the native wheels installed using --only-binary.
This is runtime qualification, not a security scan or an upgrade rehearsal.
"""

from __future__ import annotations

import json
import math
import platform
import tempfile
from pathlib import Path

import apsw
import sqlite_vec


def open_connection(path: Path) -> apsw.Connection:
    """Load the pinned vector extension and disable further extension loading."""
    connection = apsw.Connection(str(path))
    try:
        connection.enable_load_extension(enable=True)
        try:
            connection.load_extension(sqlite_vec.loadable_path())
        finally:
            connection.enable_load_extension(enable=False)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        connection.set_busy_timeout(1000)
    except BaseException:
        connection.close()
        raise
    return connection


def qualify_runtime() -> dict[str, str]:
    """Verify native versions, distance functions, WAL persistence and database integrity."""
    if apsw.apswversion() != "3.53.4.0" or apsw.sqlitelibversion() != "3.53.4":
        msg = "Unexpected APSW/SQLite version. Qualify a pin change explicitly."
        raise RuntimeError(msg)
    with tempfile.TemporaryDirectory(prefix="lfx-sqlite-runtime-") as directory:
        path = Path(directory) / "vectors.sqlite3"
        connection = open_connection(path)
        try:
            if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
                msg = "WAL mode was not enabled"
                raise RuntimeError(msg)
            version, l2, cosine = connection.execute(
                "SELECT vec_version(), vec_distance_L2('[1,2]', '[4,6]'), vec_distance_cosine('[1,0]', '[0,1]')"
            ).fetchone()
            if version != "v0.1.9" or not math.isclose(l2, 5.0) or not math.isclose(cosine, 1.0):
                msg = "sqlite-vec version or metric mismatch"
                raise RuntimeError(msg)
            try:
                connection.load_extension(sqlite_vec.loadable_path())
            except apsw.ExtensionLoadingError:
                pass
            else:
                msg = "Extension loading was not disabled"
                raise RuntimeError(msg)
            try:
                connection.execute("SELECT vec_distance_L2('[1,2]', '[1]')").fetchone()
            except apsw.SQLError:
                pass
            else:
                msg = "Mismatched vector dimensions were accepted"
                raise RuntimeError(msg)
            connection.execute("CREATE TABLE chunks(id TEXT PRIMARY KEY, vector BLOB NOT NULL)")
            with connection:
                connection.execute("INSERT INTO chunks VALUES (?, vec_f32(?))", ("native-id", "[1,2]"))
            # The reader must see the committed row while the first connection
            # is still alive, exercising the WAL rather than only the main file.
            reader = open_connection(path)
            try:
                if reader.execute("SELECT id, vec_to_json(vector) FROM chunks").fetchone() != (
                    "native-id",
                    "[1.000000,2.000000]",
                ):
                    msg = "Committed WAL data was not readable"
                    raise RuntimeError(msg)
            finally:
                reader.close()
        finally:
            connection.close()
        reopened = open_connection(path)
        try:
            if reopened.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                msg = "SQLite integrity check failed"
                raise RuntimeError(msg)
            if reopened.execute("SELECT count(*) FROM chunks").fetchone() != (1,):
                msg = "Data did not survive database reopen"
                raise RuntimeError(msg)
        finally:
            reopened.close()
    return {
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "apsw": apsw.apswversion(),
        "sqlite": apsw.sqlitelibversion(),
        "sqlite_vec": version,
    }


if __name__ == "__main__":
    print(json.dumps(qualify_runtime(), sort_keys=True))

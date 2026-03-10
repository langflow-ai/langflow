"""Windows-specific cleanup for Knowledge Base deletion.

Handles ChromaDB SQLite file locks that prevent directory deletion on Windows.
On Windows, mandatory file locks block deletion of files held open by any process.
This module provides retry-based deletion with SQLite lock file cleanup.
"""

import contextlib
import gc
import shutil
import time
import uuid
from pathlib import Path

import chromadb
import chromadb.errors
from chromadb.api.shared_system_client import SharedSystemClient
from chromadb.config import Settings
from langchain_chroma import Chroma
from lfx.log import logger

# Windows deletion constants
_MAX_DELETE_RETRIES = 5
_BASE_BACKOFF_SECONDS = 0.5
_HANDLE_RELEASE_WAIT_SECONDS = 0.3


def _close_chroma_client(kb_path: Path) -> None:
    """Close ChromaDB client and clear internal registry for a given path."""
    path_key = str(kb_path)
    try:
        if path_key in SharedSystemClient._identifier_to_system:  # noqa: SLF001
            del SharedSystemClient._identifier_to_system[path_key]  # noqa: SLF001
    except KeyError:
        pass
    gc.collect()
    time.sleep(_HANDLE_RELEASE_WAIT_SECONDS)


def _teardown_collection(kb_path: Path, kb_name: str) -> None:
    """Delete the ChromaDB collection and release all handles."""
    has_data = any((kb_path / marker).exists() for marker in ["chroma", "chroma.sqlite3", "index"])
    if not has_data:
        return

    try:
        path_key = str(kb_path)
        # Clear registry before creating a fresh client
        with contextlib.suppress(KeyError):
            if path_key in SharedSystemClient._identifier_to_system:  # noqa: SLF001
                del SharedSystemClient._identifier_to_system[path_key]  # noqa: SLF001

        client = chromadb.PersistentClient(
            path=path_key,
            settings=Settings(
                is_persistent=True,
                persist_directory=path_key,
                chroma_otel_service_name=str(uuid.uuid4()),
            ),
        )
        chroma = Chroma(client=client, collection_name=kb_name)
        with contextlib.suppress(Exception):
            chroma.delete_collection()
        chroma = None
        client = None
    except (OSError, ValueError, TypeError, chromadb.errors.ChromaError) as e:
        logger.debug("Windows teardown_collection failed for %s: %s", kb_path.name, e)

    _close_chroma_client(kb_path)


def _remove_sqlite_lock_files(kb_path: Path) -> None:
    """Remove SQLite auxiliary files (WAL, SHM, journal) that hold locks."""
    for pattern in ["*.sqlite3-wal", "*.sqlite3-shm", "*.sqlite3-journal"]:
        for lock_file in kb_path.glob(pattern):
            try:
                lock_file.unlink()
            except OSError as e:
                logger.debug("Could not remove lock file %s: %s", lock_file.name, e)


def _truncate_sqlite_files(kb_path: Path) -> None:
    """Truncate SQLite database files to release locks."""
    for sqlite_file in kb_path.glob("*.sqlite3"):
        try:
            with sqlite_file.open("r+b") as f:
                f.truncate(0)
        except OSError as e:
            logger.debug("Could not truncate %s: %s", sqlite_file.name, e)


def force_delete_kb(kb_path: Path, kb_name: str) -> bool:
    """Force delete a knowledge base directory on Windows.

    Uses retry with exponential backoff, SQLite lock file cleanup,
    and rename-as-fallback strategy.

    Args:
        kb_path: Path to the knowledge base directory.
        kb_name: Name of the knowledge base.

    Returns:
        True if deletion succeeded (or path no longer exists), False otherwise.
    """
    if not kb_path.exists():
        return True

    _teardown_collection(kb_path, kb_name)

    for attempt in range(_MAX_DELETE_RETRIES):
        try:
            if attempt > 0:
                wait = _BASE_BACKOFF_SECONDS * (2**attempt)
                time.sleep(wait)

            _remove_sqlite_lock_files(kb_path)
            _truncate_sqlite_files(kb_path)
            gc.collect()

            shutil.rmtree(kb_path, ignore_errors=False)

            if not kb_path.exists():
                logger.info("Successfully deleted knowledge base %s on attempt %d", kb_name, attempt + 1)
                return True

        except OSError as e:
            if attempt < _MAX_DELETE_RETRIES - 1:
                logger.debug("Windows KB deletion attempt %d failed for %s: %s", attempt + 1, kb_name, e)
            else:
                logger.warning(
                    "Windows KB deletion failed for %s after %d attempts: %s", kb_name, _MAX_DELETE_RETRIES, e
                )

    # Last resort: rename for deferred cleanup
    if kb_path.exists():
        try:
            deferred_path = kb_path.with_name(f".deleted_{kb_name}_{int(time.time())}")
            kb_path.rename(deferred_path)
        except OSError as e:
            logger.warning("Failed to rename %s for deferred cleanup: %s", kb_name, e)
        else:
            logger.info("Renamed %s to %s for deferred cleanup", kb_name, deferred_path.name)
            return True

    return False

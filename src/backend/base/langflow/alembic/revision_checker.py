"""Alembic Revision Compatibility Checker.

This module provides utilities to check if the database schema revision is compatible
with the current application version, and to automatically downgrade when necessary
during rollback scenarios.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text

if TYPE_CHECKING:
    from alembic.config import Config
    from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)


class RevisionCompatibilityError(Exception):
    """Raised when database revision is incompatible with application version."""


def get_current_db_revision(connection: Connection) -> str | None:
    """Get the current migration revision from the database.

    Args:
        connection: SQLAlchemy connection

    Returns:
        Current revision ID, or None if alembic_version table doesn't exist
    """
    try:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        return row[0] if row else None
    except Exception as exc: # noqa: BLE001
        logger.debug(f"Could not get current revision: {exc}")
        return None


def get_revision_chain(script: ScriptDirectory, start_rev: str, end_rev: str) -> list[str]:
    """Get the chain of revisions between two points.

    Args:
        script: Alembic ScriptDirectory
        start_rev: Starting revision
        end_rev: Ending revision

    Returns:
        List of revision IDs in the path from start to end.
        Empty list if start and end are the same.
        Returns list with revisions if there's a path.

    Raises:
        ResolutionError: If either revision doesn't exist
    """
    try:
        # iterate_revisions goes from start (current) down to end (target)
        revisions = list(script.iterate_revisions(start_rev, end_rev))
        return [rev.revision for rev in revisions] if revisions else []
    except Exception as exc:
        logger.debug(f"Could not determine revision chain: {exc}")
        return []


def is_revision_ahead(
    script: ScriptDirectory,
    current_revision: str,
    target_revision: str,
) -> bool:
    """Check if current revision is ahead of target revision.

    Args:
        script: Alembic ScriptDirectory
        current_revision: Current database revision
        target_revision: Target revision for this app version

    Returns:
        True if current is ahead of target (database has future migrations)
    """
    if current_revision == target_revision:
        return False

    try:
        # If we can iterate from current down to target, current is ahead
        chain = get_revision_chain(script, current_revision, target_revision)
        # Non-empty chain means current is ahead
        return len(chain) > 0
    except Exception as exc:
        logger.warning(f"Could not determine if revision is ahead: {exc}")
        # Be conservative - assume not ahead to avoid unnecessary downgrades
        return False


def check_and_downgrade_if_needed(
    alembic_cfg: Config,
    current_version: str,
    target_revision: str | None,
    *,
    fail_on_error: bool = False,
) -> tuple[bool, str]:
    """Check database revision compatibility and downgrade if needed.

    Args:
        alembic_cfg: Alembic configuration
        current_version: Current application version
        target_revision: Target revision for this version, or None
        fail_on_error: If True, raise error on downgrade failure. If False, log warning and continue.

    Returns:
        Tuple of (was_downgraded, message)

    Raises:
        RevisionCompatibilityError: If downgrade is needed but fails and fail_on_error is True
    """
    if not target_revision:
        logger.info(
            f"No target revision mapped for version {current_version}. "
            "Skipping compatibility check. Database may be ahead of source code, "
            "which is acceptable during rollback scenarios. "
            "See langflow/alembic/version_mapping.py to add version mapping."
        )
        return False, "No version mapping configured"

    script = ScriptDirectory.from_config(alembic_cfg)

    # Get database connection from config
    # The connection should be set by the caller
    from sqlalchemy import create_engine

    url = alembic_cfg.get_main_option("sqlalchemy.url")
    if not url:
        msg = "No database URL in alembic config"
        raise RevisionCompatibilityError(msg)

    # Create a temporary sync engine for revision checking
    # We need sync here because alembic commands expect it
    sync_url = url.replace("+aiosqlite", "").replace("+psycopg", "")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            current_db_revision = get_current_db_revision(conn)

            if not current_db_revision:
                return False, "No database revision found (fresh database)"

            if current_db_revision == target_revision:
                return False, f"Database already at target revision {target_revision}"

            # Check if database is ahead
            if is_revision_ahead(script, current_db_revision, target_revision):
                # First check if the target revision exists in the current codebase
                if not validate_revision_exists(script, target_revision):
                    error_msg = (
                        f"Target revision {target_revision} does not exist in current codebase. "
                        f"Database revision {current_db_revision} is ahead of available migrations. "
                        "This typically occurs when downgrading Langflow code but the database "
                        "still contains newer schema changes. "
                    )
                    if fail_on_error:
                        logger.exception(error_msg + "Startup will fail.")
                        raise RevisionCompatibilityError(error_msg)
                    # Log warning but allow startup to continue
                    logger.warning(
                        error_msg + "Continuing startup with newer database schema. "
                        "This may cause compatibility issues. "
                        "Consider rolling forward to the matching application version "
                        "or manually downgrading the database."
                    )
                    return (
                        False,
                        f"Target revision {target_revision} not found in current codebase, continuing anyway",
                    )

                logger.warning(
                    f"Database revision {current_db_revision} is ahead of "
                    f"target {target_revision} for version {current_version}. "
                    "This is typical during rollback from version N to N-1. "
                    "Attempting to downgrade database to maintain compatibility..."
                )

                try:
                    # Perform the downgrade
                    command.downgrade(alembic_cfg, target_revision)
                    logger.info(f"Successfully downgraded to revision {target_revision}")
                    return True, f"Downgraded from {current_db_revision} to {target_revision}"

                except Exception as exc:
                    error_msg = (
                        f"Failed to downgrade database from {current_db_revision} to {target_revision}: {exc}. "
                        "Database schema is ahead of application code. "
                    )
                    if fail_on_error:
                        logger.exception(error_msg + "Startup will fail.")
                        raise RevisionCompatibilityError(error_msg) from exc
                    # Log warning but allow startup to continue
                    logger.warning(
                        error_msg + "Continuing startup with newer database schema. "
                        "This may cause compatibility issues. "
                        "Consider rolling forward to the matching application version "
                        "or manually downgrading the database."
                    )
                    return (
                        False,
                        f"Could not downgrade from {current_db_revision} to {target_revision}, continuing anyway",
                    )

            # Database is behind target - normal upgrade scenario
            return False, f"Database at {current_db_revision}, target is {target_revision} (will upgrade)"

    finally:
        engine.dispose()


def validate_revision_exists(script: ScriptDirectory, revision: str) -> bool:
    """Validate that a revision exists in the migration history.

    Args:
        script: Alembic ScriptDirectory
        revision: Revision ID to check

    Returns:
        True if revision exists, False otherwise
    """
    try:
        script.get_revision(revision)
        return True
    except Exception:
        return False

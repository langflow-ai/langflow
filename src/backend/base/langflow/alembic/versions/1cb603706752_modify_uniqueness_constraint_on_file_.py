"""Modify uniqueness constraint on file names

Revision ID: 1cb603706752
Revises: 3162e83e485f
Create Date: 2025-07-24 07:02:14.896583
"""

from __future__ import annotations

import logging
import re
import time
from typing import Sequence, Union, Iterable, Optional, Set, Tuple

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "1cb603706752"
down_revision: Union[str, None] = "3162e83e485f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)

# Behavior constants
DUPLICATE_SUFFIX_START = 2  # first suffix to use, e.g., "name_2.ext"
BATCH_SIZE = 1000  # Process duplicates in batches for large datasets


def _get_unique_constraints_by_columns(
    inspector, table: str, expected_cols: Iterable[str]
) -> Optional[str]:
    """Return the name of a unique constraint that matches the exact set of expected columns."""
    expected = {col.lower() for col in expected_cols}  # Make case-insensitive
    
    try:
        constraints = inspector.get_unique_constraints(table)
    except Exception as e:
        logger.warning("Failed to get unique constraints for table %s: %s", table, e)
        return None
    
    for c in constraints:
        cols = {col.lower() for col in (c.get("column_names") or [])}  # Case-insensitive
        if cols == expected:
            logger.debug("Found matching constraint: %s for columns %s", c.get("name"), expected_cols)
            return c.get("name")
    
    logger.debug("No constraint found for columns %s. Available constraints: %s", 
                expected_cols, [c.get("name") for c in constraints])
    return None



def _split_base_ext(name: str) -> Tuple[str, str]:
    """Split a filename into (base, ext) where ext does not include the leading dot; ext may be ''."""
    if "." in name:
        base, ext = name.rsplit(".", 1)
        return base, ext
    return name, ""


def _escape_like(s: str) -> str:
    # escape backslash first, then SQL LIKE wildcards
    return s.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def _like_for_suffixes(base: str, ext: str) -> str:
    eb = _escape_like(base)
    if ext:
        ex = ext.replace("%", r"\%").replace("_", r"\_")
        return f"{eb}\\_%." + ex  # literal underscore
    else:
        return f"{eb}\\_%"


def _next_available_name(conn, user_id: str, base_name: str) -> str:
    """
    Compute the next available non-conflicting name for a given user.
    Handles names with or without extensions and existing _N suffixes.
    """
    base, ext = _split_base_ext(base_name)

    # Load all sibling names once
    rows = conn.execute(
        sa.text("""
            SELECT name
            FROM file
            WHERE user_id = :uid
            AND (name = :base_name OR name LIKE :like ESCAPE '\\')
        """),
        {"uid": user_id, "base_name": base_name, "like": _like_for_suffixes(base, ext)},
    ).scalars().all()

    taken: Set[str] = set(rows)

    # Pattern to detect base_N(.ext) and capture N
    if ext:
        rx = re.compile(rf"^{re.escape(base)}_(\d+)\.{re.escape(ext)}$")
    else:
        rx = re.compile(rf"^{re.escape(base)}_(\d+)$")

    max_n = 1
    for n in rows:
        m = rx.match(n)
        if m:
            max_n = max(max_n, int(m.group(1)))

    n = max(max_n + 1, DUPLICATE_SUFFIX_START)
    while True:
        candidate = f"{base}_{n}.{ext}" if ext else f"{base}_{n}"
        if candidate not in taken:
            return candidate
        n += 1


def _handle_duplicates_before_upgrade(conn) -> None:
    """
    Ensure (user_id, name) is unique by renaming older duplicates before adding the composite unique constraint.
    Keeps the most recently updated/created/id-highest record; renames the rest with _N suffix.
    """
    logger.info("Scanning for duplicate file names per user...")
    duplicates = conn.execute(
        sa.text(
            """
            SELECT user_id, name, COUNT(*) AS cnt
            FROM file
            GROUP BY user_id, name
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    if not duplicates:
        logger.info("No duplicates found.")
        return

    logger.info("Found %d duplicate sets. Resolving...", len(duplicates))
    
    # Add progress indicator for large datasets
    if len(duplicates) > 100:
        logger.info("Large number of duplicates detected. This may take several minutes...")

    # Wrap in a nested transaction so we fail cleanly on any error
    with conn.begin_nested():
        # Process duplicates in batches for better performance on large datasets
        for batch_start in range(0, len(duplicates), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(duplicates))
            batch = duplicates[batch_start:batch_end]
            
            if len(duplicates) > BATCH_SIZE:
                logger.info("Processing batch %d-%d of %d duplicate sets...", 
                           batch_start + 1, batch_end, len(duplicates))
            
            for user_id, name, cnt in batch:
                logger.debug("Resolving duplicates for user=%s, name=%r (count=%s)", user_id, name, cnt)

                file_ids = conn.execute(
                    sa.text(
                        """
                        SELECT id
                        FROM file
                        WHERE user_id = :uid AND name = :name
                        ORDER BY updated_at DESC, created_at DESC, id DESC
                        """
                    ),
                    {"uid": user_id, "name": name},
                ).scalars().all()

                # Keep the first (most recent), rename the rest
                for file_id in file_ids[1:]:
                    new_name = _next_available_name(conn, user_id, name)
                    conn.execute(
                        sa.text("UPDATE file SET name = :new_name WHERE id = :fid"),
                        {"new_name": new_name, "fid": file_id},
                    )
                    logger.debug("Renamed id=%s: %r -> %r", file_id, name, new_name)
            
            # Progress update for large batches
            if len(duplicates) > BATCH_SIZE and batch_end < len(duplicates):
                logger.info("Completed %d of %d duplicate sets (%.1f%%)", 
                           batch_end, len(duplicates), (batch_end / len(duplicates)) * 100)

    logger.info("Duplicate resolution completed.")


# Perform the upgrade
# Perform the upgrade
def upgrade() -> None:
    start_time = time.time()
    logger.info("Starting upgrade: adding composite unique (name, user_id) on file")

    conn = op.get_bind()
    inspector = inspect(conn)

    # 1) Resolve pre-existing duplicates so the new unique can be created
    duplicate_start = time.time()
    _handle_duplicates_before_upgrade(conn)
    duplicate_duration = time.time() - duplicate_start
    
    if duplicate_duration > 1.0:  # Only log if it took more than 1 second
        logger.info("Duplicate resolution completed in %.2f seconds", duplicate_duration)

    # 2) Detect existing constraints
    inspector = inspect(conn)  # refresh inspector
    composite_uc = _get_unique_constraints_by_columns(inspector, "file", {"name", "user_id"})

    # 3) Handle constraint changes based on database type
    constraint_start = time.time()
    
    # Check database type
    db_type = conn.dialect.name
    logger.info("Database type: %s", db_type)
    
    if db_type == 'sqlite':
        # SQLite: Must use batch_alter_table with recreate to drop constraints
        logger.info("Using SQLite table recreation to remove file_name_key constraint")
        with op.batch_alter_table("file", recreate="always") as batch_op:
            # Explicitly drop the old constraint during recreation
            try:
                logger.info("Explicitly dropping file_name_key constraint during table recreation")
                batch_op.drop_constraint("file_name_key", type_="unique")
            except Exception as e:
                logger.info("Could not drop file_name_key constraint (may not exist): %s", e)
            
            # Add the new composite constraint
            if not composite_uc:
                logger.info("Creating composite unique: file_name_user_id_key on (name, user_id)")
                batch_op.create_unique_constraint("file_name_user_id_key", ["name", "user_id"])
            else:
                logger.info("Composite unique already present: %s", composite_uc)
    else:
        # PostgreSQL: Can drop constraints directly
        try:
            logger.info("Dropping known single-column unique constraint: file_name_key")
            op.drop_constraint("file_name_key", "file", type_="unique")
        except Exception as e:
            logger.info("Constraint file_name_key not found or already dropped: %s", e)

        # Add the composite constraint
        if not composite_uc:
            logger.info("Creating composite unique: file_name_user_id_key on (name, user_id)")
            op.create_unique_constraint("file_name_user_id_key", "file", ["name", "user_id"])
        else:
            logger.info("Composite unique already present: %s", composite_uc)
    
    constraint_duration = time.time() - constraint_start
    if constraint_duration > 1.0:  # Only log if it took more than 1 second
        logger.info("Constraint operations completed in %.2f seconds", constraint_duration)

    total_duration = time.time() - start_time
    logger.info("Upgrade completed successfully in %.2f seconds", total_duration)


def downgrade() -> None:
    start_time = time.time()
    logger.info("Starting downgrade: reverting to single-column unique on (name)")

    conn = op.get_bind()
    inspector = inspect(conn)

    # 1) Ensure no cross-user duplicates on name (since we'll enforce global uniqueness on name)
    logger.info("Checking for cross-user duplicate names prior to downgrade...")
    validation_start = time.time()
    
    dup_names = conn.execute(
        sa.text(
            """
            SELECT name, COUNT(*) AS cnt
            FROM file
            GROUP BY name
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    validation_duration = time.time() - validation_start
    if validation_duration > 1.0:  # Only log if it took more than 1 second
        logger.info("Validation completed in %.2f seconds", validation_duration)

    if dup_names:
        examples = [row[0] for row in dup_names[:10]]
        raise RuntimeError(
            "Downgrade aborted: duplicate names exist across users. "
            f"Examples: {examples}{'...' if len(dup_names) > 10 else ''}. "
            "Rename conflicting files before downgrading."
        )

    # 2) Detect constraints
    inspector = inspect(conn)  # refresh
    composite_uc = _get_unique_constraints_by_columns(inspector, "file", {"name", "user_id"})
    single_name_uc = _get_unique_constraints_by_columns(inspector, "file", {"name"})

    # 3) Perform alteration using batch with reflect to preserve other objects
    constraint_start = time.time()
    with op.batch_alter_table("file", recreate="always") as batch_op:
        if composite_uc:
            logger.info("Dropping composite unique: %s", composite_uc)
            batch_op.drop_constraint(composite_uc, type_="unique")
        else:
            logger.info("No composite unique found to drop.")

        if not single_name_uc:
            logger.info("Creating single-column unique: file_name_key on (name)")
            batch_op.create_unique_constraint("file_name_key", ["name"])
        else:
            logger.info("Single-column unique already present: %s", single_name_uc)
    
    constraint_duration = time.time() - constraint_start
    if constraint_duration > 1.0:  # Only log if it took more than 1 second
        logger.info("Constraint operations completed in %.2f seconds", constraint_duration)

    total_duration = time.time() - start_time
    logger.info("Downgrade completed successfully in %.2f seconds", total_duration)

#!/usr/bin/env python3
"""
Migration script to migrate published flows between environments.

Usage:
    python scripts/migrate_published_flows.py \
        --source "postgresql://user:pass@localhost:5432/source_db" \
        --target "postgresql://user:pass@localhost:5432/target_db" \
        --email "jagveer@autonomize.ai"

This script migrates:
- Flow records (creates 2 flows: one in "Starter Project", one in "Marketplace Agent")
- published_flow records
- published_flow_input_sample records
- version_flow_input_sample records
- flow_version records
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Constants
MARKETPLACE_AGENT_FOLDER = "Marketplace Agent"
STARTER_PROJECT_FOLDER = "Starter Project"
DEFAULT_VERSION = "1.0.0"
PUBLISHED_STATUS_ID = 5
UNPUBLISHED_STATUS_ID = 6


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate published flows between environments"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source database connection string (e.g., postgresql://user:pass@host:port/db)",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target database connection string (e.g., postgresql://user:pass@host:port/db)",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email of the migration user in target database (e.g., jagveer@autonomize.ai)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making changes to target database",
    )
    return parser.parse_args()


def derive_name_from_email(email: str) -> str:
    """
    Derive display name from email address.

    Examples:
        jagveer@autonomize.ai -> Jagveer
        rishikant.kumar@autonomize.ai -> Rishikant Kumar
    """
    local_part = email.split("@")[0]
    parts = local_part.split(".")
    return " ".join(part.capitalize() for part in parts)


def connect_to_database(connection_string: str) -> psycopg2.extensions.connection:
    """Connect to a PostgreSQL database."""
    try:
        conn = psycopg2.connect(connection_string)
        logger.info(f"Connected to database: {connection_string.split('@')[-1]}")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


def get_user_by_email(
    conn: psycopg2.extensions.connection, email: str
) -> Optional[dict]:
    """Get user by email/username from the database."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            'SELECT id, username FROM "user" WHERE username = %s',
            (email,),
        )
        result = cur.fetchone()
        return dict(result) if result else None


def get_folder_by_name(
    conn: psycopg2.extensions.connection, folder_name: str, user_id: Optional[str] = None
) -> Optional[dict]:
    """Get folder by name, optionally filtered by user_id."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if user_id:
            cur.execute(
                "SELECT id, name, user_id FROM folder WHERE name = %s AND user_id = %s",
                (folder_name, user_id),
            )
        else:
            # For shared folders like "Marketplace Agent", user_id might be NULL
            cur.execute(
                "SELECT id, name, user_id FROM folder WHERE name = %s",
                (folder_name,),
            )
        result = cur.fetchone()
        return dict(result) if result else None


def validate_target_database(
    conn: psycopg2.extensions.connection, email: str
) -> dict:
    """
    Validate target database has required user and folders.
    Returns dict with user_id, marketplace_folder_id, and starter_project_folder_id.
    """
    # Get user
    user = get_user_by_email(conn, email)
    if not user:
        raise ValueError(f"User with email '{email}' not found in target database")

    user_id = str(user["id"])
    logger.info(f"Found user: {email} (ID: {user_id})")

    # Get Marketplace Agent folder
    marketplace_folder = get_folder_by_name(conn, MARKETPLACE_AGENT_FOLDER)
    if not marketplace_folder:
        raise ValueError(
            f"Folder '{MARKETPLACE_AGENT_FOLDER}' not found in target database"
        )

    marketplace_folder_id = str(marketplace_folder["id"])
    logger.info(
        f"Found folder: {MARKETPLACE_AGENT_FOLDER} (ID: {marketplace_folder_id})"
    )

    # Get Starter Project folder for the user
    starter_folder = get_folder_by_name(conn, STARTER_PROJECT_FOLDER, user_id)
    if not starter_folder:
        raise ValueError(
            f"Folder '{STARTER_PROJECT_FOLDER}' not found for user '{email}' in target database"
        )

    starter_folder_id = str(starter_folder["id"])
    logger.info(
        f"Found folder: {STARTER_PROJECT_FOLDER} (ID: {starter_folder_id})"
    )

    return {
        "user_id": user_id,
        "username": user["username"],
        "marketplace_folder_id": marketplace_folder_id,
        "starter_project_folder_id": starter_folder_id,
    }


def fetch_published_flows(conn: psycopg2.extensions.connection) -> list[dict]:
    """Fetch all published flows from source database."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                id, flow_id, user_id, published_by, status, version,
                description, tags, category, flow_cloned_from, flow_name,
                flow_icon, published_by_username, published_at, unpublished_at,
                created_at, updated_at, flow_icon_updated_at
            FROM published_flow
            ORDER BY created_at
        """)
        results = cur.fetchall()
        return [dict(row) for row in results]


def fetch_flow_by_id(
    conn: psycopg2.extensions.connection, flow_id: str
) -> Optional[dict]:
    """Fetch a flow by its ID."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                id, name, description, icon, icon_bg_color, gradient,
                data, is_component, webhook, endpoint_name, tags, locked,
                mcp_enabled, action_name, action_description, access_type,
                updated_at, user_id, folder_id
            FROM flow
            WHERE id = %s
            """,
            (flow_id,),
        )
        result = cur.fetchone()
        return dict(result) if result else None


def fetch_published_flow_input_samples(
    conn: psycopg2.extensions.connection, published_flow_id: str
) -> list[dict]:
    """Fetch input samples for a published flow, ordered by most recent first."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                id, published_flow_id, storage_account, container_name,
                file_names, sample_text, sample_output, created_at, updated_at
            FROM published_flow_input_sample
            WHERE published_flow_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (published_flow_id,),
        )
        results = cur.fetchall()
        return [dict(row) for row in results]


def insert_flow(
    conn: psycopg2.extensions.connection,
    flow_data: dict,
    new_id: str,
    folder_id: str,
    user_id: str,
    new_name: Optional[str] = None,
) -> str:
    """Insert a new flow into the target database."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO flow (
                id, name, description, icon, icon_bg_color, gradient,
                data, is_component, webhook, endpoint_name, tags, locked,
                mcp_enabled, action_name, action_description, access_type,
                updated_at, user_id, folder_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                new_id,
                new_name or flow_data.get("name"),
                flow_data.get("description"),
                flow_data.get("icon"),
                flow_data.get("icon_bg_color"),
                flow_data.get("gradient"),
                json.dumps(flow_data.get("data")) if flow_data.get("data") else None,
                flow_data.get("is_component", False),
                flow_data.get("webhook", False),
                flow_data.get("endpoint_name"),
                json.dumps(flow_data.get("tags")) if flow_data.get("tags") else None,
                flow_data.get("locked", False),
                flow_data.get("mcp_enabled", False),
                flow_data.get("action_name"),
                flow_data.get("action_description"),
                flow_data.get("access_type", "PRIVATE"),
                datetime.now(timezone.utc) - timedelta(days=1),  # Set 1 day back to not dominate "Top 9 Agents" list
                user_id,
                folder_id,
            ),
        )
        return new_id


def insert_published_flow(
    conn: psycopg2.extensions.connection,
    source_pf: dict,
    flow_id: str,
    flow_cloned_from: str,
    user_id: str,
    username: str,
) -> str:
    """Insert a new published_flow record into the target database."""
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO published_flow (
                id, flow_id, user_id, published_by, status, version,
                description, tags, category, flow_cloned_from, flow_name,
                flow_icon, published_by_username, published_at, unpublished_at,
                created_at, updated_at, flow_icon_updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                new_id,
                flow_id,
                user_id,
                user_id,
                source_pf.get("status", "PUBLISHED"),
                DEFAULT_VERSION,
                source_pf.get("description"),
                json.dumps(source_pf.get("tags")) if source_pf.get("tags") else None,
                source_pf.get("category"),
                flow_cloned_from,
                source_pf.get("flow_name"),
                source_pf.get("flow_icon"),
                username,
                now,
                None,
                now,
                now,
                source_pf.get("flow_icon_updated_at"),
            ),
        )
        return new_id


def insert_published_flow_input_sample(
    conn: psycopg2.extensions.connection,
    source_sample: dict,
    published_flow_id: str,
) -> str:
    """Insert a new published_flow_input_sample record."""
    new_id = str(uuid.uuid4())

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO published_flow_input_sample (
                id, published_flow_id, storage_account, container_name,
                file_names, sample_text, sample_output, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                new_id,
                published_flow_id,
                source_sample.get("storage_account"),
                source_sample.get("container_name"),
                json.dumps(source_sample.get("file_names")) if source_sample.get("file_names") else None,
                json.dumps(source_sample.get("sample_text")) if source_sample.get("sample_text") else None,
                json.dumps(source_sample.get("sample_output")) if source_sample.get("sample_output") else None,
                source_sample.get("created_at") or datetime.now(timezone.utc),
                source_sample.get("updated_at") or datetime.now(timezone.utc),
            ),
        )
        return new_id


def insert_version_flow_input_sample(
    conn: psycopg2.extensions.connection,
    source_sample: Optional[dict],
    flow_version_id: str,
    original_flow_id: str,
) -> Optional[str]:
    """Insert a new version_flow_input_sample record."""
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        if source_sample:
            cur.execute(
                """
                INSERT INTO version_flow_input_sample (
                    id, flow_version_id, original_flow_id, version,
                    storage_account, container_name, file_names,
                    sample_text, sample_output, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    new_id,
                    flow_version_id,
                    original_flow_id,
                    DEFAULT_VERSION,
                    source_sample.get("storage_account"),
                    source_sample.get("container_name"),
                    json.dumps(source_sample.get("file_names")) if source_sample.get("file_names") else None,
                    json.dumps(source_sample.get("sample_text")) if source_sample.get("sample_text") else None,
                    json.dumps(source_sample.get("sample_output")) if source_sample.get("sample_output") else None,
                    source_sample.get("created_at") or now,
                    source_sample.get("updated_at") or now,
                ),
            )
        else:
            # Insert with NULL values if no source sample
            cur.execute(
                """
                INSERT INTO version_flow_input_sample (
                    id, flow_version_id, original_flow_id, version,
                    storage_account, container_name, file_names,
                    sample_text, sample_output, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    new_id,
                    flow_version_id,
                    original_flow_id,
                    DEFAULT_VERSION,
                    None,
                    None,
                    None,
                    None,
                    None,
                    now,
                    now,
                ),
            )
        return new_id


def insert_flow_version(
    conn: psycopg2.extensions.connection,
    original_flow_id: str,
    version_flow_id: str,
    flow_data: dict,
    source_pf: dict,
    sample_id: Optional[str],
    user_id: str,
    email: str,
) -> str:
    """Insert a new flow_version record."""
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Determine status_id based on published_flow status
    status = source_pf.get("status", "PUBLISHED")
    status_id = PUBLISHED_STATUS_ID if status == "PUBLISHED" else UNPUBLISHED_STATUS_ID

    # Derive name from email
    display_name = derive_name_from_email(email)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO flow_version (
                id, original_flow_id, version_flow_id, status_id, version,
                title, description, tags, agent_logo, sample_id,
                submitted_by, submitted_by_name, submitted_by_email, submitted_at,
                reviewed_by, reviewed_by_name, reviewed_by_email, reviewed_at, rejection_reason,
                published_by, published_by_name, published_by_email, published_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                new_id,
                original_flow_id,
                version_flow_id,
                status_id,
                DEFAULT_VERSION,
                flow_data.get("name"),
                flow_data.get("description"),
                json.dumps(source_pf.get("tags")) if source_pf.get("tags") else None,
                source_pf.get("flow_icon"),
                sample_id,
                user_id,
                display_name,
                email,
                now,
                None,  # reviewed_by
                None,  # reviewed_by_name
                None,  # reviewed_by_email
                None,  # reviewed_at
                None,  # rejection_reason
                user_id,
                display_name,
                email,
                now,
                now,
                now,
            ),
        )
        return new_id


def update_flow_version_sample_id(
    conn: psycopg2.extensions.connection,
    flow_version_id: str,
    sample_id: str,
) -> None:
    """Update flow_version record with sample_id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE flow_version
            SET sample_id = %s
            WHERE id = %s
            """,
            (sample_id, flow_version_id),
        )


def migrate_single_published_flow(
    source_conn: psycopg2.extensions.connection,
    target_conn: psycopg2.extensions.connection,
    source_pf: dict,
    target_context: dict,
    dry_run: bool = False,
) -> bool:
    """
    Migrate a single published flow from source to target.
    Returns True if successful, False otherwise.
    """
    try:
        flow_cloned_from_id = source_pf.get("flow_cloned_from")
        if not flow_cloned_from_id:
            logger.warning(
                f"Skipping published_flow {source_pf['id']}: no flow_cloned_from"
            )
            return False

        # Fetch original flow from source
        original_flow = fetch_flow_by_id(source_conn, str(flow_cloned_from_id))
        if not original_flow:
            logger.warning(
                f"Skipping published_flow {source_pf['id']}: "
                f"original flow {flow_cloned_from_id} not found"
            )
            return False

        # Fetch input samples from source
        input_samples = fetch_published_flow_input_samples(
            source_conn, str(source_pf["id"])
        )
        source_sample = input_samples[0] if input_samples else None

        if dry_run:
            logger.info(f"[DRY RUN] Would migrate published_flow {source_pf['id']}")
            logger.info(f"  - Original flow: {original_flow['name']}")
            logger.info(f"  - Status: {source_pf.get('status')}")
            logger.info(f"  - Has input samples: {len(input_samples) > 0}")
            return True

        # Generate new UUIDs for target flows
        flow1_id = str(uuid.uuid4())  # Original flow in Starter Project
        flow2_id = str(uuid.uuid4())  # Published flow in Marketplace Agent

        # Create Flow 1 (Starter Project)
        insert_flow(
            target_conn,
            original_flow,
            flow1_id,
            target_context["starter_project_folder_id"],
            target_context["user_id"],
        )
        logger.info(f"  Created Flow 1 (Starter Project): {flow1_id}")

        # Create Flow 2 (Marketplace Agent) with modified name
        published_flow_name = (
            f"{original_flow['name']}-published-{DEFAULT_VERSION}-{flow1_id[:8]}"
        )
        insert_flow(
            target_conn,
            original_flow,
            flow2_id,
            target_context["marketplace_folder_id"],
            target_context["user_id"],
            new_name=published_flow_name,
        )
        logger.info(f"  Created Flow 2 (Marketplace Agent): {flow2_id}")

        # Create published_flow record
        new_pf_id = insert_published_flow(
            target_conn,
            source_pf,
            flow2_id,  # flow_id = the cloned/published flow in Marketplace Agent
            flow1_id,  # flow_cloned_from = the original flow in Starter Project (source of the clone)
            target_context["user_id"],
            target_context["username"],
        )
        logger.info(f"  Created published_flow: {new_pf_id}")

        # Create published_flow_input_sample (if source has data)
        if source_sample:
            new_sample_id = insert_published_flow_input_sample(
                target_conn,
                source_sample,
                new_pf_id,  # published_flow_id points to the published_flow record
            )
            logger.info(f"  Created published_flow_input_sample: {new_sample_id}")

        # Create flow_version record first (before version_flow_input_sample due to FK)
        # We'll update sample_id after creating version_flow_input_sample
        flow_version_id = insert_flow_version(
            target_conn,
            flow1_id,  # original_flow_id
            flow2_id,  # version_flow_id
            original_flow,
            source_pf,
            None,  # sample_id will be updated later
            target_context["user_id"],
            target_context["username"],
        )
        logger.info(f"  Created flow_version: {flow_version_id}")

        # Create version_flow_input_sample (now that flow_version exists)
        version_sample_id = insert_version_flow_input_sample(
            target_conn,
            source_sample,
            flow_version_id,  # flow_version_id points to the flow_version record
            flow1_id,  # original_flow_id points to Starter Project flow
        )
        logger.info(f"  Created version_flow_input_sample: {version_sample_id}")

        # Update flow_version with sample_id
        update_flow_version_sample_id(target_conn, flow_version_id, version_sample_id)
        logger.info(f"  Updated flow_version sample_id: {version_sample_id}")

        return True

    except Exception as e:
        logger.error(f"Error migrating published_flow {source_pf['id']}: {e}")
        return False


def main():
    """Main entry point for the migration script."""
    args = parse_args()

    logger.info("=" * 60)
    logger.info("Published Flow Migration Script")
    logger.info("=" * 60)
    logger.info(f"Source: {args.source.split('@')[-1]}")
    logger.info(f"Target: {args.target.split('@')[-1]}")
    logger.info(f"Migration User: {args.email}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info("=" * 60)

    source_conn = None
    target_conn = None

    try:
        # Connect to databases
        source_conn = connect_to_database(args.source)
        target_conn = connect_to_database(args.target)

        # Validate target database
        logger.info("\nValidating target database...")
        target_context = validate_target_database(target_conn, args.email)

        # Fetch published flows from source
        logger.info("\nFetching published flows from source...")
        published_flows = fetch_published_flows(source_conn)
        logger.info(f"Found {len(published_flows)} published flows to migrate")

        if not published_flows:
            logger.info("No published flows to migrate. Exiting.")
            return

        # Migrate each published flow
        success_count = 0
        failure_count = 0

        for i, pf in enumerate(published_flows, 1):
            logger.info(f"\n[{i}/{len(published_flows)}] Migrating: {pf.get('flow_name', 'Unknown')} (ID: {pf['id']})")

            try:
                if migrate_single_published_flow(
                    source_conn, target_conn, pf, target_context, args.dry_run
                ):
                    if not args.dry_run:
                        target_conn.commit()
                    success_count += 1
                else:
                    # Rollback on failure (returned False)
                    if not args.dry_run:
                        target_conn.rollback()
                    failure_count += 1
            except Exception as e:
                logger.error(f"Failed to migrate {pf['id']}: {e}")
                if not args.dry_run:
                    target_conn.rollback()
                failure_count += 1

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("Migration Summary")
        logger.info("=" * 60)
        logger.info(f"Total: {len(published_flows)}")
        logger.info(f"Success: {success_count}")
        logger.info(f"Failed: {failure_count}")
        if args.dry_run:
            logger.info("(Dry run - no changes were made)")
        logger.info("=" * 60)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        if source_conn:
            source_conn.close()
        if target_conn:
            target_conn.close()


if __name__ == "__main__":
    main()

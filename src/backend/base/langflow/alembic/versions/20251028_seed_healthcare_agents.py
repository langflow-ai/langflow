"""Seed 112 healthcare agents from agents.tsv

Revision ID: 20251028_seed_healthcare_agents
Revises: 20251027130000
Create Date: 2025-10-28 00:00:00.000000

"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Sequence, Union
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine.reflection import Inspector
from sqlmodel import create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

# revision identifiers, used by Alembic.
revision: str = "20251028_seed_healthcare_agents"
down_revision: Union[str, None] = "20251027130000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Setup logging for migration
logger = logging.getLogger(__name__)

# Configure logging if not already configured
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def upgrade() -> None:
    """Seed healthcare agents from TSV file."""
    logger.info("Starting healthcare agents seeding migration")

    try:
        # Get database connection
        conn = op.get_bind()
        inspector: Inspector = sa.inspect(conn)  # type: ignore
        table_names = inspector.get_table_names()

        # Verify required tables exist
        required_tables = ["user", "flow", "published_flow", "folder"]
        missing_tables = [table for table in required_tables if table not in table_names]

        if missing_tables:
            logger.error(f"Required tables missing: {missing_tables}")
            raise RuntimeError(f"Cannot proceed with seeding - missing tables: {missing_tables}")

        # Run async seeding process within existing event loop
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop is not None:
            # We're already in an async context, use sync version
            _sync_upgrade(conn)
        else:
            # Not in async context, safe to use asyncio.run
            asyncio.run(_async_upgrade())

    except Exception as e:
        logger.error(f"Migration upgrade failed: {e}")
        raise


def downgrade() -> None:
    """Remove seeded healthcare agents."""
    logger.info("Starting healthcare agents seeding rollback")

    try:
        # Get database connection
        conn = op.get_bind()

        # Run sync rollback process
        _sync_downgrade(conn)

    except Exception as e:
        logger.error(f"Migration downgrade failed: {e}")
        raise


async def _async_upgrade():
    """Async implementation of the upgrade process."""
    # Import seeding modules (delayed to avoid import issues during migration)
    import sys
    from pathlib import Path

    # Add the scripts directory to Python path for imports
    scripts_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    try:
        from data_seeding.tsv_parser import TSVParser
        from data_seeding.seeding_service import AgentSeedingService
        from data_seeding.models import AgentData
    except ImportError as e:
        logger.error(f"Failed to import seeding modules: {e}")
        raise RuntimeError(f"Cannot import required seeding modules: {e}")

    # Get database connection and create async session
    conn = op.get_bind()

    # Create async engine from sync connection
    # Note: This approach works within Alembic migration context
    database_url = str(conn.engine.url)
    if database_url.startswith('postgresql://'):
        async_database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    elif database_url.startswith('sqlite://'):
        async_database_url = database_url.replace('sqlite://', 'sqlite+aiosqlite://', 1)
    else:
        # For other databases, try to create async URL
        async_database_url = database_url

    # Create async engine and session
    async_engine = create_async_engine(async_database_url)

    try:
        async with AsyncSession(async_engine) as session:
            # Look up user by username
            user_id = await _get_user_id_by_username(session, "jagveer@autonomize.ai")
            if not user_id:
                logger.error("User 'jagveer@autonomize.ai' not found in database")
                raise RuntimeError("Target user 'jagveer@autonomize.ai' not found")

            logger.info(f"Found user 'jagveer@autonomize.ai' with ID: {user_id}")

            # Safety check: Look for existing seeded agents to prevent duplicate runs
            existing_count = await _count_existing_healthcare_agents(session, user_id)
            if existing_count > 0:
                logger.warning(f"Found {existing_count} existing healthcare agents. Migration may have already run.")
                logger.warning("To re-run migration, first run downgrade to remove existing agents.")
                raise RuntimeError(f"Migration appears to have already run ({existing_count} agents found). "
                                 "Use downgrade first to remove existing agents.")

            # Load agents from TSV file
            agents_data = await _load_agents_from_tsv()
            if not agents_data:
                logger.warning("No agents data loaded from TSV file")
                return

            logger.info(f"Loaded {len(agents_data)} agents from TSV file")

            # Initialize seeding service
            seeding_service = AgentSeedingService(
                session=session,
                user_id=user_id,
                template_name="Simple Agent"
            )

            # Validate agent data before seeding
            validation_errors = []
            for agent in agents_data:
                errors = seeding_service.validate_agent_data(agent)
                if errors:
                    validation_errors.extend([f"{agent.agent_name}: {error}" for error in errors])

            if validation_errors:
                logger.error(f"Agent data validation failed: {len(validation_errors)} errors found")
                for error in validation_errors[:5]:  # Log first 5 errors
                    logger.error(f"Validation error: {error}")
                raise ValueError(f"Agent data validation failed with {len(validation_errors)} errors")

            # Seed agents with comprehensive error handling
            logger.info("Starting agent seeding process...")

            batch_result = await seeding_service.seed_agents_from_data(
                agents_data=agents_data,
                batch_size=10,
                dry_run=False,
                publish_flows=True
            )

            # Log results
            logger.info(f"Seeding completed: {batch_result.successful}/{batch_result.total_processed} successful")
            logger.info(f"Success rate: {batch_result.success_rate:.1%}")
            logger.info(f"Duration: {batch_result.duration_seconds:.1f} seconds")

            if batch_result.failed > 0:
                logger.warning(f"Failed to seed {batch_result.failed} agents")
                # Log first few failures for debugging
                failures = [r for r in batch_result.results if not r.success]
                for failure in failures[:5]:
                    logger.warning(f"Failed agent '{failure.agent_name}': {failure.error_message}")

            # Commit the transaction
            await session.commit()
            logger.info("Successfully committed all seeded agents to database")

    except Exception as e:
        logger.error(f"Error during seeding process: {e}")
        raise
    finally:
        # Clean up async engine
        await async_engine.dispose()


async def _async_downgrade():
    """Async implementation of the downgrade process."""
    # Get database connection and create async session
    conn = op.get_bind()

    # Create async engine from sync connection
    database_url = str(conn.engine.url)
    if database_url.startswith('postgresql://'):
        async_database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    elif database_url.startswith('sqlite://'):
        async_database_url = database_url.replace('sqlite://', 'sqlite+aiosqlite://', 1)
    else:
        async_database_url = database_url

    async_engine = create_async_engine(async_database_url)

    try:
        async with AsyncSession(async_engine) as session:
            # Look up user by username
            user_id = await _get_user_id_by_username(session, "jagveer@autonomize.ai")
            if not user_id:
                logger.warning("User 'jagveer@autonomize.ai' not found - skipping rollback")
                return

            logger.info(f"Rolling back seeded agents for user: {user_id}")

            # Load the original agents data to identify what was seeded
            agents_data = await _load_agents_from_tsv()
            if not agents_data:
                logger.warning("No agents data loaded from TSV - cannot perform targeted rollback")
                return

            # Create list of agent names that were seeded
            agent_names = [agent.agent_name for agent in agents_data]
            original_agent_names = [f"{agent.agent_name} - original" for agent in agents_data]
            all_agent_names = agent_names + original_agent_names

            logger.info(f"Looking for {len(all_agent_names)} agent flows to remove")

            # Delete published flows first (due to foreign key constraints)
            published_flow_ids = []
            for name in agent_names:
                result = await session.execute(
                    text("""
                        SELECT pf.id FROM published_flow pf
                        JOIN flow f ON pf.flow_id = f.id
                        WHERE f.name = :name AND f.user_id = :user_id
                    """),
                    {"name": name, "user_id": str(user_id)}
                )
                for row in result:
                    published_flow_ids.append(row.id)

            if published_flow_ids:
                logger.info(f"Deleting {len(published_flow_ids)} published flows")
                for pf_id in published_flow_ids:
                    await session.execute(
                        text("DELETE FROM published_flow WHERE id = :id"),
                        {"id": str(pf_id)}
                    )

            # Delete the flows
            deleted_flows = 0
            for name in all_agent_names:
                result = await session.execute(
                    text("DELETE FROM flow WHERE name = :name AND user_id = :user_id"),
                    {"name": name, "user_id": str(user_id)}
                )
                deleted_flows += result.rowcount

            logger.info(f"Deleted {deleted_flows} flows and {len(published_flow_ids)} published flows")

            # Commit the rollback
            await session.commit()
            logger.info("Successfully rolled back seeded healthcare agents")

    except Exception as e:
        logger.error(f"Error during rollback process: {e}")
        raise
    finally:
        await async_engine.dispose()


def _sync_upgrade(conn):
    """Synchronous implementation of the upgrade process for use within Alembic context."""
    try:
        # Look up user by username - try jagveer@autonomize.ai first, fallback to langflow
        user_id = None
        username = None

        # Try jagveer@autonomize.ai first
        result = conn.execute(
            text('SELECT id FROM "user" WHERE username = :username LIMIT 1'),
            {"username": "jagveer@autonomize.ai"}
        )
        user_row = result.fetchone()

        if user_row:
            user_id = user_row.id
            username = "jagveer@autonomize.ai"
        else:
            # Fallback to langflow user
            result = conn.execute(
                text('SELECT id FROM "user" WHERE username = :username LIMIT 1'),
                {"username": "langflow"}
            )
            user_row = result.fetchone()

            if user_row:
                user_id = user_row.id
                username = "langflow"

        if not user_id:
            logger.error("Neither 'jagveer@autonomize.ai' nor 'langflow' user found in database")
            raise RuntimeError("Cannot proceed with seeding - no suitable user found")

        logger.info(f"Found user: {username} with ID: {user_id}")

        # Check if agents are already seeded to prevent duplicates
        result = conn.execute(
            text("""
                SELECT COUNT(*) as count FROM flow
                WHERE user_id = :user_id
                AND (name LIKE '%Agent%' OR name LIKE '%- original%')
                AND name NOT LIKE '%(Published)%'
            """),
            {"user_id": str(user_id)}
        )
        existing_count = result.fetchone().count

        if existing_count > 50:  # Rough threshold to detect if already seeded
            logger.warning(f"Found {existing_count} existing agent flows - skipping seeding to prevent duplicates")
            logger.info("Healthcare agents seeding skipped (already exists)")
            return

        # Use existing seeding service for full functionality
        logger.info("Starting healthcare agent seeding using existing seeding service...")
        _run_seeding_with_existing_service(conn, user_id)

    except Exception as e:
        logger.error(f"Error during sync seeding process: {e}")
        raise


def _sync_downgrade(conn):
    """Synchronous implementation of the downgrade process for use within Alembic context."""
    try:
        # Look up user by username
        result = conn.execute(
            text('SELECT id FROM "user" WHERE username = :username LIMIT 1'),
            {"username": "langflow"}
        )
        user_row = result.fetchone()

        if not user_row:
            logger.warning("User 'jagveer@autonomize.ai' not found - skipping rollback")
            return

        user_id = user_row.id
        logger.info(f"Rolling back seeded agents for user: {user_id}")

        # Delete flows that look like our seeded agents
        result = conn.execute(
            text("""
                DELETE FROM flow
                WHERE user_id = :user_id
                AND (name LIKE '%Agent%' OR name LIKE '%- original%')
                AND name NOT LIKE '%(Published)%'
            """),
            {"user_id": str(user_id)}
        )
        deleted_count = result.rowcount

        logger.info(f"Deleted {deleted_count} agent flows during rollback")
        logger.info("Healthcare agents rollback completed")

    except Exception as e:
        logger.error(f"Error during sync rollback process: {e}")
        raise


async def _get_user_id_by_username(session: AsyncSession, username: str) -> UUID | None:
    """Look up user ID by username."""
    try:
        result = await session.execute(
            text('SELECT id FROM "user" WHERE username = :username LIMIT 1'),
            {"username": username}
        )
        row = result.fetchone()
        return UUID(str(row.id)) if row else None
    except Exception as e:
        logger.error(f"Error looking up user '{username}': {e}")
        return None


async def _count_existing_healthcare_agents(session: AsyncSession, user_id: UUID) -> int:
    """Count existing healthcare agents to detect if migration already ran."""
    try:
        # Count flows that match our naming pattern for healthcare agents
        result = await session.execute(
            text("""
                SELECT COUNT(*) as count FROM flow
                WHERE user_id = :user_id
                AND (name LIKE '%Agent%' OR name LIKE '%- original')
                AND (
                    folder_id IN (SELECT id FROM folder WHERE name = 'Starter Project' AND user_id = :user_id)
                    OR folder_id IN (SELECT id FROM folder WHERE name = 'Marketplace Agent' AND user_id IS NULL)
                )
            """),
            {"user_id": str(user_id)}
        )
        row = result.fetchone()
        return row.count if row else 0
    except Exception as e:
        logger.warning(f"Could not check for existing agents: {e}")
        return 0


async def _load_agents_from_tsv() -> list:
    """Load agents data from TSV file."""
    try:
        # Import TSV parser (delayed import)
        import sys
        from pathlib import Path

        # Add scripts directory to path
        scripts_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from data_seeding.tsv_parser import TSVParser

        # TSV file should be in the project root
        project_root = Path(__file__).parent.parent.parent.parent.parent.parent
        tsv_file_path = project_root / "agents.tsv"

        if not tsv_file_path.exists():
            logger.error(f"TSV file not found at: {tsv_file_path}")
            raise FileNotFoundError(f"agents.tsv not found at {tsv_file_path}")

        logger.info(f"Loading agents from: {tsv_file_path}")

        # Parse TSV file
        parser = TSVParser(str(tsv_file_path))

        # Validate file structure first
        validation_errors = parser.validate_file_structure()
        if validation_errors:
            logger.error(f"TSV file validation failed: {validation_errors}")
            raise ValueError(f"Invalid TSV file structure: {validation_errors}")

        # Parse agents
        agents_data = parser.parse_agents()
        logger.info(f"Successfully parsed {len(agents_data)} agents from TSV")

        return agents_data

    except Exception as e:
        logger.error(f"Failed to load agents from TSV: {e}")
        raise


def _run_seeding_with_existing_service(conn, user_id):
    """Run seeding using the existing AgentSeedingService."""
    try:
        # Import existing services (delayed import)
        import sys
        from pathlib import Path

        # Add scripts directory to path - migration file is in src/backend/base/langflow/alembic/versions/
        # So we need to go up 7 levels to get to project root, then into scripts
        project_root = Path(__file__).parent.parent.parent.parent.parent.parent.parent
        scripts_dir = project_root / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        logger.info(f"Project root: {project_root}")
        logger.info(f"Scripts directory: {scripts_dir}")
        logger.info(f"Scripts dir exists: {scripts_dir.exists()}")

        from data_seeding.seeding_service import AgentSeedingService
        from data_seeding.tsv_parser import TSVParser

        # Create async engine from sync connection
        database_url = str(conn.engine.url)
        if database_url.startswith('postgresql://'):
            async_database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        elif database_url.startswith('sqlite://'):
            async_database_url = database_url.replace('sqlite://', 'sqlite+aiosqlite://', 1)
        else:
            async_database_url = database_url

        async_engine = create_async_engine(async_database_url)

        async def do_seeding():
            try:
                async with AsyncSession(async_engine) as session:
                    # Load TSV data
                    tsv_file_path = project_root / "agents.tsv"

                    if not tsv_file_path.exists():
                        logger.error(f"TSV file not found at: {tsv_file_path}")
                        raise FileNotFoundError(f"agents.tsv not found at {tsv_file_path}")

                    logger.info(f"Loading agents from: {tsv_file_path}")
                    parser = TSVParser(str(tsv_file_path))

                    # Validate and parse
                    validation_errors = parser.validate_file_structure()
                    if validation_errors:
                        raise ValueError(f"Invalid TSV file structure: {validation_errors}")

                    agents_data = parser.parse_agents()
                    logger.info(f"Successfully parsed {len(agents_data)} agents from TSV")

                    # Use existing seeding service
                    seeding_service = AgentSeedingService(session, user_id, "Simple Agent")
                    result = await seeding_service.seed_agents_from_data(
                        agents_data,
                        batch_size=10,
                        dry_run=False,
                        publish_flows=True
                    )

                    logger.info(f"Healthcare agents seeding completed! Success: {result.successful}/{result.total_processed} agents")
                    logger.info(f"Success rate: {result.success_rate:.1%}, Duration: {result.duration_seconds:.1f}s")

                    if result.failed > 0:
                        logger.warning(f"{result.failed} agents failed to seed")

            finally:
                await async_engine.dispose()

        # Run the async seeding - we need to handle the event loop context
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop is not None:
            # We're in an event loop, create a task and wait for it
            task = loop.create_task(do_seeding())
            # Since we can't await in a sync function, we need to use loop.run_until_complete
            # But this won't work in an async context, so we'll schedule it
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, do_seeding())
                future.result()  # This will block until completion
        else:
            # Not in event loop, safe to use asyncio.run
            asyncio.run(do_seeding())

    except Exception as e:
        logger.error(f"Failed to run seeding with existing service: {e}")
        raise
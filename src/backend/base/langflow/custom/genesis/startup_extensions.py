"""
Startup Extensions for Genesis Studio Backend

This module extends Langflow's functionality by replacing built-in starter projects
with Genesis Studio's custom projects.
"""

import os
import shutil
from pathlib import Path
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger


async def initialize_genesis_studio_extensions() -> bool:
    """Initialize Genesis Studio startup extensions.

    Returns:
        bool: True if initialization was successful
    """
    try:
        logger.info("🚀 Initializing Genesis Studio startup extensions...")

        # For now, just return True as the main integration is in the middleware
        # Add any specific startup logic here if needed

        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize Genesis startup extensions: {e}")
        return False


async def initialize_complete_genesis_extensions(session: AsyncSession) -> bool:
    """Initialize complete Genesis Studio extensions with database access.

    Args:
        session: Database session for operations

    Returns:
        bool: True if initialization was successful
    """
    try:
        logger.info("🎯 Initializing complete Genesis Studio extensions...")

        # For now, just return True as the main integration is in the middleware
        # Add any database-dependent startup logic here if needed

        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize complete Genesis extensions: {e}")
        return False


def replace_all_starter_projects() -> bool:
    """Replace all Langflow starter projects with Genesis Studio custom projects.

    Returns:
        bool: True if replacement was successful
    """
    try:
        logger.info(
            "🚀 Replacing all Langflow starter projects with Genesis Studio projects"
        )

        # Source directory (our custom examples)
        source_dir = Path(__file__).parent / "config" / "basic_examples"

        # Target directory (Langflow's starter projects)
        try:
            import langflow
            langflow_package_path = Path(langflow.__file__).parent
            target_dir = langflow_package_path / "initial_setup" / "starter_projects"
        except ImportError:
            logger.error("❌ Could not find Langflow package")
            return False

        if not source_dir.exists():
            logger.warning(f"⚠️ Source directory does not exist: {source_dir}")
            return False

        if not target_dir.exists():
            logger.error(f"❌ Target directory does not exist: {target_dir}")
            return False

        # Get all JSON files from source
        json_files = list(source_dir.glob("*.json"))

        if not json_files:
            logger.warning("⚠️ No JSON files found in source directory")
            return False

        logger.info(f"📁 Found {len(json_files)} Genesis starter projects to copy")

        # Copy all files from source to target, overwriting existing files
        success_count = 0
        for json_file in json_files:
            try:
                target_file = target_dir / json_file.name
                shutil.copy2(json_file, target_file)
                logger.debug(f"✅ Copied: {json_file.name}")
                success_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to copy {json_file.name}: {e}")

        if success_count > 0:
            logger.info(f"✅ Successfully replaced {success_count} starter projects")
            return True
        else:
            logger.error("❌ No starter projects were successfully copied")
            return False

    except Exception as e:
        logger.error(f"❌ Critical error during starter projects replacement: {e}")
        return False


__all__ = [
    "initialize_genesis_studio_extensions",
    "initialize_complete_genesis_extensions",
    "replace_all_starter_projects",
]
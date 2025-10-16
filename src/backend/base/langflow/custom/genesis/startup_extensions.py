"""
Startup Extensions for Genesis Studio Backend

This module extends Langflow's functionality by replacing built-in starter projects
with Genesis Studio's custom projects.
"""

import os
import shutil
from pathlib import Path

from loguru import logger

# Guardrails removed - no longer needed


def replace_all_starter_projects() -> bool:
    """Replace all Langflow starter projects with Genesis Studio custom projects."""
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

        logger.info(
            f"📁 Found {len(json_files)} custom starter projects to replace with"
        )

        # STEP 1: Remove ALL existing starter projects (clean slate)
        logger.info("🧹 Removing all existing Langflow starter projects...")
        removed_count = 0
        for existing_file in target_dir.glob("*.json"):
            try:
                existing_file.unlink()
                removed_count += 1
                logger.debug(f"🗑️ Removed: {existing_file.name}")
            except Exception as e:
                logger.error(f"❌ Failed to remove {existing_file.name}: {e}")
                continue

        logger.info(f"✅ Removed {removed_count} existing starter projects")

        # STEP 2: Copy our custom projects (without prefix since they're the only ones now)
        logger.info("📦 Installing Genesis Studio starter projects...")
        copied_files = []
        for json_file in json_files:
            # Use original filename since we're replacing everything
            target_path = target_dir / json_file.name

            try:
                shutil.copy2(json_file, target_path)
                copied_files.append(json_file.name)
                logger.debug(f"✅ Installed: {json_file.name}")
            except Exception as e:
                logger.error(f"❌ Failed to install {json_file.name}: {e}")
                continue

        if copied_files:
            logger.info(
                f"✅ Successfully replaced with {len(copied_files)} Genesis Studio starter projects:"
            )
            for filename in copied_files:
                logger.info(f"  • {filename}")

            logger.info("🎯 Only Genesis Studio projects will appear in Langflow UI")
            return True
        else:
            logger.error("❌ No files were successfully installed")
            return False

    except Exception as e:
        logger.error(f"❌ Error replacing starter projects: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def backup_original_starter_projects() -> bool:
    """Create a backup of original Langflow starter projects before replacing them."""
    try:
        logger.info("💾 Creating backup of original Langflow starter projects...")

        # Target directory (Langflow's starter projects)
        try:
            import langflow

            langflow_package_path = Path(langflow.__file__).parent
            target_dir = langflow_package_path / "initial_setup" / "starter_projects"
            backup_dir = (
                langflow_package_path / "initial_setup" / "starter_projects_backup"
            )
        except ImportError:
            logger.error("❌ Could not find Langflow package")
            return False

        if not target_dir.exists():
            logger.warning(f"⚠️ Target directory does not exist: {target_dir}")
            return True  # Nothing to backup

        # Create backup directory if it doesn't exist
        backup_dir.mkdir(exist_ok=True)

        # Copy all JSON files to backup (only if backup doesn't already exist)
        json_files = list(target_dir.glob("*.json"))
        existing_backup_files = list(backup_dir.glob("*.json"))

        if existing_backup_files:
            logger.info(
                f"ℹ️ Backup already exists with {len(existing_backup_files)} files, skipping backup"
            )
            return True

        if not json_files:
            logger.info("ℹ️ No starter projects found to backup")
            return True

        backed_up_files = []
        for json_file in json_files:
            backup_path = backup_dir / json_file.name
            try:
                shutil.copy2(json_file, backup_path)
                backed_up_files.append(json_file.name)
                logger.debug(f"💾 Backed up: {json_file.name}")
            except Exception as e:
                logger.error(f"❌ Failed to backup {json_file.name}: {e}")
                continue

        if backed_up_files:
            logger.info(
                f"✅ Backed up {len(backed_up_files)} original starter projects"
            )
            return True
        else:
            logger.warning("⚠️ Some files could not be backed up")
            return False

    except Exception as e:
        logger.error(f"❌ Error creating backup: {e}")
        return False


def restore_original_starter_projects() -> bool:
    """Restore original Langflow starter projects from backup."""
    try:
        logger.info("🔄 Restoring original Langflow starter projects from backup...")

        # Target directory (Langflow's starter projects)
        try:
            import langflow

            langflow_package_path = Path(langflow.__file__).parent
            target_dir = langflow_package_path / "initial_setup" / "starter_projects"
            backup_dir = (
                langflow_package_path / "initial_setup" / "starter_projects_backup"
            )
        except ImportError:
            logger.error("❌ Could not find Langflow package")
            return False

        if not backup_dir.exists():
            logger.error(f"❌ Backup directory does not exist: {backup_dir}")
            return False

        # Get backup files
        backup_files = list(backup_dir.glob("*.json"))

        if not backup_files:
            logger.warning("⚠️ No backup files found to restore")
            return False

        logger.info(f"📁 Found {len(backup_files)} backup files to restore")

        # Clear current directory
        for existing_file in target_dir.glob("*.json"):
            try:
                existing_file.unlink()
                logger.debug(f"🗑️ Removed: {existing_file.name}")
            except Exception as e:
                logger.error(f"❌ Failed to remove {existing_file.name}: {e}")
                continue

        # Restore backup files
        restored_files = []
        for backup_file in backup_files:
            target_path = target_dir / backup_file.name
            try:
                shutil.copy2(backup_file, target_path)
                restored_files.append(backup_file.name)
                logger.debug(f"🔄 Restored: {backup_file.name}")
            except Exception as e:
                logger.error(f"❌ Failed to restore {backup_file.name}: {e}")
                continue

        if restored_files:
            logger.info(f"✅ Restored {len(restored_files)} original starter projects")
            return True
        else:
            logger.error("❌ No files were successfully restored")
            return False

    except Exception as e:
        logger.error(f"❌ Error restoring starter projects: {e}")
        return False


def is_custom_starter_projects_enabled() -> bool:
    """Check if custom starter projects replacement is enabled."""
    return os.getenv("GENESIS_ENABLE_CUSTOM_STARTER_PROJECTS", "true").lower() == "true"


def is_genesis_starter_projects_already_installed() -> bool:
    """Check if Genesis Studio starter projects are already installed."""
    try:
        # Get Langflow's starter projects directory
        import langflow

        langflow_package_path = Path(langflow.__file__).parent
        target_dir = langflow_package_path / "initial_setup" / "starter_projects"

        if not target_dir.exists():
            logger.warning(f"Starter projects directory does not exist: {target_dir}")
            return False

        # Check if any of our Genesis Studio project names are present
        genesis_project_names = {
            "Prior Auth Form Extraction Agent.json",
            "Auth Guideline Agent.json",
            "Basic Prompting.json",
            "BenefitCheckAgent.json",
            "Document Q&A.json",
            "Document Retrieval Agent.json",
            "Basic Prompt Chaining.json",
            "Clinical Summarization Agent.json",
            "IE Criteria Simplification.json",
            "Summarization.json",
            "Relation Extraction Agent.json",
            "Clinical Extraction.json",
            "Entity Normalization Agent.json",
            "ICD Code Agent.json",
            "Lab Value Extraction Agent.json",
            "Clinical Entity Extraction.json",
            "Simple Agent.json",
            "Prior Auth Recommendation Agent.json",
            "CPT Code Agent.json",
        }

        existing_files = {f.name for f in target_dir.glob("*.json")}

        # Log current state for debugging
        logger.info(
            f"📁 Found {len(existing_files)} starter projects in Langflow directory"
        )
        genesis_found = genesis_project_names.intersection(existing_files)

        if genesis_found:
            logger.info(
                f"✅ Found {len(genesis_found)} Genesis Studio projects already installed"
            )
            logger.debug(f"Genesis projects found: {sorted(genesis_found)}")

            # Check if we're missing any projects
            missing = genesis_project_names - existing_files
            if missing:
                logger.warning(
                    f"⚠️ Missing {len(missing)} Genesis Studio projects: {sorted(missing)}"
                )
                return False
            return True

        logger.info("❌ No Genesis Studio projects found in Langflow directory")
        logger.debug(f"Existing files: {sorted(existing_files)}")
        return False

    except Exception as e:
        logger.error(f"Could not check for existing Genesis Studio projects: {e}")
        return False


async def initialize_component_mapping_population(session=None) -> bool:
    """Initialize component mapping population on startup."""
    try:
        from langflow.services.component_mapping.startup_population import StartupPopulationService

        logger.info("🚀 Initializing component mapping population...")

        # Create startup population service
        startup_service = StartupPopulationService()

        # Check if population should run
        if not startup_service.should_run_startup_population():
            logger.info("ℹ️ Component mapping population disabled via environment")
            return True

        # Get database session if not provided
        if session is None:
            try:
                from langflow.services.database.utils import session_getter
                from langflow.services.deps import get_db_service

                db_service = get_db_service()
                async with session_getter(db_service) as db_session:
                    result = await startup_service.populate_on_startup(db_session)
            except ImportError:
                logger.warning("⚠️ Could not get database session, skipping population")
                return True
        else:
            result = await startup_service.populate_on_startup(session)

        if result.get("status") == "completed":
            logger.info("✅ Component mapping population completed successfully")
            return True
        elif result.get("status") == "skipped":
            logger.info("ℹ️ Component mapping population skipped (already populated)")
            return True
        else:
            logger.warning(f"⚠️ Component mapping population failed: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to initialize component mapping population: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def initialize_genesis_studio_extensions() -> bool:
    """Initialize Genesis Studio extensions by replacing all starter projects with custom ones."""
    try:
        logger.info("🚀 Initializing Genesis Studio extensions...")

        if not is_custom_starter_projects_enabled():
            logger.info("ℹ️ Custom starter projects disabled via environment variable")
            return True

        # Check environment variable to force replacement
        force_replacement = (
            os.getenv("GENESIS_FORCE_STARTER_PROJECTS_REPLACEMENT", "false").lower()
            == "true"
        )

        # Check if Genesis Studio projects are already installed (e.g., via Docker build)
        already_installed = is_genesis_starter_projects_already_installed()

        if already_installed and not force_replacement:
            logger.info(
                "ℹ️ Genesis Studio starter projects already installed, skipping runtime replacement"
            )
            logger.info(
                "💡 Set GENESIS_FORCE_STARTER_PROJECTS_REPLACEMENT=true to force replacement"
            )
            return True

        if force_replacement:
            logger.info(
                "🔄 Force replacement enabled, replacing starter projects regardless of current state"
            )

        # Create backup of original projects first
        backup_success = backup_original_starter_projects()
        if not backup_success:
            logger.warning("⚠️ Failed to create backup, but continuing with replacement")

        # Replace all starter projects with custom ones
        success = replace_all_starter_projects()

        if success:
            logger.info("✅ Genesis Studio extensions initialized successfully")
            logger.info(
                "🎯 Only Genesis Studio starter projects will be available in Langflow"
            )
        else:
            logger.warning("⚠️ Genesis Studio extensions initialization failed")

        return success

    except Exception as e:
        logger.error(f"❌ Failed to initialize Genesis Studio extensions: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


async def initialize_complete_genesis_extensions(session=None) -> bool:
    """
    Initialize complete Genesis Studio extensions including startup population.

    This is the main entry point for AUTPE-6180 integration.
    """
    try:
        logger.info("🚀 Starting complete Genesis Studio extensions initialization...")

        # Phase 1: Initialize starter projects
        logger.info("📦 Phase 1: Initializing starter projects...")
        starter_success = initialize_genesis_studio_extensions()
        if not starter_success:
            logger.warning("⚠️ Starter projects initialization failed, but continuing...")

        # Phase 2: Initialize component mapping population
        logger.info("🗄️ Phase 2: Initializing component mapping population...")
        population_success = await initialize_component_mapping_population(session)
        if not population_success:
            logger.warning("⚠️ Component mapping population failed, but continuing...")

        # Phase 3: Initialize schema integration
        logger.info("🔧 Phase 3: Initializing schema integration...")
        schema_success = initialize_complete_schema_integration()
        if not schema_success:
            logger.warning("⚠️ Schema integration failed, but continuing...")

        overall_success = starter_success and population_success and schema_success

        if overall_success:
            logger.info("✅ Complete Genesis Studio extensions initialized successfully")
        else:
            logger.warning("⚠️ Some Genesis Studio extensions failed, but core functionality available")

        return overall_success

    except Exception as e:
        logger.error(f"❌ Failed to initialize complete Genesis Studio extensions: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def initialize_complete_schema_integration() -> bool:
    """Initialize complete schema integration for all component types."""
    try:
        from langflow.services.spec.complete_component_schemas import integrate_schemas_with_validation

        logger.info("🔧 Integrating complete component schema coverage...")

        result = integrate_schemas_with_validation()

        if result.get("success"):
            added_count = result.get("added_count", 0)
            total_count = result.get("final_count", 0)
            logger.info(f"✅ Schema integration successful: {added_count} new schemas added, {total_count} total")
            return True
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"❌ Schema integration failed: {error}")
            return False

    except Exception as e:
        logger.error(f"❌ Error in schema integration: {e}")
        return False

#!/usr/bin/env python3
"""Main script for seeding AI Studio agents from TSV data."""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

from .tsv_parser import TSVParser
from .seeding_service import AgentSeedingService
from .validation import AgentDataValidator
from .models import BatchResult, ValidationError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentSeedingCLI:
    """Command-line interface for agent seeding."""

    def __init__(self):
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser."""
        parser = argparse.ArgumentParser(
            description="Seed AI Studio agents from TSV data",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Dry run to validate data
  python -m scripts.data_seeding.main --tsv-file agents.tsv --user-id <uuid> --dry-run

  # Seed agents without publishing
  python -m scripts.data_seeding.main --tsv-file agents.tsv --user-id <uuid> --no-publish

  # Full seeding with custom batch size
  python -m scripts.data_seeding.main --tsv-file agents.tsv --user-id <uuid> --batch-size 5

  # Validate TSV file structure only
  python -m scripts.data_seeding.main --tsv-file agents.tsv --validate-only
            """
        )

        parser.add_argument(
            '--tsv-file',
            type=str,
            required=True,
            help='Path to TSV file containing agent data'
        )

        parser.add_argument(
            '--user-id',
            type=str,
            help='UUID of the user to associate with created flows (required unless --validate-only)'
        )

        parser.add_argument(
            '--database-url',
            type=str,
            default='postgresql+asyncpg://postgres:postgres@localhost:5432/studio-test',
            help='Database connection URL (default: %(default)s)'
        )

        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of agents to process in each batch (default: %(default)s)'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate data and show what would be created without making changes'
        )

        parser.add_argument(
            '--no-publish',
            action='store_true',
            help='Create flows but do not publish them'
        )

        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate TSV file structure and data, do not seed'
        )

        parser.add_argument(
            '--verbose',
            '-v',
            action='store_true',
            help='Enable verbose logging'
        )

        parser.add_argument(
            '--continue-on-error',
            action='store_true',
            help='Continue processing even if some agents fail validation'
        )


        return parser

    async def run(self, args: argparse.Namespace) -> int:
        """Run the seeding process."""
        try:
            # Configure logging level
            if args.verbose:
                logging.getLogger().setLevel(logging.DEBUG)

            # Validate arguments
            if not args.validate_only and not args.user_id:
                logger.error("--user-id is required unless using --validate-only")
                return 1

            # Validate TSV file exists
            tsv_path = Path(args.tsv_file)
            if not tsv_path.exists():
                logger.error(f"TSV file not found: {args.tsv_file}")
                return 1

            # Parse TSV file
            logger.info(f"Parsing TSV file: {args.tsv_file}")
            parser = TSVParser(args.tsv_file)

            # Validate file structure
            structure_errors = parser.validate_file_structure()
            if structure_errors:
                logger.error("TSV file structure validation failed:")
                for error in structure_errors:
                    logger.error(f"  - {error}")
                return 1

            # Parse agents data
            agents_data = parser.parse_agents()
            if not agents_data:
                logger.error("No valid agent data found in TSV file")
                return 1

            logger.info(f"Successfully parsed {len(agents_data)} agents")

            # If validate-only mode, just do basic validation and stop
            if args.validate_only:
                # Do basic field validation without database access
                validator = AgentDataValidator(None, None)
                basic_validation = {}
                for agent in agents_data:
                    errors = []
                    errors.extend(validator._validate_required_fields(agent))
                    errors.extend(validator._validate_field_formats(agent))
                    errors.extend(validator._validate_business_rules(agent))
                    basic_validation[agent.agent_name] = errors

                # Check for duplicates within batch
                batch_validation = validator.validate_batch_uniqueness(agents_data)

                # Merge validation results
                all_validation = {}
                for agent_name in basic_validation:
                    all_validation[agent_name] = basic_validation[agent_name] + batch_validation.get(agent_name, [])

                validation_summary = validator.get_validation_summary(all_validation)
                print(f"\n=== VALIDATION RESULTS ===")
                print(f"Total agents: {validation_summary['total_agents']}")
                print(f"Valid agents: {validation_summary['valid_agents']}")
                print(f"Agents with errors: {validation_summary['agents_with_errors']}")

                if validation_summary['agents_with_errors'] > 0:
                    print("\nValidation errors found:")
                    for agent_name, errors in all_validation.items():
                        if errors:
                            print(f"  {agent_name}:")
                            for error in errors:
                                print(f"    - {error.field}: {error.error}")
                    return 1
                else:
                    logger.info("All agents passed validation")
                    return 0

            # Convert user_id to UUID
            try:
                user_id = UUID(args.user_id)
            except ValueError:
                logger.error(f"Invalid user ID format: {args.user_id}")
                return 1

            # Create database session
            engine = create_async_engine(args.database_url, echo=args.verbose)
            async with AsyncSession(engine) as session:
                # Validate data against database
                validator = AgentDataValidator(session, user_id)
                validation_results = await validator.validate_batch(agents_data)

                # Check for validation errors
                agents_with_errors = [
                    name for name, errors in validation_results.items() if errors
                ]

                if agents_with_errors:
                    logger.warning(f"Found validation errors for {len(agents_with_errors)} agents")

                    # Log specific error types for debugging
                    error_types = {}
                    for name, errors in validation_results.items():
                        for error in errors:
                            error_types[error.error] = error_types.get(error.error, 0) + 1

                    logger.info("Error breakdown:")
                    for error_msg, count in error_types.items():
                        logger.info(f"  - '{error_msg}': {count} agents")

                    if not args.continue_on_error:
                        logger.error("Stopping due to validation errors. Use --continue-on-error to proceed.")
                        self._print_validation_errors(validation_results)
                        return 1
                    else:
                        logger.warning("Continuing with valid agents only")

                # Filter out agents with errors
                valid_agents = [
                    agent for agent in agents_data
                    if agent.agent_name not in agents_with_errors
                ]

                if not valid_agents:
                    logger.error("No valid agents to process after validation")
                    return 1

                logger.info(f"Processing {len(valid_agents)} valid agents")

                # Create seeding service and process agents
                seeding_service = AgentSeedingService(session, user_id)
                result = await seeding_service.seed_agents_from_data(
                    valid_agents,
                    batch_size=args.batch_size,
                    dry_run=args.dry_run,
                    publish_flows=not args.no_publish
                )

                # Commit the transaction to persist changes to database
                if not args.dry_run and result.successful > 0:
                    await session.commit()
                    logger.info(f"Successfully committed {result.successful} agents to database")

                # Print results
                self._print_results(result, args.dry_run)

                # Print validation summary if there were errors
                if agents_with_errors:
                    self._print_validation_summary(validator.get_validation_summary(validation_results))

                return 0 if result.failed == 0 else 1

        except KeyboardInterrupt:
            logger.info("Process interrupted by user")
            return 130
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if args.verbose:
                logger.exception("Full traceback:")
            return 1

    def _print_validation_errors(self, validation_results: dict):
        """Print validation errors in a readable format."""
        print("\n=== VALIDATION ERRORS ===")
        for agent_name, errors in validation_results.items():
            if errors:
                print(f"\nAgent: {agent_name}")
                for error in errors:
                    print(f"  - {error.field}: {error.error}")

    def _print_validation_summary(self, summary: dict):
        """Print validation summary."""
        print("\n=== VALIDATION SUMMARY ===")
        print(f"Total agents: {summary['total_agents']}")
        print(f"Valid agents: {summary['valid_agents']}")
        print(f"Agents with errors: {summary['agents_with_errors']}")
        print(f"Error rate: {summary['error_rate']:.1%}")

        if summary['errors_by_field']:
            print("\nErrors by field:")
            for field, count in sorted(summary['errors_by_field'].items()):
                print(f"  - {field}: {count}")

    def _print_results(self, result: BatchResult, dry_run: bool):
        """Print seeding results."""
        mode = "DRY RUN" if dry_run else "SEEDING"
        print(f"\n=== {mode} RESULTS ===")
        print(f"Total processed: {result.total_processed}")
        print(f"Successful: {result.successful}")
        print(f"Failed: {result.failed}")
        print(f"Success rate: {result.success_rate:.1%}")
        print(f"Duration: {result.duration_seconds:.1f} seconds")

        if result.failed > 0:
            print("\nFailed agents:")
            for r in result.results:
                if not r.success:
                    print(f"  - {r.agent_name}: {r.error_message}")

        if not dry_run and result.successful > 0:
            print(f"\nSuccessfully created {result.successful} flows")


async def main():
    """Main entry point."""
    cli = AgentSeedingCLI()
    args = cli.parser.parse_args()
    return await cli.run(args)


def sync_main():
    """Synchronous wrapper for main."""
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(sync_main())
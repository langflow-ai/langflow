"""Database seeding service for AI Studio agents."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.published_flow.model import PublishedFlow, PublishStatusEnum
from langflow.services.database.models.user.model import User
from langflow.services.database.models.folder.model import Folder
from langflow.graph.graph.base import Graph

from .models import AgentData, SeedingResult, BatchResult
from .templates import FlowTemplateFactory


logger = logging.getLogger(__name__)


class AgentSeedingService:
    """Service for seeding AI Studio agents from TSV data."""

    def __init__(self, session: AsyncSession, user_id: UUID, template_name: str = "Simple Agent"):
        self.session = session
        self.user_id = user_id
        self.template_name = template_name
        self.template_factory = FlowTemplateFactory()
        self._folder_cache: Dict[str, UUID] = {}
        self._template_cache: Optional[dict] = None

    async def seed_agents_from_data(
        self,
        agents_data: List[AgentData],
        batch_size: int = 10,
        dry_run: bool = False,
        publish_flows: bool = True
    ) -> BatchResult:
        """Seed multiple agents with batch processing and transaction management."""
        logger.info(f"Starting to seed {len(agents_data)} agents (dry_run={dry_run})")

        # Ensure required folders exist before processing
        if not dry_run:
            await self._ensure_folders_exist()

        start_time = datetime.now()
        results = []
        successful = 0
        failed = 0

        # Process in batches
        for i in range(0, len(agents_data), batch_size):
            batch = agents_data[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: agents {i+1}-{min(i+batch_size, len(agents_data))}")

            batch_results = await self._process_batch(batch, dry_run, publish_flows)
            results.extend(batch_results)

            # Count successes and failures
            batch_successful = sum(1 for r in batch_results if r.success)
            batch_failed = len(batch_results) - batch_successful
            successful += batch_successful
            failed += batch_failed

            logger.info(f"Batch completed: {batch_successful} successful, {batch_failed} failed")

        end_time = datetime.now()

        batch_result = BatchResult(
            total_processed=len(agents_data),
            successful=successful,
            failed=failed,
            results=results,
            start_time=start_time,
            end_time=end_time
        )

        logger.info(
            f"Seeding completed: {successful}/{len(agents_data)} successful "
            f"({batch_result.success_rate:.1%}) in {batch_result.duration_seconds:.1f}s"
        )

        return batch_result

    async def _process_batch(
        self,
        batch: List[AgentData],
        dry_run: bool,
        publish_flows: bool
    ) -> List[SeedingResult]:
        """Process a batch of agents with savepoint-based error recovery."""
        results = []

        for agent_data in batch:
            # Use savepoint for individual agent processing
            savepoint = await self.session.begin_nested()
            try:
                result = await self._create_agent_flow(agent_data, dry_run, publish_flows)
                if not dry_run:
                    await savepoint.commit()
                results.append(result)
                logger.debug(f"Successfully processed agent: {agent_data.agent_name}")
            except Exception as e:
                await savepoint.rollback()
                error_msg = f"Failed to process agent '{agent_data.agent_name}': {str(e)}"
                logger.warning(error_msg)
                results.append(SeedingResult(
                    agent_name=agent_data.agent_name,
                    success=False,
                    error_message=error_msg
                ))

        return results

    async def _create_agent_flow(
        self,
        agent_data: AgentData,
        dry_run: bool,
        publish_flows: bool
    ) -> SeedingResult:
        """Create a single agent flow and optionally publish it."""
        try:
            # Check if flow already exists
            existing_flow = await self._find_existing_flow(agent_data)
            if existing_flow:
                logger.info(f"Flow already exists for agent: {agent_data.agent_name}")
                return SeedingResult(
                    flow_id=existing_flow.id,
                    agent_name=agent_data.agent_name,
                    success=True,
                    error_message="Flow already exists (skipped)"
                )

            if dry_run:
                logger.info(f"[DRY RUN] Would create flow for: {agent_data.agent_name}")
                return SeedingResult(
                    agent_name=agent_data.agent_name,
                    success=True,
                    error_message="Dry run - not actually created"
                )

            # Load Simple Agent starter project and customize just the system prompt
            flow_data = await self._get_template_from_database(agent_data)

            # If template loading failed, fall back to generated template
            if not flow_data:
                logger.warning(f"Using generated template for {agent_data.agent_name} (database template unavailable)")
                template_result = self.template_factory.create_agent_flow(agent_data)
                flow_data = template_result.get('data', {})
            else:
                logger.debug(f"Using '{self.template_name}' starter project for {agent_data.agent_name}")

            domain_color = self.template_factory.get_domain_color(agent_data.domain_area)

            # Get folder ID for starter projects
            starter_folder_id = await self._get_folder_id("Starter Project")

            # Create flow
            flow = Flow(
                id=uuid4(),
                name=f"{agent_data.agent_name} - original",
                description=agent_data.description,
                data=flow_data,
                user_id=self.user_id,
                folder_id=starter_folder_id,
                endpoint_name=await self._generate_unique_endpoint_name(agent_data.endpoint_name),
                tags=agent_data.tags,
                icon_bg_color=domain_color,
                icon=None,  # No icon by default
                webhook=False,
                is_component=False,
                updated_at=datetime.now()
            )

            self.session.add(flow)
            await self.session.flush()  # Get the flow ID

            result = SeedingResult(
                flow_id=flow.id,
                agent_name=agent_data.agent_name,
                success=True
            )

            # Create published flow if requested
            if publish_flows:
                published_flow = await self._create_published_flow(flow, agent_data)
                result.published_flow_id = published_flow.id

            return result

        except Exception as e:
            logger.error(f"Error creating agent flow for {agent_data.agent_name}: {e}")
            raise

    async def _create_published_flow(self, flow: Flow, agent_data: AgentData) -> PublishedFlow:
        """Create a published flow entry."""
        # Get folder ID for marketplace agents
        marketplace_folder_id = await self._get_folder_id("Marketplace Agent")

        # Create a clone of the flow for publishing - make a deep copy of data
        import copy
        cloned_data = copy.deepcopy(flow.data)

        cloned_flow = Flow(
            id=uuid4(),
            name=agent_data.agent_name,  # Use real agent name for published flow
            description=flow.description,
            data=cloned_data,
            user_id=self.user_id,
            folder_id=marketplace_folder_id,
            endpoint_name=None,  # Published flows don't need endpoints
            tags=flow.tags,
            icon_bg_color=flow.icon_bg_color,
            icon=flow.icon,
            webhook=False,
            is_component=False,
            updated_at=datetime.now()
        )

        self.session.add(cloned_flow)
        await self.session.flush()

        # Create published flow entry
        now = datetime.now()

        # Get username dynamically based on user_id
        username = await self.get_username_by_id(self.user_id)
        if not username:
            logger.warning(f"Could not find username for user {self.user_id}, using 'system' as fallback")
            username = "system"

        published_flow = PublishedFlow(
            id=uuid4(),
            flow_id=cloned_flow.id,
            flow_cloned_from=flow.id,
            user_id=self.user_id,
            published_by=self.user_id,
            status=PublishStatusEnum.UNPUBLISHED,
            version="1.0.0",
            description=agent_data.description,
            tags=agent_data.tags,
            category=agent_data.category,
            published_at=now,
            created_at=now,
            updated_at=now,
            # Denormalized fields
            flow_name=agent_data.agent_name,  # Use real agent name
            flow_icon=flow.icon,
            published_by_username=username  # Dynamic username based on user_id
        )

        self.session.add(published_flow)
        await self.session.flush()

        return published_flow

    async def _find_existing_flow(self, agent_data: AgentData) -> Optional[Flow]:
        """Check if a flow with the same name already exists for this user."""
        # Check for both old naming style and new naming style
        original_name = f"{agent_data.agent_name} - original"
        result = await self.session.execute(
            text("SELECT * FROM flow WHERE (name = :name OR name = :original_name) AND user_id = :user_id LIMIT 1"),
            {"name": agent_data.agent_name, "original_name": original_name, "user_id": str(self.user_id)}
        )
        row = result.fetchone()
        if row:
            return Flow(**dict(row._asdict()))
        return None

    async def _generate_unique_endpoint_name(self, base_name: str) -> str:
        """Generate a unique endpoint name by checking for conflicts."""
        endpoint_name = base_name
        counter = 1

        while await self._endpoint_exists(endpoint_name):
            endpoint_name = f"{base_name}-{counter}"
            counter += 1

        return endpoint_name

    async def _endpoint_exists(self, endpoint_name: str) -> bool:
        """Check if an endpoint name already exists for this user."""
        result = await self.session.execute(
            text("SELECT COUNT(*) as count FROM flow WHERE endpoint_name = :endpoint_name AND user_id = :user_id"),
            {"endpoint_name": endpoint_name, "user_id": str(self.user_id)}
        )
        row = result.fetchone()
        return row.count > 0 if row else False

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID for validation."""
        result = await self.session.execute(
            text("SELECT * FROM user WHERE id = :user_id LIMIT 1"),
            {"user_id": str(user_id)}
        )
        row = result.fetchone()
        if row:
            return User(**dict(row._asdict()))
        return None

    def validate_agent_data(self, agent_data: AgentData) -> List[str]:
        """Validate agent data before processing."""
        errors = []

        if not agent_data.agent_name or len(agent_data.agent_name.strip()) == 0:
            errors.append("Agent name is required")

        if not agent_data.description or len(agent_data.description.strip()) == 0:
            errors.append("Agent description is required")

        if not agent_data.domain_area:
            errors.append("Domain area is required")

        # Check endpoint name validity
        endpoint_name = agent_data.endpoint_name
        if endpoint_name and not endpoint_name.replace("-", "").replace("_", "").isalnum():
            errors.append(f"Invalid endpoint name: {endpoint_name}")

        return errors

    async def _get_folder_id(self, folder_name: str) -> Optional[UUID]:
        """Get folder ID by name, with special handling for global folders."""
        if folder_name in self._folder_cache:
            return self._folder_cache[folder_name]

        # For Marketplace Agent, check for global folder first (user_id = NULL)
        if folder_name == "Marketplace Agent":
            result = await self.session.execute(
                text("SELECT id FROM folder WHERE name = :name AND user_id IS NULL LIMIT 1"),
                {"name": folder_name}
            )
            row = result.fetchone()
            if row:
                folder_id = UUID(str(row.id))
                self._folder_cache[folder_name] = folder_id
                logger.info(f"Using existing global folder '{folder_name}' with ID {folder_id}")
                return folder_id

        # For user-specific folders (like Starter Project), check user-scoped
        result = await self.session.execute(
            text("SELECT id FROM folder WHERE name = :name AND user_id = :user_id LIMIT 1"),
            {"name": folder_name, "user_id": str(self.user_id)}
        )
        row = result.fetchone()

        folder_id = UUID(str(row.id)) if row else None
        self._folder_cache[folder_name] = folder_id

        if not folder_id:
            logger.warning(f"Folder '{folder_name}' not found for user {self.user_id}")

        return folder_id

    async def _get_template_from_database(self, agent_data: AgentData = None) -> dict:
        """Load and customize a flow template from database using Graph processing pipeline."""
        # Always load fresh template for customization if agent_data is provided
        if agent_data is None and self._template_cache is not None:
            return self._template_cache

        try:
            # Get flow template from database by name
            result = await self.session.execute(
                text("SELECT data FROM flow WHERE name = :name AND user_id IS NULL LIMIT 1"),
                {"name": self.template_name}
            )
            row = result.fetchone()

            if not row:
                logger.error(f"Template '{self.template_name}' not found in database")
                return {}

            # Extract the flow data
            raw_flow_data = dict(row.data) if row.data else {}

            if not raw_flow_data:
                logger.error(f"Template '{self.template_name}' has empty data")
                return {}

            # Don't process through Graph pipeline - just use the raw template data
            # The Simple Agent template already works correctly
            processed_flow_data = raw_flow_data
            logger.info(f"Using raw '{self.template_name}' template without Graph processing")

            # Customize template with agent-specific data if provided
            if agent_data:
                processed_flow_data = self._customize_template_with_agent_data(processed_flow_data, agent_data)
                logger.info(f"Customized '{self.template_name}' template from database for {agent_data.agent_name}")
            else:
                # Cache the base template if no customization needed
                self._template_cache = processed_flow_data
                logger.info(f"Loaded '{self.template_name}' template from database")

            return processed_flow_data

        except Exception as e:
            logger.error(f"Error loading '{self.template_name}' template from database: {e}")
            # Fallback to the original template factory if database load fails
            logger.warning("Falling back to generated template")
            return {}

    def _customize_template_with_agent_data(self, flow_data: dict, agent_data: AgentData) -> dict:
        """Customize only the system prompt in the Agent node."""
        import copy
        customized_data = copy.deepcopy(flow_data)

        # Find and update the Agent component's system prompt only
        nodes = customized_data.get('nodes', [])
        for node in nodes:
            node_data = node.get('data', {})
            if node_data.get('type') == 'Agent':
                # Update the system prompt with agent's description
                template = node_data.get('node', {}).get('template', {})
                if 'system_prompt' in template:
                    # Simple system prompt with agent name and description
                    system_prompt = f"You are {agent_data.agent_name}. {agent_data.description}"
                    template['system_prompt']['value'] = system_prompt
                    logger.debug(f"Updated system prompt for {agent_data.agent_name}")
                break

        return customized_data

    async def _ensure_folders_exist(self) -> None:
        """Ensure required folders exist for the user."""
        required_folders = ["Starter Project", "Marketplace Agent"]

        for folder_name in required_folders:
            # Check if folder exists
            existing_id = await self._get_folder_id(folder_name)

            if not existing_id:
                # Create the folder with appropriate user_id
                if folder_name == "Marketplace Agent":
                    # Marketplace Agent should be global (user_id = NULL)
                    user_id_for_folder = None
                    logger.info(f"Creating global folder '{folder_name}'")
                else:
                    # Other folders are user-specific
                    user_id_for_folder = self.user_id
                    logger.info(f"Creating folder '{folder_name}' for user {self.user_id}")

                folder = Folder(
                    id=uuid4(),
                    name=folder_name,
                    description=f"Auto-created folder for {folder_name.lower()}",
                    user_id=user_id_for_folder,
                    parent_id=None
                )

                self.session.add(folder)
                await self.session.flush()  # Get the folder ID

                # Update cache
                self._folder_cache[folder_name] = folder.id
                logger.info(f"Created folder '{folder_name}' with ID {folder.id}")

    async def get_username_by_id(self, user_id: UUID) -> Optional[str]:
        """Get username by user ID."""
        result = await self.session.execute(
            text('SELECT username FROM "user" WHERE id = :user_id LIMIT 1'),
            {"user_id": str(user_id)}
        )
        row = result.fetchone()
        return row.username if row else None
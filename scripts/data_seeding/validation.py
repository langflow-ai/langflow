"""Validation utilities for agent seeding."""

import re
import logging
from typing import List, Set, Dict, Any, Optional
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text

from .models import AgentData, ValidationError


logger = logging.getLogger(__name__)


class AgentDataValidator:
    """Validator for agent data integrity and business rules."""

    def __init__(self, session: AsyncSession, user_id: Optional[UUID] = None):
        self.session = session
        self.user_id = user_id

    async def validate_batch(self, agents_data: List[AgentData]) -> Dict[str, List[ValidationError]]:
        """Validate a batch of agent data."""
        validation_results = {}

        # Check for duplicate names within batch
        agent_names = [agent.agent_name for agent in agents_data]
        duplicates = self._find_duplicates(agent_names)

        for agent_data in agents_data:
            errors = []

            # Basic field validation
            errors.extend(self._validate_required_fields(agent_data))
            errors.extend(self._validate_field_formats(agent_data))

            # Business rule validation
            errors.extend(self._validate_business_rules(agent_data))

            # Check for duplicates within batch
            if agent_data.agent_name in duplicates:
                errors.append(ValidationError(
                    field="agent_name",
                    value=agent_data.agent_name,
                    error="Duplicate agent name found in batch"
                ))

            validation_results[agent_data.agent_name] = errors

        # Database validation (async operations)
        await self._validate_against_database(agents_data, validation_results)

        return validation_results

    def _validate_required_fields(self, agent_data: AgentData) -> List[ValidationError]:
        """Validate required fields are present and non-empty."""
        errors = []

        required_fields = {
            'agent_name': agent_data.agent_name,
            'description': agent_data.description,
            'domain_area': agent_data.domain_area,
            'goals': agent_data.goals,
            'kpis': agent_data.kpis,
            'tools': agent_data.tools
        }

        for field_name, value in required_fields.items():
            if not value or not value.strip():
                errors.append(ValidationError(
                    field=field_name,
                    value=str(value),
                    error=f"Required field '{field_name}' is empty or missing"
                ))

        return errors

    def _validate_field_formats(self, agent_data: AgentData) -> List[ValidationError]:
        """Validate field formats and constraints."""
        errors = []

        # Agent name validation
        if agent_data.agent_name:
            if len(agent_data.agent_name) > 100:
                errors.append(ValidationError(
                    field="agent_name",
                    value=agent_data.agent_name,
                    error="Agent name exceeds 100 characters"
                ))

            # Check for invalid characters in agent name
            if not re.match(r'^[a-zA-Z0-9\s\-_().\/&]+$', agent_data.agent_name):
                errors.append(ValidationError(
                    field="agent_name",
                    value=agent_data.agent_name,
                    error="Agent name contains invalid characters"
                ))

        # Description validation
        if agent_data.description and len(agent_data.description) > 2000:
            errors.append(ValidationError(
                field="description",
                value=agent_data.description[:50] + "...",
                error="Description exceeds 2000 characters"
            ))

        # Endpoint name validation
        endpoint_name = agent_data.endpoint_name
        if endpoint_name:
            if not re.match(r'^[a-z0-9\-_]+$', endpoint_name):
                errors.append(ValidationError(
                    field="endpoint_name",
                    value=endpoint_name,
                    error="Endpoint name must contain only lowercase letters, numbers, hyphens, and underscores"
                ))

            if len(endpoint_name) > 50:
                errors.append(ValidationError(
                    field="endpoint_name",
                    value=endpoint_name,
                    error="Endpoint name exceeds 50 characters"
                ))

        return errors

    def _validate_business_rules(self, agent_data: AgentData) -> List[ValidationError]:
        """Validate business-specific rules."""
        errors = []

        # At least one applicability must be true
        if not any([
            agent_data.applicable_to_payers,
            agent_data.applicable_to_payviders,
            agent_data.applicable_to_providers
        ]):
            errors.append(ValidationError(
                field="applicability",
                value="all_false",
                error="Agent must be applicable to at least one entity type (payers, payviders, or providers)"
            ))

        # Domain area validation - get from AgentDomain enum
        from .models import AgentDomain
        valid_domains = {domain.value for domain in AgentDomain}

        if agent_data.domain_area not in valid_domains:
            errors.append(ValidationError(
                field="domain_area",
                value=agent_data.domain_area,
                error=f"Invalid domain area. Must be one of: {', '.join(valid_domains)}"
            ))

        return errors

    async def _validate_against_database(
        self,
        agents_data: List[AgentData],
        validation_results: Dict[str, List[ValidationError]]
    ):
        """Validate data against existing database records."""
        try:
            # Only perform database validation if user_id is provided
            if not self.user_id:
                logger.warning("No user_id provided - skipping database validation")
                return

            # Check for existing agent names (user-scoped)
            agent_names = [agent.agent_name for agent in agents_data]
            placeholders = ','.join([f':name_{i}' for i in range(len(agent_names))])

            query = f"""
                SELECT name FROM flow
                WHERE name IN ({placeholders})
                AND user_id = :user_id
            """

            params = {f'name_{i}': name for i, name in enumerate(agent_names)}
            params['user_id'] = str(self.user_id)
            result = await self.session.execute(text(query), params)
            existing_names = {row.name for row in result.fetchall()}

            # Check for existing endpoint names (user-scoped)
            endpoint_names = [agent.endpoint_name for agent in agents_data if agent.endpoint_name]
            if endpoint_names:
                placeholders = ','.join([f':endpoint_{i}' for i in range(len(endpoint_names))])
                query = f"""
                    SELECT endpoint_name FROM flow
                    WHERE endpoint_name IN ({placeholders})
                    AND user_id = :user_id
                """

                params = {f'endpoint_{i}': name for i, name in enumerate(endpoint_names)}
                params['user_id'] = str(self.user_id)
                result = await self.session.execute(text(query), params)
                existing_endpoints = {row.endpoint_name for row in result.fetchall()}
            else:
                existing_endpoints = set()

            # Add validation errors for existing records
            for agent_data in agents_data:
                errors = validation_results[agent_data.agent_name]

                if agent_data.agent_name in existing_names:
                    errors.append(ValidationError(
                        field="agent_name",
                        value=agent_data.agent_name,
                        error="Agent with this name already exists for this user"
                    ))

                if agent_data.endpoint_name in existing_endpoints:
                    errors.append(ValidationError(
                        field="endpoint_name",
                        value=agent_data.endpoint_name,
                        error="Endpoint name already exists for this user"
                    ))

        except Exception as e:
            logger.error(f"Database validation failed: {e}")
            # Add generic error for all agents
            for agent_name in validation_results.keys():
                validation_results[agent_name].append(ValidationError(
                    field="database",
                    value="",
                    error=f"Database validation failed: {str(e)}"
                ))

    def _find_duplicates(self, items: List[str]) -> Set[str]:
        """Find duplicate items in a list."""
        seen = set()
        duplicates = set()

        for item in items:
            if item in seen:
                duplicates.add(item)
            else:
                seen.add(item)

        return duplicates

    def validate_batch_uniqueness(self, agents_data: List[AgentData]) -> Dict[str, List[ValidationError]]:
        """Validate uniqueness within the batch itself."""
        validation_results = {agent.agent_name: [] for agent in agents_data}

        # Check for duplicate agent names within batch
        agent_names = [agent.agent_name for agent in agents_data]
        name_duplicates = self._find_duplicates(agent_names)

        # Check for duplicate endpoint names within batch
        endpoint_names = [agent.endpoint_name for agent in agents_data if agent.endpoint_name]
        endpoint_duplicates = self._find_duplicates(endpoint_names)

        for agent_data in agents_data:
            errors = validation_results[agent_data.agent_name]

            if agent_data.agent_name in name_duplicates:
                errors.append(ValidationError(
                    field="agent_name",
                    value=agent_data.agent_name,
                    error="Duplicate agent name found in batch"
                ))

            if agent_data.endpoint_name in endpoint_duplicates:
                errors.append(ValidationError(
                    field="endpoint_name",
                    value=agent_data.endpoint_name,
                    error="Duplicate endpoint name found in batch"
                ))

        return validation_results

    def get_validation_summary(self, validation_results: Dict[str, List[ValidationError]]) -> Dict[str, Any]:
        """Generate a summary of validation results."""
        total_agents = len(validation_results)
        agents_with_errors = sum(1 for errors in validation_results.values() if errors)
        total_errors = sum(len(errors) for errors in validation_results.values())

        error_by_field = {}
        for errors in validation_results.values():
            for error in errors:
                if error.field not in error_by_field:
                    error_by_field[error.field] = 0
                error_by_field[error.field] += 1

        return {
            "total_agents": total_agents,
            "valid_agents": total_agents - agents_with_errors,
            "agents_with_errors": agents_with_errors,
            "total_errors": total_errors,
            "error_rate": agents_with_errors / total_agents if total_agents > 0 else 0,
            "errors_by_field": error_by_field
        }
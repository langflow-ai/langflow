"""Validator for YAML specifications."""

import logging
from typing import List

import yaml

from .component_resolver import ComponentResolver
from .models import ComponentStatus, ValidationReport

logger = logging.getLogger(__name__)


class SpecValidator:
    """Validates YAML specifications - checks if components exist."""

    def __init__(self, component_resolver: ComponentResolver):
        """
        Initialize validator with component resolver.

        Args:
            component_resolver: ComponentResolver instance for finding components
        """
        self.resolver = component_resolver

    async def validate(self, yaml_content: str) -> ValidationReport:
        """
        Validate YAML specification - check component existence only.

        This is Step 1 of validation. We ONLY check if components exist in the catalog.
        Later steps will validate configs, connections, etc.

        Steps:
        1. Parse the YAML content
        2. Load the component catalog
        3. For each component in YAML:
           - Get the type field (class name)
           - Search catalog using component_resolver
           - Record whether it was found or not
        4. Build and return a ValidationReport

        Example:
            Input YAML has 6 components with types:
            - PromptComponent
            - ChatInput
            - AgentComponent
            - KnowledgeHubSearchComponent
            - APIRequestComponent
            - ChatOutput

            Validator checks each one:
            ✓ PromptComponent → Found as "Prompt Template" in "processing"
            ✓ ChatInput → Found as "ChatInput" in "input_output"
            ✓ AgentComponent → Found as "Agent" in "agents"
            ... etc

            Returns: ValidationReport with valid=True, all 6 found

        Args:
            yaml_content: YAML specification string

        Returns:
            ValidationReport with validation results
        """
        errors: List[str] = []
        component_statuses: List[ComponentStatus] = []

        try:
            # Step 1: Parse YAML
            spec_dict = yaml.safe_load(yaml_content)
            if not spec_dict:
                return ValidationReport(
                    valid=False,
                    total_components=0,
                    found_components=0,
                    missing_components=0,
                    components=[],
                    errors=["Empty or invalid YAML content"],
                )

            # Step 2: Load component catalog
            await self.resolver.fetch_all_components()

            # Step 3: Get components list from YAML
            components = spec_dict.get("components", [])
            if not components:
                errors.append("No components defined in specification")

            # Step 4: Check each component
            found_count = 0

            for component in components:
                # Extract component info from YAML
                comp_id = component.get("id", "unknown")
                comp_name = component.get("name", "unknown")
                comp_type = component.get("type", "unknown")

                logger.info(f"Validating component: id={comp_id}, name={comp_name}, type={comp_type}")

                # Try to find component in catalog
                result = self.resolver.find_component(comp_type)

                if result:
                    # Component found!
                    category, catalog_name, comp_data = result

                    component_statuses.append(
                        ComponentStatus(
                            id=comp_id,
                            name=comp_name,
                            yaml_type=comp_type,
                            found=True,
                            catalog_name=catalog_name,
                            category=category,
                            error=None,
                        )
                    )
                    found_count += 1
                    logger.info(f"  ✓ Found: {comp_type} → {category}.{catalog_name}")

                else:
                    # Component NOT found
                    error_msg = f"Component type '{comp_type}' not found in catalog"

                    component_statuses.append(
                        ComponentStatus(
                            id=comp_id,
                            name=comp_name,
                            yaml_type=comp_type,
                            found=False,
                            catalog_name=None,
                            category=None,
                            error=error_msg,
                        )
                    )
                    errors.append(f"Component '{comp_id}' (type: '{comp_type}') not found in catalog")
                    logger.warning(f"  ✗ Not found: {comp_type}")

            # Build final report
            total = len(components)
            missing = total - found_count
            is_valid = missing == 0  # Valid only if ALL components found

            logger.info(f"Validation complete: {found_count}/{total} components found")

            return ValidationReport(
                valid=is_valid,
                total_components=total,
                found_components=found_count,
                missing_components=missing,
                components=component_statuses,
                errors=errors,
            )

        except yaml.YAMLError as e:
            # YAML parsing failed
            logger.error(f"YAML parsing error: {e}")
            return ValidationReport(
                valid=False,
                total_components=0,
                found_components=0,
                missing_components=0,
                components=[],
                errors=[f"YAML parsing error: {str(e)}"],
            )

        except Exception as e:
            # Unexpected error
            logger.error(f"Validation error: {e}", exc_info=True)
            return ValidationReport(
                valid=False,
                total_components=0,
                found_components=0,
                missing_components=0,
                components=[],
                errors=[f"Validation failed: {str(e)}"],
            )
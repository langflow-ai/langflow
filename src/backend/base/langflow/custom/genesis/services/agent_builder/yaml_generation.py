"""
YAML Generation Engine for Agent Builder

Generates Langflow-compatible agent YAML from assembled components.
Adapted from Genesis YAMLGenerationEngine for service context.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .component_assembly import AssemblyResult
from .task_decomposition import TaskAnalysis


class YAMLGenerationEngine:
    """Engine for generating agent YAML specifications"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_agent_yaml(self, task_analysis: TaskAnalysis,
                          assembly_result: AssemblyResult,
                          user_request: str) -> str:
        """
        Generate complete agent YAML specification

        Args:
            task_analysis: Task decomposition results
            assembly_result: Component assembly results
            user_request: Original user request

        Returns:
            Complete YAML string for Langflow agent
        """
        try:
            # Generate agent metadata
            agent_metadata = self._generate_agent_metadata(task_analysis, assembly_result, user_request)

            # Generate components section
            components = self._generate_components_section(assembly_result.components)

            # Combine into full YAML
            yaml_content = f"""name: {agent_metadata['name']}
description: {agent_metadata['description']}
domain: {task_analysis.domain}

components:
{components}

metadata:
  generated_at: '{agent_metadata['generated_at']}'
  optimization_score: {assembly_result.compatibility_score}
  source_requirements:
    original_request: "{user_request}"
    primary_task: {task_analysis.primary_task}
    domain: {task_analysis.domain}
  validation:
    healthcare_compliant: {assembly_result.healthcare_compliant}
    chain_validated: {assembly_result.validation_passed}
"""

            self.logger.info("Generated agent YAML successfully")
            return yaml_content

        except Exception as e:
            self.logger.error(f"Error generating YAML: {e}")
            return self._generate_fallback_yaml(user_request)

    def _generate_agent_metadata(self, task_analysis: TaskAnalysis,
                               assembly_result: AssemblyResult,
                               user_request: str) -> Dict[str, Any]:
        """Generate agent metadata"""
        # Create agent name from task
        agent_name = self._generate_agent_name(task_analysis.primary_task, task_analysis.domain)

        # Create description
        description = f"Auto-generated {task_analysis.domain} agent for {task_analysis.primary_task}"

        return {
            "name": agent_name,
            "description": description,
            "generated_at": datetime.now().isoformat(),
            "component_count": len(assembly_result.components)
        }

    def _generate_agent_name(self, primary_task: str, domain: str) -> str:
        """Generate human-readable agent name"""
        task_names = {
            "summarization": "Summarization",
            "extraction": "Data Extraction",
            "classification": "Classification",
            "analysis": "Analysis",
            "general_processing": "Processing"
        }

        task_name = task_names.get(primary_task, "Processing")
        domain_name = domain.title() if domain != "general" else ""

        if domain_name:
            return f"{domain_name} {task_name} Agent"
        else:
            return f"{task_name} Agent"

    def _generate_components_section(self, components: List) -> str:
        """Generate the components section of YAML"""
        if not components:
            return self._generate_minimal_components()

        yaml_lines = []

        # Generate components with proper connections
        for i, comp_match in enumerate(components):
            comp_spec = comp_match.component_spec
            comp_yaml = self._generate_component_yaml(comp_spec, i, len(components))
            yaml_lines.append(comp_yaml)

        return "\n".join(yaml_lines)

    def _generate_component_yaml(self, comp_spec, index: int, total: int) -> str:
        """Generate YAML for a single component"""
        # Map component types to Langflow-compatible types
        langflow_type = self._map_to_langflow_type(comp_spec.component_type)

        yaml_block = f"""- id: component_{index + 1}
  name: {comp_spec.name}
  type: {langflow_type}"""

        # Add connections based on position
        if index == 0:
            # First component - input
            yaml_block += "\n  provides:\n  - useAs: input"
            if total > 1:
                yaml_block += f"\n    in: component_{index + 2}"
                yaml_block += "\n    description: Connect to next component"
        elif index == total - 1:
            # Last component - output
            yaml_block += "\n  provides:\n  - useAs: input"
            yaml_block += "\n    in: output"
            yaml_block += "\n    description: Final output"
        else:
            # Middle component
            yaml_block += f"\n  provides:\n  - useAs: input\n    in: component_{index + 2}"
            yaml_block += "\n    description: Connect to next component"

        return yaml_block

    def _map_to_langflow_type(self, genesis_type: str) -> str:
        """Map Genesis component types to Langflow component types"""
        type_mapping = {
            "genesis:chat_input": "ChatInput",
            "genesis:chat_output": "ChatOutput",
            "genesis:file_reader": "File",
            "agent:extraction_agent": "Agent",  # Generic agent type
            "agent:summarization_agent": "Agent",
            "agent:classification_agent": "Agent",
            "agent:analysis_agent": "Agent",
        }

        return type_mapping.get(genesis_type, "Agent")  # Default to Agent

    def _generate_minimal_components(self) -> str:
        """Generate minimal component chain when no components found"""
        return """- id: input
  name: User Input
  type: ChatInput
  provides:
  - useAs: input
    in: output
    description: Direct input to output

- id: output
  name: Result Output
  type: ChatOutput"""

    def _generate_fallback_yaml(self, user_request: str) -> str:
        """Generate fallback YAML when generation fails"""
        return f"""name: Fallback Agent
description: Auto-generated agent for request - generation failed
domain: general

components:
- id: input
  name: User Input
  type: ChatInput
  provides:
  - useAs: input
    in: output
    description: Fallback connection

- id: output
  name: Result Output
  type: ChatOutput

metadata:
  generated_at: '{datetime.now().isoformat()}'
  optimization_score: 0.0
  source_requirements:
    original_request: "{user_request}"
    error: "YAML generation failed"
"""

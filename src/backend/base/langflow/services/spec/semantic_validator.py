"""
Semantic validation engine for Genesis specifications.

This module provides semantic validation beyond basic schema validation,
including component relationships, workflow patterns, and business logic validation.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
import logging
from collections import defaultdict, deque

from .validation_schemas import (
    get_component_config_schema,
    get_validation_patterns_for_workflow,
    CREWAI_WORKFLOW_PATTERNS
)

logger = logging.getLogger(__name__)


class SemanticValidationResult:
    """Result of semantic validation with detailed error tracking."""

    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.suggestions: List[Dict[str, Any]] = []
        self.is_valid = True

    def add_error(self, code: str, message: str, component_id: Optional[str] = None,
                  field: Optional[str] = None, suggestion: Optional[str] = None):
        """Add a validation error with context."""
        self.errors.append({
            "code": code,
            "message": message,
            "component_id": component_id,
            "field": field,
            "severity": "error",
            "suggestion": suggestion
        })
        self.is_valid = False

    def add_warning(self, code: str, message: str, component_id: Optional[str] = None,
                   field: Optional[str] = None, suggestion: Optional[str] = None):
        """Add a validation warning with context."""
        self.warnings.append({
            "code": code,
            "message": message,
            "component_id": component_id,
            "field": field,
            "severity": "warning",
            "suggestion": suggestion
        })

    def add_suggestion(self, code: str, message: str, component_id: Optional[str] = None,
                      action: Optional[str] = None):
        """Add an improvement suggestion."""
        self.suggestions.append({
            "code": code,
            "message": message,
            "component_id": component_id,
            "action": action,
            "severity": "suggestion"
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "summary": {
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
                "suggestion_count": len(self.suggestions)
            }
        }


class SemanticValidator:
    """
    Semantic validation engine for Genesis specifications.

    Performs deep validation of component relationships, workflow patterns,
    and business logic beyond basic schema validation.
    """

    def __init__(self, component_mapper=None):
        """Initialize the semantic validator."""
        self.component_mapper = component_mapper
        self.result = SemanticValidationResult()

    def validate(self, spec_dict: Dict[str, Any]) -> SemanticValidationResult:
        """
        Perform comprehensive semantic validation.

        Args:
            spec_dict: Parsed specification dictionary

        Returns:
            Detailed validation result with errors, warnings, and suggestions
        """
        self.result = SemanticValidationResult()

        try:
            # 1. Validate basic semantic structure
            self._validate_basic_semantics(spec_dict)

            # 2. Validate component relationships
            self._validate_component_relationships(spec_dict)

            # 3. Validate workflow patterns (CrewAI, etc.)
            self._validate_workflow_patterns(spec_dict)

            # 4. Validate component configurations
            self._validate_component_configurations(spec_dict)

            # 5. Validate data flow and connections
            self._validate_data_flow(spec_dict)

            # 6. Validate business logic consistency
            self._validate_business_logic(spec_dict)

            # 7. Performance and scalability validation
            self._validate_performance_characteristics(spec_dict)

            # 8. Security and compliance validation
            self._validate_security_compliance(spec_dict)

            logger.info(f"Semantic validation completed: {len(self.result.errors)} errors, "
                       f"{len(self.result.warnings)} warnings, {len(self.result.suggestions)} suggestions")

        except Exception as e:
            logger.error(f"Error during semantic validation: {e}")
            self.result.add_error(
                "VALIDATION_ERROR",
                f"Internal validation error: {e}",
                suggestion="Please report this issue to the development team"
            )

        return self.result

    def _validate_basic_semantics(self, spec_dict: Dict[str, Any]):
        """Validate basic semantic requirements."""
        # Validate ID format and consistency
        spec_id = spec_dict.get("id")
        name = spec_dict.get("name", "").lower().replace(" ", "_")

        if spec_id:
            # Extract name from URN and compare with actual name
            try:
                urn_parts = spec_id.split(":")
                if len(urn_parts) >= 5:
                    urn_name = urn_parts[4]
                    if urn_name != name.replace("_", "-"):
                        self.result.add_warning(
                            "ID_NAME_MISMATCH",
                            f"ID contains '{urn_name}' but name suggests '{name.replace('_', '-')}'",
                            field="id",
                            suggestion=f"Consider updating ID to match name: urn:agent:genesis:autonomize.ai:{name.replace('_', '-')}:1.0.0"
                        )
            except Exception:
                pass

        # Validate goal-component alignment
        agent_goal = spec_dict.get("agentGoal", "").lower()
        components = self._get_components_list(spec_dict)

        # Check if components support the stated goal
        goal_keywords = {
            "search": ["knowledge_hub_search", "web_search", "search"],
            "analyze": ["analysis", "classifier", "model"],
            "generate": ["llm", "agent", "openai", "anthropic"],
            "process": ["processing", "transformer", "converter"],
            "integrate": ["api", "connector", "integration"],
            "automate": ["workflow", "crew", "agent"]
        }

        for keyword, component_indicators in goal_keywords.items():
            if keyword in agent_goal:
                has_supporting_component = any(
                    any(indicator in comp.get("type", "").lower() for indicator in component_indicators)
                    for comp in components
                )
                if not has_supporting_component:
                    self.result.add_suggestion(
                        "GOAL_COMPONENT_ALIGNMENT",
                        f"Goal mentions '{keyword}' but no supporting components found",
                        action=f"Consider adding components like: {', '.join(f'genesis:{ind}' for ind in component_indicators[:2])}"
                    )

    def _validate_component_relationships(self, spec_dict: Dict[str, Any]):
        """Validate component relationship semantics."""
        components = self._get_components_list(spec_dict)
        component_map = {comp.get("id"): comp for comp in components}

        # 1. Validate provides relationships
        for component in components:
            comp_id = component.get("id")
            provides = component.get("provides", [])

            for provide in provides:
                if not isinstance(provide, dict):
                    continue

                target_id = provide.get("in")
                use_as = provide.get("useAs")

                # Check target exists
                if target_id not in component_map:
                    self.result.add_error(
                        "MISSING_TARGET_COMPONENT",
                        f"Component '{comp_id}' references non-existent target '{target_id}'",
                        component_id=comp_id,
                        suggestion=f"Add component with ID '{target_id}' or fix the reference"
                    )
                    continue

                target_comp = component_map[target_id]

                # Validate semantic compatibility
                self._validate_connection_semantics(component, target_comp, provide)

        # 2. Check for orphaned components
        connected_components = set()
        for component in components:
            comp_id = component.get("id")
            provides = component.get("provides", [])

            if provides:
                connected_components.add(comp_id)
                for provide in provides:
                    if isinstance(provide, dict) and "in" in provide:
                        connected_components.add(provide["in"])

        orphaned = [comp.get("id") for comp in components
                   if comp.get("id") not in connected_components and
                   comp.get("type") not in ["genesis:chat_input", "genesis:chat_output"]]

        if orphaned:
            self.result.add_warning(
                "ORPHANED_COMPONENTS",
                f"Components not connected to workflow: {', '.join(orphaned)}",
                suggestion="Connect these components or remove them if not needed"
            )

        # 3. Validate circular dependencies
        self._check_circular_dependencies(components)

    def _validate_connection_semantics(self, source_comp: Dict[str, Any],
                                     target_comp: Dict[str, Any],
                                     provide: Dict[str, Any]):
        """Validate semantic correctness of component connections."""
        source_type = source_comp.get("type", "")
        target_type = target_comp.get("type", "")
        use_as = provide.get("useAs")
        source_id = source_comp.get("id")
        target_id = target_comp.get("id")

        # Tool connection validation
        if use_as == "tools":
            # Check if source can be a tool
            can_be_tool = (
                source_comp.get("asTools", False) or
                "tool" in source_type or
                "mcp" in source_type or
                "knowledge_hub_search" in source_type or
                "api" in source_type
            )

            if not can_be_tool:
                self.result.add_error(
                    "INVALID_TOOL_CONNECTION",
                    f"Component '{source_id}' used as tool but not marked as tool-capable",
                    component_id=source_id,
                    suggestion="Set 'asTools: true' or use a different component type"
                )

            # Check if target can accept tools
            can_accept_tools = "agent" in target_type or "crew" in target_type
            if not can_accept_tools:
                self.result.add_error(
                    "INVALID_TOOL_TARGET",
                    f"Component '{target_id}' cannot accept tools",
                    component_id=target_id,
                    suggestion="Use an agent or crew component as the target"
                )

        # System prompt validation
        elif use_as == "system_prompt":
            if "agent" not in target_type:
                self.result.add_warning(
                    "NON_AGENT_SYSTEM_PROMPT",
                    f"System prompt sent to non-agent component '{target_id}'",
                    component_id=target_id,
                    suggestion="System prompts are typically used with agent components"
                )

        # Input/output flow validation
        elif use_as in ["input", "message", "data"]:
            # Check logical flow patterns
            if source_type == "genesis:chat_output" and target_type != "genesis:chat_input":
                self.result.add_warning(
                    "UNUSUAL_OUTPUT_CONNECTION",
                    f"Chat output '{source_id}' connected to '{target_id}' instead of ending workflow",
                    component_id=source_id,
                    suggestion="Chat output typically ends the workflow"
                )

    def _validate_workflow_patterns(self, spec_dict: Dict[str, Any]):
        """Validate workflow-specific patterns (CrewAI, etc.)."""
        kind = spec_dict.get("kind", "")
        components = self._get_components_list(spec_dict)

        if kind == "Multi Agent":
            self._validate_crewai_workflow(spec_dict, components)
        elif kind == "Single Agent":
            self._validate_single_agent_workflow(spec_dict, components)

    def _validate_crewai_workflow(self, spec_dict: Dict[str, Any], components: List[Dict[str, Any]]):
        """Validate CrewAI multi-agent workflow patterns."""
        # Identify CrewAI components
        agents = [c for c in components if c.get("type") == "genesis:crewai_agent"]
        tasks = [c for c in components if "task" in c.get("type", "")]
        crews = [c for c in components if "crew" in c.get("type", "")]

        if not agents:
            self.result.add_error(
                "MISSING_CREWAI_AGENTS",
                "Multi Agent workflow requires CrewAI agent components",
                suggestion="Add 'genesis:crewai_agent' components with roles and goals"
            )
            return

        if len(agents) < 2:
            self.result.add_warning(
                "INSUFFICIENT_AGENTS",
                f"Multi Agent workflow has only {len(agents)} agent(s), consider adding more for collaboration",
                suggestion="Add at least 2 agents for meaningful multi-agent interaction"
            )

        # Validate agent configurations
        for agent in agents:
            agent_id = agent.get("id")
            config = agent.get("config", {})

            required_fields = ["role", "goal", "backstory"]
            missing_fields = [field for field in required_fields if not config.get(field)]

            if missing_fields:
                self.result.add_error(
                    "INCOMPLETE_AGENT_CONFIG",
                    f"Agent '{agent_id}' missing required fields: {', '.join(missing_fields)}",
                    component_id=agent_id,
                    suggestion=f"Add {', '.join(missing_fields)} to agent configuration"
                )

            # Validate role uniqueness
            role = config.get("role", "")
            duplicate_roles = [a for a in agents if a.get("config", {}).get("role") == role and a.get("id") != agent_id]
            if duplicate_roles:
                self.result.add_warning(
                    "DUPLICATE_AGENT_ROLES",
                    f"Multiple agents have role '{role}': {agent_id}, {', '.join(a.get('id') for a in duplicate_roles)}",
                    component_id=agent_id,
                    suggestion="Consider unique roles for each agent to avoid confusion"
                )

        # Validate task-agent relationships
        if tasks:
            for task in tasks:
                task_id = task.get("id")
                config = task.get("config", {})

                agent_id = config.get("agent_id")
                if agent_id and agent_id not in [a.get("id") for a in agents]:
                    self.result.add_error(
                        "MISSING_TASK_AGENT",
                        f"Task '{task_id}' references non-existent agent '{agent_id}'",
                        component_id=task_id,
                        suggestion=f"Create agent with ID '{agent_id}' or fix the reference"
                    )

        # Validate crew configuration
        if crews:
            for crew in crews:
                crew_id = crew.get("id")
                config = crew.get("config", {})

                crew_agents = config.get("agents", [])
                crew_tasks = config.get("tasks", [])

                # Check if all referenced agents exist
                missing_agents = [aid for aid in crew_agents if aid not in [a.get("id") for a in agents]]
                if missing_agents:
                    self.result.add_error(
                        "MISSING_CREW_AGENTS",
                        f"Crew '{crew_id}' references non-existent agents: {', '.join(missing_agents)}",
                        component_id=crew_id,
                        suggestion="Ensure all referenced agents are defined in the specification"
                    )

                # Check if all referenced tasks exist
                missing_tasks = [tid for tid in crew_tasks if tid not in [t.get("id") for t in tasks]]
                if missing_tasks:
                    self.result.add_error(
                        "MISSING_CREW_TASKS",
                        f"Crew '{crew_id}' references non-existent tasks: {', '.join(missing_tasks)}",
                        component_id=crew_id,
                        suggestion="Ensure all referenced tasks are defined in the specification"
                    )

                # Validate crew execution flow
                self._validate_crewai_execution_flow(crew, agents, tasks)

                # Validate memory configuration
                self._validate_crewai_memory_config(crew, agents)

                # Validate tool delegation patterns
                self._validate_crewai_tool_delegation(crew, agents, spec_dict)

    def _validate_crewai_execution_flow(self, crew: Dict[str, Any], agents: List[Dict[str, Any]], tasks: List[Dict[str, Any]]):
        """Validate CrewAI execution flow and task dependencies."""
        crew_id = crew.get("id")
        crew_type = crew.get("type", "")
        config = crew.get("config", {})

        crew_agents = config.get("agents", [])
        crew_tasks = config.get("tasks", [])

        # Validate sequential crew execution
        if "sequential" in crew_type:
            # Tasks should have clear sequence
            task_dependencies = {}
            for task in tasks:
                if task.get("id") in crew_tasks:
                    task_config = task.get("config", {})
                    depends_on = task_config.get("depends_on", [])
                    task_dependencies[task.get("id")] = depends_on

            # Check for proper task sequencing
            if len(crew_tasks) > 1:
                isolated_tasks = [tid for tid in crew_tasks if not task_dependencies.get(tid, [])]
                if len(isolated_tasks) > 1:
                    self.result.add_warning(
                        "UNSEQUENCED_TASKS",
                        f"Crew '{crew_id}' has multiple isolated tasks: {', '.join(isolated_tasks)}",
                        component_id=crew_id,
                        suggestion="Define task dependencies with 'depends_on' field for proper sequencing"
                    )

        # Validate hierarchical crew execution
        elif "hierarchical" in crew_type:
            manager_config = config.get("manager", {})
            if not manager_config:
                self.result.add_error(
                    "MISSING_CREW_MANAGER",
                    f"Hierarchical crew '{crew_id}' requires a manager configuration",
                    component_id=crew_id,
                    suggestion="Add 'manager' configuration with agent or LLM settings"
                )

            # Check if agents allow delegation
            non_delegating_agents = []
            for agent_id in crew_agents:
                agent = next((a for a in agents if a.get("id") == agent_id), None)
                if agent:
                    agent_config = agent.get("config", {})
                    if not agent_config.get("allow_delegation", False):
                        non_delegating_agents.append(agent_id)

            if non_delegating_agents:
                self.result.add_warning(
                    "DELEGATION_DISABLED",
                    f"Hierarchical crew '{crew_id}' has agents with delegation disabled: {', '.join(non_delegating_agents)}",
                    component_id=crew_id,
                    suggestion="Enable 'allow_delegation' for agents in hierarchical crews"
                )

        # Validate task-agent assignment coverage
        assigned_agents = set()
        for task in tasks:
            if task.get("id") in crew_tasks:
                task_config = task.get("config", {})
                agent_id = task_config.get("agent_id")
                if agent_id:
                    assigned_agents.add(agent_id)

        unassigned_agents = set(crew_agents) - assigned_agents
        if unassigned_agents:
            self.result.add_warning(
                "UNASSIGNED_AGENTS",
                f"Crew '{crew_id}' has agents without tasks: {', '.join(unassigned_agents)}",
                component_id=crew_id,
                suggestion="Assign tasks to all agents or remove unused agents from crew"
            )

    def _validate_crewai_memory_config(self, crew: Dict[str, Any], agents: List[Dict[str, Any]]):
        """Validate CrewAI memory and knowledge sharing configuration."""
        crew_id = crew.get("id")
        config = crew.get("config", {})

        # Check memory configuration
        memory_config = config.get("memory", {})
        if memory_config:
            memory_type = memory_config.get("type", "short_term")

            if memory_type == "long_term" and not memory_config.get("provider"):
                self.result.add_error(
                    "INCOMPLETE_MEMORY_CONFIG",
                    f"Crew '{crew_id}' uses long-term memory but no provider specified",
                    component_id=crew_id,
                    suggestion="Specify memory provider (e.g., 'rag', 'vector_db') for long-term memory"
                )

        # Validate agent memory compatibility
        crew_agents = config.get("agents", [])
        for agent_id in crew_agents:
            agent = next((a for a in agents if a.get("id") == agent_id), None)
            if agent:
                agent_config = agent.get("config", {})
                agent_memory = agent_config.get("memory")

                if memory_config and agent_memory and agent_memory != memory_config:
                    self.result.add_warning(
                        "MEMORY_CONFIG_MISMATCH",
                        f"Agent '{agent_id}' memory config differs from crew '{crew_id}' memory config",
                        component_id=agent_id,
                        suggestion="Align agent and crew memory configurations for consistency"
                    )

    def _validate_crewai_tool_delegation(self, crew: Dict[str, Any], agents: List[Dict[str, Any]], spec_dict: Dict[str, Any]):
        """Validate CrewAI tool delegation and sharing patterns."""
        crew_id = crew.get("id")
        config = crew.get("config", {})
        crew_agents = config.get("agents", [])

        # Identify tools available to agents
        components = self._get_components_list(spec_dict)
        agent_tools = {}

        for agent_id in crew_agents:
            agent_tools[agent_id] = []

            # Find tools connected to this agent
            for component in components:
                for provide in component.get("provides", []):
                    if (isinstance(provide, dict) and
                        provide.get("in") == agent_id and
                        provide.get("useAs") == "tools"):
                        agent_tools[agent_id].append(component.get("id"))

        # Check for tool sharing opportunities
        all_tools = set()
        for tools in agent_tools.values():
            all_tools.update(tools)

        if len(all_tools) > 0:
            agents_with_tools = [aid for aid, tools in agent_tools.items() if tools]
            agents_without_tools = [aid for aid in crew_agents if aid not in agents_with_tools]

            if agents_without_tools and len(agents_with_tools) > 0:
                self.result.add_suggestion(
                    "TOOL_SHARING_OPPORTUNITY",
                    f"Crew '{crew_id}' could benefit from tool sharing between agents",
                    component_id=crew_id,
                    action=f"Consider enabling tool delegation for agents: {', '.join(agents_without_tools)}"
                )

        # Validate delegation settings for tool access
        for agent_id in crew_agents:
            agent = next((a for a in agents if a.get("id") == agent_id), None)
            if agent:
                agent_config = agent.get("config", {})
                has_tools = len(agent_tools.get(agent_id, [])) > 0
                can_delegate = agent_config.get("allow_delegation", False)

                if has_tools and not can_delegate:
                    self.result.add_suggestion(
                        "DELEGATION_RECOMMENDATION",
                        f"Agent '{agent_id}' has tools but delegation is disabled",
                        component_id=agent_id,
                        action="Consider enabling 'allow_delegation' to share tools with other agents"
                    )

    def _validate_single_agent_workflow(self, spec_dict: Dict[str, Any], components: List[Dict[str, Any]]):
        """Validate single agent workflow patterns."""
        agents = [c for c in components if "agent" in c.get("type", "")]

        if len(agents) == 0:
            self.result.add_error(
                "MISSING_AGENT",
                "Single Agent workflow must have at least one agent component",
                suggestion="Add 'genesis:agent' or 'genesis:autonomize_agent' component"
            )
        elif len(agents) > 1:
            self.result.add_warning(
                "MULTIPLE_AGENTS_SINGLE_WORKFLOW",
                f"Single Agent workflow has {len(agents)} agents, consider Multi Agent workflow",
                suggestion="Change 'kind' to 'Multi Agent' or use only one agent"
            )

        # Validate agent has necessary inputs
        for agent in agents:
            agent_id = agent.get("id")

            # Check if agent receives input
            receives_input = any(
                provide.get("in") == agent_id and provide.get("useAs") in ["input", "message"]
                for comp in components
                for provide in comp.get("provides", [])
                if isinstance(provide, dict)
            )

            if not receives_input:
                self.result.add_warning(
                    "AGENT_NO_INPUT",
                    f"Agent '{agent_id}' doesn't receive any input",
                    component_id=agent_id,
                    suggestion="Connect an input component to provide data to the agent"
                )

    def _validate_component_configurations(self, spec_dict: Dict[str, Any]):
        """Validate component-specific configurations."""
        components = self._get_components_list(spec_dict)

        for component in components:
            comp_type = component.get("type")
            comp_id = component.get("id")
            config = component.get("config", {})

            # Get schema for this component type
            config_schema = get_component_config_schema(comp_type)
            if not config_schema:
                continue

            # Validate required fields
            required_fields = config_schema.get("required", [])
            missing_fields = [field for field in required_fields if field not in config]

            if missing_fields:
                self.result.add_error(
                    "MISSING_CONFIG_FIELDS",
                    f"Component '{comp_id}' missing required configuration: {', '.join(missing_fields)}",
                    component_id=comp_id,
                    field="config",
                    suggestion=f"Add required fields to config: {', '.join(missing_fields)}"
                )

            # Validate field values
            properties = config_schema.get("properties", {})
            for field, value in config.items():
                if field in properties:
                    field_schema = properties[field]
                    self._validate_config_field(comp_id, field, value, field_schema)

    def _validate_config_field(self, comp_id: str, field: str, value: Any, field_schema: Dict[str, Any]):
        """Validate individual configuration field."""
        field_type = field_schema.get("type")

        # Type validation
        if field_type == "string" and not isinstance(value, str):
            self.result.add_error(
                "INVALID_CONFIG_TYPE",
                f"Component '{comp_id}' field '{field}' must be a string, got {type(value).__name__}",
                component_id=comp_id,
                field=field
            )
        elif field_type == "integer" and not isinstance(value, int):
            self.result.add_error(
                "INVALID_CONFIG_TYPE",
                f"Component '{comp_id}' field '{field}' must be an integer, got {type(value).__name__}",
                component_id=comp_id,
                field=field
            )
        elif field_type == "number" and not isinstance(value, (int, float)):
            self.result.add_error(
                "INVALID_CONFIG_TYPE",
                f"Component '{comp_id}' field '{field}' must be a number, got {type(value).__name__}",
                component_id=comp_id,
                field=field
            )

        # Enum validation
        enum_values = field_schema.get("enum")
        if enum_values and value not in enum_values:
            self.result.add_error(
                "INVALID_ENUM_VALUE",
                f"Component '{comp_id}' field '{field}' has invalid value '{value}', must be one of: {', '.join(map(str, enum_values))}",
                component_id=comp_id,
                field=field,
                suggestion=f"Use one of: {', '.join(map(str, enum_values))}"
            )

        # Range validation
        minimum = field_schema.get("minimum")
        maximum = field_schema.get("maximum")
        if isinstance(value, (int, float)):
            if minimum is not None and value < minimum:
                self.result.add_error(
                    "VALUE_TOO_LOW",
                    f"Component '{comp_id}' field '{field}' value {value} is below minimum {minimum}",
                    component_id=comp_id,
                    field=field
                )
            if maximum is not None and value > maximum:
                self.result.add_error(
                    "VALUE_TOO_HIGH",
                    f"Component '{comp_id}' field '{field}' value {value} exceeds maximum {maximum}",
                    component_id=comp_id,
                    field=field
                )

    def _validate_data_flow(self, spec_dict: Dict[str, Any]):
        """Validate data flow through the workflow."""
        components = self._get_components_list(spec_dict)

        # Build flow graph
        flow_graph = defaultdict(list)
        component_types = {}

        for component in components:
            comp_id = component.get("id")
            comp_type = component.get("type")
            component_types[comp_id] = comp_type

            for provide in component.get("provides", []):
                if isinstance(provide, dict) and "in" in provide:
                    flow_graph[comp_id].append(provide["in"])

        # Check for complete data flow from input to output
        input_components = [comp.get("id") for comp in components if comp.get("type") == "genesis:chat_input"]
        output_components = [comp.get("id") for comp in components if comp.get("type") == "genesis:chat_output"]

        if input_components and output_components:
            for input_comp in input_components:
                for output_comp in output_components:
                    if not self._has_path(flow_graph, input_comp, output_comp):
                        self.result.add_warning(
                            "INCOMPLETE_DATA_FLOW",
                            f"No data flow path from input '{input_comp}' to output '{output_comp}'",
                            suggestion="Ensure components are properly connected to enable data flow"
                        )

    def _validate_business_logic(self, spec_dict: Dict[str, Any]):
        """Validate business logic consistency."""
        # Validate tools vs toolsUse flag
        tools_use = spec_dict.get("toolsUse", False)
        components = self._get_components_list(spec_dict)

        has_tools = any(
            comp.get("asTools", False) or "tool" in comp.get("type", "")
            for comp in components
        )

        if has_tools and not tools_use:
            self.result.add_warning(
                "TOOLS_FLAG_MISMATCH",
                "Specification contains tool components but toolsUse is false",
                field="toolsUse",
                suggestion="Set 'toolsUse: true' when using tool components"
            )
        elif not has_tools and tools_use:
            self.result.add_warning(
                "TOOLS_FLAG_UNUSED",
                "toolsUse is true but no tool components found",
                field="toolsUse",
                suggestion="Add tool components or set 'toolsUse: false'"
            )

        # Validate learning capability vs components
        learning = spec_dict.get("learningCapability", "None")
        if learning != "None":
            has_learning_components = any(
                "model" in comp.get("type", "") or "llm" in comp.get("type", "")
                for comp in components
            )
            if not has_learning_components:
                self.result.add_warning(
                    "LEARNING_WITHOUT_MODELS",
                    f"Learning capability '{learning}' specified but no learning-capable components found",
                    field="learningCapability",
                    suggestion="Add LLM or model components to support learning capabilities"
                )

    def _validate_performance_characteristics(self, spec_dict: Dict[str, Any]):
        """Validate performance and scalability aspects."""
        components = self._get_components_list(spec_dict)

        # Check for potential performance bottlenecks
        agent_count = sum(1 for c in components if "agent" in c.get("type", ""))
        if agent_count > 10:
            self.result.add_warning(
                "HIGH_AGENT_COUNT",
                f"Specification has {agent_count} agents, which may impact performance",
                suggestion="Consider reducing agent count or using hierarchical patterns"
            )

        # Check for synchronous API calls that might block
        api_components = [c for c in components if "api" in c.get("type", "")]
        for api_comp in api_components:
            config = api_comp.get("config", {})
            timeout = config.get("timeout", 30)

            if timeout > 60:
                self.result.add_warning(
                    "HIGH_API_TIMEOUT",
                    f"API component '{api_comp.get('id')}' has high timeout ({timeout}s)",
                    component_id=api_comp.get("id"),
                    suggestion="Consider reducing timeout or implementing async patterns"
                )

    def _validate_security_compliance(self, spec_dict: Dict[str, Any]):
        """Validate security and compliance aspects."""
        security_info = spec_dict.get("securityInfo", {})
        components = self._get_components_list(spec_dict)

        # Check for sensitive data handling
        has_api_components = any("api" in c.get("type", "") for c in components)
        if has_api_components and not security_info:
            self.result.add_suggestion(
                "MISSING_SECURITY_INFO",
                "Specification uses API components but lacks security information",
                action="Add securityInfo section to document data handling and compliance"
            )

        # Check for healthcare compliance
        healthcare_indicators = ["ehr", "patient", "medical", "health", "clinical", "hipaa"]
        spec_text = str(spec_dict).lower()

        if any(indicator in spec_text for indicator in healthcare_indicators):
            hipaa_compliant = security_info.get("hipaaCompliant")
            if hipaa_compliant is None:
                self.result.add_warning(
                    "MISSING_HIPAA_COMPLIANCE",
                    "Specification appears healthcare-related but HIPAA compliance not specified",
                    field="securityInfo.hipaaCompliant",
                    suggestion="Set 'hipaaCompliant' field to indicate HIPAA compliance status"
                )

    def _get_components_list(self, spec_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get components as a list regardless of format."""
        components = spec_dict.get("components", [])

        if isinstance(components, dict):
            # Convert dict format to list
            return [
                {**comp_data, "id": comp_id}
                for comp_id, comp_data in components.items()
            ]
        elif isinstance(components, list):
            return components
        else:
            return []

    def _check_circular_dependencies(self, components: List[Dict[str, Any]]):
        """Check for circular dependencies in component graph."""
        # Build dependency graph
        graph = defaultdict(list)
        for component in components:
            comp_id = component.get("id")
            for provide in component.get("provides", []):
                if isinstance(provide, dict) and "in" in provide:
                    graph[comp_id].append(provide["in"])

        # Use DFS to detect cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            if node in rec_stack:
                return True
            if node in visited:
                return False

            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if has_cycle(neighbor):
                    return True

            rec_stack.remove(node)
            return False

        # Check each component for cycles
        for component in components:
            comp_id = component.get("id")
            if comp_id not in visited and has_cycle(comp_id):
                self.result.add_error(
                    "CIRCULAR_DEPENDENCY",
                    f"Circular dependency detected involving component '{comp_id}'",
                    component_id=comp_id,
                    suggestion="Remove circular references between components"
                )
                break

    def _has_path(self, graph: Dict[str, List[str]], start: str, end: str) -> bool:
        """Check if there's a path from start to end in the graph."""
        if start == end:
            return True

        visited = set()
        queue = deque([start])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue

            visited.add(current)

            for neighbor in graph.get(current, []):
                if neighbor == end:
                    return True
                if neighbor not in visited:
                    queue.append(neighbor)

        return False
"""Pattern Analyzer for AI Studio Agent Builder - Generates component connections."""

import asyncio
from typing import Dict, List, Any, Optional
from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput, BoolInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger


class PatternAnalyzer(Component):
    """Analyzes agent specifications and generates proper component connections."""

    display_name = "Pattern Analyzer"
    description = "Analyzes specifications and generates component connections and data flow patterns"
    icon = "git-branch"
    name = "PatternAnalyzer"
    category = "Helpers"

    inputs = [
        MessageTextInput(
            name="spec_components",
            display_name="Spec Components",
            info="JSON list of components to analyze for connections",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="agent_goal",
            display_name="Agent Goal",
            info="The agent's primary goal to inform connection patterns",
            required=False,
            tool_mode=True,
        ),
        BoolInput(
            name="add_connections",
            display_name="Add Connections",
            info="Whether to add provides relationships to components",
            value=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Connected Components", name="connected_components", method="analyze_connections"),
    ]

    def analyze_connections(self) -> Data:
        """Analyze components and generate proper connections."""
        try:
            import json

            # Parse the components
            try:
                components = json.loads(self.spec_components) if isinstance(self.spec_components, str) else self.spec_components
            except json.JSONDecodeError:
                return Data(data={
                    "success": False,
                    "error": "Invalid JSON format for components",
                    "components": []
                })

            if not isinstance(components, list):
                return Data(data={
                    "success": False,
                    "error": "Components must be a list",
                    "components": []
                })

            if not self.add_connections:
                return Data(data={
                    "success": True,
                    "components": components,
                    "connections_added": 0,
                    "message": "No connections added (add_connections=False)"
                })

            # Analyze and add connections
            connected_components = self._generate_connections(components)
            connections_count = self._count_connections(connected_components)

            return Data(data={
                "success": True,
                "components": connected_components,
                "connections_added": connections_count,
                "message": f"Generated {connections_count} component connections",
                "flow_analysis": self._analyze_flow(connected_components)
            })

        except Exception as e:
            logger.error(f"Error in pattern analyzer: {e}")
            return Data(data={
                "success": False,
                "error": str(e),
                "components": []
            })

    def _generate_connections(self, components: List[Dict]) -> List[Dict]:
        """Generate proper component connections based on healthcare patterns."""
        if not components:
            return components

        # First, fix component structure to match specification requirements
        self._fix_component_structure(components)

        # Create a mapping of component IDs to components
        comp_map = {comp.get("id", f"comp_{i}"): comp for i, comp in enumerate(components)}
        comp_ids = list(comp_map.keys())

        # Standard healthcare flow patterns
        input_components = [comp for comp in components if comp.get("type") == "genesis:chat_input"]
        output_components = [comp for comp in components if comp.get("type") == "genesis:chat_output"]
        agent_components = [comp for comp in components if comp.get("type") == "genesis:agent"]
        prompt_components = [comp for comp in components if comp.get("type") == "genesis:prompt"]
        model_components = [comp for comp in components if comp.get("type", "").startswith("genesis:") and
                          any(model_type in comp.get("type", "") for model_type in ["clinical_llm", "icd10", "cpt", "rxnorm", "combined_entity"])]
        api_components = [comp for comp in components if comp.get("type") == "genesis:api_request"]
        tool_components = [comp for comp in components if comp.get("type") == "genesis:mcp_tool"]

        # Generate connections for each component
        for comp in components:
            comp_id = comp.get("id")
            comp_type = comp.get("type", "")

            if not comp_id:
                continue

            # Initialize provides if not exists
            if "provides" not in comp:
                comp["provides"] = []

            # Connection patterns based on component type
            if comp_type == "genesis:chat_input":
                # Input connects to processing components (models, agents, APIs)
                targets = []

                # Prioritize clinical models for healthcare inputs
                if model_components:
                    targets.extend([m.get("id") for m in model_components[:2]])  # Limit to 2 models
                elif agent_components:
                    targets.append(agent_components[0].get("id"))
                elif api_components:
                    targets.append(api_components[0].get("id"))

                for target in targets:
                    if target and target != comp_id:
                        comp["provides"].append({
                            "useAs": "input_value",
                            "in": target,
                            "description": f"Provides user input to {target}"
                        })

            elif comp_type in ["genesis:clinical_llm", "genesis:icd10", "genesis:cpt_code", "genesis:cpt", "genesis:rxnorm", "genesis:combined_entity_linking"]:
                # Medical models connect to agents or other models, then to output
                targets = []

                # Connect to agent if available, or to other models in sequence
                if agent_components:
                    targets.append(agent_components[0].get("id"))
                elif api_components:
                    targets.append(api_components[0].get("id"))
                elif output_components:
                    targets.append(output_components[0].get("id"))

                for target in targets:
                    if target and target != comp_id:
                        comp["provides"].append({
                            "useAs": "input_value" if "agent" in target else "input_value",
                            "in": target,
                            "description": f"Provides medical analysis to {target}"
                        })

            elif comp_type == "genesis:agent":
                # Agent connections: tools come TO agent, output goes FROM agent

                # Connect to output components
                if output_components:
                    for output in output_components:
                        target_id = output.get("id")
                        if target_id and target_id != comp_id:
                            comp["provides"].append({
                                "useAs": "input",
                                "in": target_id,
                                "description": f"Provides agent response to {target_id}"
                            })

            elif comp_type == "genesis:mcp_tool":
                # MCP tools provide TO agents via tools relationship
                if agent_components:
                    for agent in agent_components:
                        agent_id = agent.get("id")
                        if agent_id and agent_id != comp_id:
                            comp["provides"].append({
                                "useAs": "tools",
                                "in": agent_id,
                                "description": f"Provides tool capabilities to {agent_id}"
                            })

            elif comp_type == "genesis:prompt":
                # Prompts provide TO agents via system_prompt relationship
                if agent_components:
                    for agent in agent_components:
                        agent_id = agent.get("id")
                        if agent_id and agent_id != comp_id:
                            comp["provides"].append({
                                "useAs": "system_prompt",
                                "in": agent_id,
                                "description": f"Provides system prompt to {agent_id}"
                            })

            elif comp_type == "genesis:api_request":
                # API components typically connect to output
                if output_components:
                    target = output_components[0].get("id")
                    if target and target != comp_id:
                        comp["provides"].append({
                            "useAs": "input_value",
                            "in": target,
                            "description": f"Provides API response to {target}"
                        })

            elif comp_type == "genesis:mcp_tool":
                # MCP tools are typically used by agents (already handled above)
                # They don't usually provide to other components directly
                pass

            # Note: genesis:chat_output doesn't provide to anything (it's a sink)

        return components

    def _fix_component_structure(self, components: List[Dict]) -> None:
        """Fix component structure to match specification requirements."""
        for comp in components:
            # Add missing 'name' field if not present
            if "name" not in comp:
                comp_type = comp.get("type", "")
                if "name" in comp and comp["name"]:
                    # Keep existing name
                    pass
                elif comp_type == "genesis:chat_input":
                    comp["name"] = "User Input"
                elif comp_type == "genesis:chat_output":
                    comp["name"] = "Response Output"
                elif comp_type == "genesis:agent":
                    comp["name"] = "AI Agent"
                elif comp_type == "genesis:prompt":
                    comp["name"] = "Agent Instructions"
                elif comp_type == "genesis:mcp_tool":
                    comp["name"] = comp.get("description", "Integration Tool")
                else:
                    comp["name"] = comp.get("description", "Component")

            # Add missing 'kind' field based on component type
            if "kind" not in comp:
                comp_type = comp.get("type", "")
                if comp_type in ["genesis:chat_input", "genesis:chat_output"]:
                    comp["kind"] = "Data"
                elif comp_type == "genesis:agent":
                    comp["kind"] = "Agent"
                elif comp_type == "genesis:prompt":
                    comp["kind"] = "Prompt"
                elif comp_type == "genesis:mcp_tool":
                    comp["kind"] = "Tool"
                    # Add asTools: true for MCP tools
                    comp["asTools"] = True
                else:
                    comp["kind"] = "Data"

            # Ensure provides is initialized
            if "provides" not in comp:
                comp["provides"] = []

    def _count_connections(self, components: List[Dict]) -> int:
        """Count the total number of connections added."""
        count = 0
        for comp in components:
            count += len(comp.get("provides", []))
        return count

    def _analyze_flow(self, components: List[Dict]) -> Dict[str, Any]:
        """Analyze the flow structure and provide insights."""
        input_count = len([c for c in components if c.get("type") == "genesis:chat_input"])
        output_count = len([c for c in components if c.get("type") == "genesis:chat_output"])
        agent_count = len([c for c in components if c.get("type") == "genesis:agent"])
        model_count = len([c for c in components if c.get("type", "").startswith("genesis:") and
                          any(model in c.get("type", "") for model in ["clinical_llm", "icd10", "cpt", "rxnorm"])])

        # Check for disconnected components
        connected_components = set()
        for comp in components:
            comp_id = comp.get("id")
            if comp_id:
                connected_components.add(comp_id)
                for provide in comp.get("provides", []):
                    if "in" in provide:
                        connected_components.add(provide["in"])

        total_components = len([c for c in components if c.get("id")])
        disconnected_count = total_components - len(connected_components)

        return {
            "total_components": total_components,
            "input_components": input_count,
            "output_components": output_count,
            "agent_components": agent_count,
            "model_components": model_count,
            "connected_components": len(connected_components),
            "potentially_disconnected": disconnected_count,
            "flow_type": self._determine_flow_type(input_count, output_count, agent_count, model_count),
            "is_valid_flow": input_count >= 1 and output_count >= 1 and disconnected_count == 0
        }

    def _determine_flow_type(self, inputs: int, outputs: int, agents: int, models: int) -> str:
        """Determine the type of flow based on component counts."""
        if agents >= 1 and models >= 2:
            return "Multi-Model Healthcare Agent"
        elif agents >= 1 and models >= 1:
            return "Healthcare Agent with Medical Models"
        elif agents >= 1:
            return "Simple Agent Flow"
        elif models >= 1:
            return "Model-Based Processing"
        else:
            return "Basic Flow"
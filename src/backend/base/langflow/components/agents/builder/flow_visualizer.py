"""Flow Visualizer Component

Generates visual flow diagrams and representations of agent specifications.
Helps users understand the architecture and data flow of their agents.
"""

import json
from typing import Any, Dict, List, Optional

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Data, Text
from langflow.inputs.inputs import MessageTextInput, DictInput, DropdownInput, BoolInput
from langflow.schema.data import Data as DataType
from langflow.template.field.base import Output


class FlowVisualizerComponent(Component):
    display_name = "Flow Visualizer"
    description = "Generates visual flow diagrams and representations of agent specifications"
    documentation = "Helps users understand architecture and data flow of their agents"
    icon = "git-graph"
    name = "FlowVisualizer"

    inputs = [
        MessageTextInput(
            name="yaml_specification",
            display_name="YAML Specification",
            info="Complete YAML specification to visualize",
            required=True,
        ),
        DropdownInput(
            name="diagram_type",
            display_name="Diagram Type",
            options=["mermaid", "ascii", "json_graph", "architectural"],
            value="mermaid",
            info="Type of diagram to generate",
        ),
        BoolInput(
            name="include_details",
            display_name="Include Details",
            value=True,
            info="Whether to include component details in visualization",
        ),
    ]

    outputs = [
        Output(display_name="Flow Diagram", name="flow_diagram", method="generate_flow_diagram"),
        Output(display_name="Architecture View", name="architecture", method="create_architecture_view"),
        Output(display_name="Data Flow", name="data_flow", method="analyze_data_flow"),
        Output(display_name="Component Layout", name="layout", method="generate_layout"),
        Output(display_name="Visual Summary", name="summary", method="create_visual_summary"),
    ]

    def generate_flow_diagram(self) -> DataType:
        """Generate flow diagram in specified format"""
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            if self.diagram_type == "mermaid":
                diagram = self._generate_mermaid_diagram(spec_dict)
            elif self.diagram_type == "ascii":
                diagram = self._generate_ascii_diagram(spec_dict)
            elif self.diagram_type == "json_graph":
                diagram = self._generate_json_graph(spec_dict)
            else:  # architectural
                diagram = self._generate_architectural_diagram(spec_dict)
                
            return DataType(value={
                "diagram_type": self.diagram_type,
                "diagram_content": diagram,
                "component_count": len(spec_dict.get("components", [])),
                "visualization_notes": self._generate_visualization_notes(spec_dict),
            })
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to generate diagram: {str(e)}",
                "diagram_content": None,
            })

    def create_architecture_view(self) -> DataType:
        """Create architectural overview"""
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            architecture = self._analyze_architecture(spec_dict)
            
            return DataType(value={
                "architecture_type": architecture["type"],
                "layers": architecture["layers"],
                "patterns": architecture["patterns"],
                "complexity_analysis": architecture["complexity"],
                "scalability_notes": architecture["scalability"],
            })
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to analyze architecture: {str(e)}"
            })

    def analyze_data_flow(self) -> DataType:
        """Analyze data flow through components"""
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            data_flow = self._trace_data_flow(spec_dict)
            
            return DataType(value={
                "flow_paths": data_flow["paths"],
                "entry_points": data_flow["entry_points"],
                "exit_points": data_flow["exit_points"],
                "transformation_points": data_flow["transformations"],
                "bottlenecks": data_flow["bottlenecks"],
            })
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to analyze data flow: {str(e)}"
            })

    def generate_layout(self) -> DataType:
        """Generate component layout information"""
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            layout = self._generate_component_layout(spec_dict)
            
            return DataType(value={
                "component_positions": layout["positions"],
                "connection_routes": layout["connections"],
                "layer_organization": layout["layers"],
                "layout_recommendations": layout["recommendations"],
            })
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to generate layout: {str(e)}"
            })

    def create_visual_summary(self) -> DataType:
        """Create visual summary of the specification"""
        
        try:
            import yaml
            spec_dict = yaml.safe_load(self.yaml_specification)
            
            summary = self._create_specification_summary(spec_dict)
            
            return DataType(value=summary)
            
        except Exception as e:
            return DataType(value={
                "error": f"Failed to create summary: {str(e)}"
            })

    def _generate_mermaid_diagram(self, spec_dict: Dict[str, Any]) -> str:
        """Generate Mermaid diagram"""
        
        components = spec_dict.get("components", [])
        
        mermaid_lines = ["graph TD"]
        
        # Add nodes
        for comp in components:
            comp_id = comp.get("id", "unknown")
            comp_name = comp.get("name", comp_id)
            comp_type = comp.get("type", "")
            
            # Style based on component type
            if "input" in comp_type:
                mermaid_lines.append(f'    {comp_id}["{comp_name}"]')
                mermaid_lines.append(f'    {comp_id} --> style_{comp_id}')
                mermaid_lines.append(f'    style {comp_id} fill:#e1f5fe')
            elif "output" in comp_type:
                mermaid_lines.append(f'    {comp_id}["{comp_name}"]')
                mermaid_lines.append(f'    style {comp_id} fill:#f3e5f5')
            elif "agent" in comp_type:
                mermaid_lines.append(f'    {comp_id}["{comp_name}"]')
                mermaid_lines.append(f'    style {comp_id} fill:#fff3e0')
            else:
                mermaid_lines.append(f'    {comp_id}["{comp_name}"]')
        
        # Add connections
        for comp in components:
            comp_id = comp.get("id", "unknown")
            provides = comp.get("provides", [])
            
            for provide in provides:
                target = provide.get("in")
                relationship = provide.get("useAs", "")
                if target:
                    mermaid_lines.append(f'    {comp_id} -->|{relationship}| {target}')
        
        return "\n".join(mermaid_lines)

    def _generate_ascii_diagram(self, spec_dict: Dict[str, Any]) -> str:
        """Generate ASCII art diagram"""
        
        components = spec_dict.get("components", [])
        
        ascii_lines = []
        ascii_lines.append("Agent Flow Diagram")
        ascii_lines.append("=" * 50)
        ascii_lines.append("")
        
        # Group components by type
        input_comps = [c for c in components if "input" in c.get("type", "")]
        agent_comps = [c for c in components if "agent" in c.get("type", "")]
        tool_comps = [c for c in components if "tool" in c.get("type", "") or "mcp" in c.get("type", "")]
        output_comps = [c for c in components if "output" in c.get("type", "")]
        
        # Input layer
        if input_comps:
            ascii_lines.append("INPUT LAYER:")
            for comp in input_comps:
                ascii_lines.append(f"  📥 {comp.get('name', 'Input')}")
            ascii_lines.append("    |")
            ascii_lines.append("    v")
            ascii_lines.append("")
        
        # Agent layer
        if agent_comps:
            ascii_lines.append("PROCESSING LAYER:")
            for comp in agent_comps:
                ascii_lines.append(f"  🤖 {comp.get('name', 'Agent')}")
            if tool_comps:
                ascii_lines.append("    |")
                ascii_lines.append("    +-- TOOLS:")
                for tool in tool_comps:
                    ascii_lines.append(f"    |   🔧 {tool.get('name', 'Tool')}")
            ascii_lines.append("    |")
            ascii_lines.append("    v")
            ascii_lines.append("")
        
        # Output layer
        if output_comps:
            ascii_lines.append("OUTPUT LAYER:")
            for comp in output_comps:
                ascii_lines.append(f"  📤 {comp.get('name', 'Output')}")
        
        return "\n".join(ascii_lines)

    def _generate_json_graph(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Generate JSON graph representation"""
        
        components = spec_dict.get("components", [])
        
        nodes = []
        edges = []
        
        # Create nodes
        for comp in components:
            comp_id = comp.get("id", "unknown")
            node = {
                "id": comp_id,
                "label": comp.get("name", comp_id),
                "type": comp.get("type", ""),
                "category": self._categorize_component(comp),
                "description": comp.get("description", ""),
            }
            
            if self.include_details:
                node["config"] = comp.get("config", {})
            
            nodes.append(node)
        
        # Create edges
        for comp in components:
            comp_id = comp.get("id", "unknown")
            provides = comp.get("provides", [])
            
            for provide in provides:
                target = provide.get("in")
                if target:
                    edge = {
                        "source": comp_id,
                        "target": target,
                        "relationship": provide.get("useAs", ""),
                        "description": provide.get("description", ""),
                    }
                    edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "agent_name": spec_dict.get("name", "Unknown Agent"),
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            }
        }

    def _generate_architectural_diagram(self, spec_dict: Dict[str, Any]) -> str:
        """Generate architectural text diagram"""
        
        lines = []
        lines.append(f"Architecture: {spec_dict.get('name', 'Agent')}")
        lines.append("=" * 60)
        lines.append("")
        
        # Agent kind and characteristics
        kind = spec_dict.get("kind", "Unknown")
        lines.append(f"Type: {kind}")
        lines.append(f"Domain: {spec_dict.get('subDomain', 'general')}")
        lines.append(f"Goal: {spec_dict.get('agentGoal', 'Not specified')}")
        lines.append("")
        
        # Component architecture
        components = spec_dict.get("components", [])
        architecture = self._analyze_architecture(spec_dict)
        
        lines.append("ARCHITECTURAL LAYERS:")
        for layer_name, layer_comps in architecture["layers"].items():
            if layer_comps:
                lines.append(f"\n{layer_name.upper()}:")
                for comp_name in layer_comps:
                    lines.append(f"  • {comp_name}")
        
        # Patterns used
        lines.append("\nPATTERNS IDENTIFIED:")
        for pattern in architecture["patterns"]:
            lines.append(f"  • {pattern}")
        
        return "\n".join(lines)

    def _categorize_component(self, component: Dict[str, Any]) -> str:
        """Categorize component for visualization"""
        
        comp_type = component.get("type", "")
        
        if "input" in comp_type:
            return "input"
        elif "output" in comp_type:
            return "output"
        elif "agent" in comp_type:
            return "agent"
        elif "tool" in comp_type or "mcp" in comp_type:
            return "tool"
        elif "crew" in comp_type or "task" in comp_type:
            return "coordination"
        elif "prompt" in comp_type:
            return "prompt"
        elif "memory" in comp_type.lower():
            return "memory"
        else:
            return "other"

    def _analyze_architecture(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze architectural characteristics"""
        
        components = spec_dict.get("components", [])
        kind = spec_dict.get("kind", "")
        
        # Determine architecture type
        arch_type = "Single Agent Pipeline"
        if "Multi Agent" in kind:
            arch_type = "Multi-Agent Workflow"
        elif len([c for c in components if "crew" in c.get("type", "")]) > 0:
            arch_type = "CrewAI Orchestrated Workflow"
        
        # Organize into layers
        layers = {
            "input_layer": [],
            "processing_layer": [],
            "tool_layer": [],
            "coordination_layer": [],
            "output_layer": [],
        }
        
        for comp in components:
            comp_name = comp.get("name", comp.get("id", "Unknown"))
            category = self._categorize_component(comp)
            
            if category == "input":
                layers["input_layer"].append(comp_name)
            elif category == "output":
                layers["output_layer"].append(comp_name)
            elif category == "agent":
                layers["processing_layer"].append(comp_name)
            elif category == "tool":
                layers["tool_layer"].append(comp_name)
            elif category == "coordination":
                layers["coordination_layer"].append(comp_name)
        
        # Identify patterns
        patterns = []
        if len(layers["processing_layer"]) > 1:
            patterns.append("Multi-Agent Processing")
        if layers["coordination_layer"]:
            patterns.append("Workflow Orchestration")
        if len(layers["tool_layer"]) > 2:
            patterns.append("Tool-Rich Integration")
        if not patterns:
            patterns.append("Simple Linear Processing")
        
        # Assess complexity
        total_comps = len(components)
        if total_comps > 15:
            complexity = "Enterprise"
        elif total_comps > 10:
            complexity = "Advanced"
        elif total_comps > 6:
            complexity = "Intermediate"
        else:
            complexity = "Simple"
        
        return {
            "type": arch_type,
            "layers": layers,
            "patterns": patterns,
            "complexity": complexity,
            "scalability": self._assess_scalability(components),
        }

    def _assess_scalability(self, components: List[Dict[str, Any]]) -> List[str]:
        """Assess scalability characteristics"""
        
        scalability_notes = []
        
        agent_count = len([c for c in components if "agent" in c.get("type", "")])
        tool_count = len([c for c in components if "tool" in c.get("type", "") or "mcp" in c.get("type", "")])
        
        if agent_count > 1:
            scalability_notes.append("Horizontal scaling possible with multiple agents")
        
        if tool_count > 3:
            scalability_notes.append("High integration complexity may impact scaling")
        
        if any("crew" in c.get("type", "") for c in components):
            scalability_notes.append("CrewAI coordination enables distributed processing")
        
        if not scalability_notes:
            scalability_notes.append("Simple architecture scales vertically")
        
        return scalability_notes

    def _trace_data_flow(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Trace data flow through components"""
        
        components = spec_dict.get("components", [])
        
        # Build component map
        comp_map = {comp.get("id"): comp for comp in components}
        
        # Find entry and exit points
        entry_points = []
        exit_points = []
        
        for comp in components:
            comp_type = comp.get("type", "")
            if "input" in comp_type:
                entry_points.append(comp.get("name", comp.get("id")))
            elif "output" in comp_type:
                exit_points.append(comp.get("name", comp.get("id")))
        
        # Trace flow paths
        flow_paths = []
        for comp in components:
            provides = comp.get("provides", [])
            for provide in provides:
                source = comp.get("name", comp.get("id"))
                target_id = provide.get("in")
                target_comp = comp_map.get(target_id)
                target = target_comp.get("name", target_id) if target_comp else target_id
                relationship = provide.get("useAs", "data")
                
                flow_paths.append({
                    "from": source,
                    "to": target,
                    "type": relationship,
                    "description": provide.get("description", "")
                })
        
        # Identify transformation points
        transformations = []
        for comp in components:
            if "agent" in comp.get("type", ""):
                transformations.append({
                    "component": comp.get("name", comp.get("id")),
                    "type": "LLM Processing",
                    "description": "Transforms input through language model processing"
                })
            elif "tool" in comp.get("type", ""):
                transformations.append({
                    "component": comp.get("name", comp.get("id")),
                    "type": "External Integration",
                    "description": "Transforms data through external service call"
                })
        
        # Identify potential bottlenecks
        bottlenecks = []
        agent_components = [c for c in components if "agent" in c.get("type", "")]
        if len(agent_components) == 1 and len(components) > 5:
            bottlenecks.append("Single agent processing multiple tools may become bottleneck")
        
        return {
            "paths": flow_paths,
            "entry_points": entry_points,
            "exit_points": exit_points,
            "transformations": transformations,
            "bottlenecks": bottlenecks,
        }

    def _generate_component_layout(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Generate component layout suggestions"""
        
        components = spec_dict.get("components", [])
        
        # Calculate positions based on component relationships
        positions = {}
        layer_y = 0
        
        # Input components at top
        input_comps = [c for c in components if "input" in c.get("type", "")]
        for i, comp in enumerate(input_comps):
            positions[comp.get("id")] = {"x": i * 200, "y": layer_y, "layer": "input"}
        
        # Agent components in middle
        layer_y += 150
        agent_comps = [c for c in components if "agent" in c.get("type", "")]
        for i, comp in enumerate(agent_comps):
            positions[comp.get("id")] = {"x": i * 200, "y": layer_y, "layer": "processing"}
        
        # Tool components on the side
        tool_comps = [c for c in components if "tool" in c.get("type", "") or "mcp" in c.get("type", "")]
        for i, comp in enumerate(tool_comps):
            positions[comp.get("id")] = {"x": 400 + (i * 150), "y": layer_y, "layer": "tools"}
        
        # Output components at bottom
        layer_y += 150
        output_comps = [c for c in components if "output" in c.get("type", "")]
        for i, comp in enumerate(output_comps):
            positions[comp.get("id")] = {"x": i * 200, "y": layer_y, "layer": "output"}
        
        # Generate connection routes
        connections = []
        for comp in components:
            provides = comp.get("provides", [])
            for provide in provides:
                source_id = comp.get("id")
                target_id = provide.get("in")
                if source_id in positions and target_id in positions:
                    connections.append({
                        "from": source_id,
                        "to": target_id,
                        "type": provide.get("useAs", "data")
                    })
        
        return {
            "positions": positions,
            "connections": connections,
            "layers": {
                "input": 0,
                "processing": 150,
                "tools": 150,
                "output": 300
            },
            "recommendations": [
                "Place input components at the top",
                "Center processing agents in the middle",
                "Position tools to the right of agents",
                "Place output components at the bottom"
            ]
        }

    def _generate_visualization_notes(self, spec_dict: Dict[str, Any]) -> List[str]:
        """Generate notes about the visualization"""
        
        notes = []
        components = spec_dict.get("components", [])
        
        total_comps = len(components)
        notes.append(f"Total components: {total_comps}")
        
        agent_count = len([c for c in components if "agent" in c.get("type", "")])
        if agent_count > 1:
            notes.append(f"Multi-agent workflow with {agent_count} agents")
        
        tool_count = len([c for c in components if "tool" in c.get("type", "") or "mcp" in c.get("type", "")])
        if tool_count > 0:
            notes.append(f"Integrates with {tool_count} external tools")
        
        if any("crew" in c.get("type", "") for c in components):
            notes.append("Uses CrewAI for workflow coordination")
        
        return notes

    def _create_specification_summary(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Create visual summary of specification"""
        
        components = spec_dict.get("components", [])
        
        # Component statistics
        component_stats = {}
        for comp in components:
            category = self._categorize_component(comp)
            component_stats[category] = component_stats.get(category, 0) + 1
        
        # Complexity assessment
        total_comps = len(components)
        complexity = "Simple"
        if total_comps > 15:
            complexity = "Enterprise"
        elif total_comps > 10:
            complexity = "Advanced"
        elif total_comps > 6:
            complexity = "Intermediate"
        
        return {
            "agent_overview": {
                "name": spec_dict.get("name", "Unknown Agent"),
                "kind": spec_dict.get("kind", "Unknown"),
                "domain": spec_dict.get("subDomain", "general"),
                "complexity": complexity,
            },
            "component_breakdown": component_stats,
            "architecture_summary": self._analyze_architecture(spec_dict),
            "integration_summary": {
                "external_tools": component_stats.get("tool", 0),
                "coordination_components": component_stats.get("coordination", 0),
                "processing_agents": component_stats.get("agent", 0),
            },
            "visual_complexity": {
                "total_components": total_comps,
                "connection_count": self._count_connections(components),
                "layer_count": len([layer for layer, comps in self._analyze_architecture(spec_dict)["layers"].items() if comps]),
            }
        }

    def _count_connections(self, components: List[Dict[str, Any]]) -> int:
        """Count total connections between components"""
        
        connection_count = 0
        for comp in components:
            provides = comp.get("provides", [])
            connection_count += len(provides)
        
        return connection_count
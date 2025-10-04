# Path: src/backend/base/langflow/services/specification/converter.py

import json
import copy
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from langflow.services.specification.models import (
    ComponentSpec,
    ConversionResult,
    ConversionStrategy,
    EnhancedAgentSpec,
    EnhancedKPI,
    SecurityInfo,
    VariableDefinition,
)
from langflow.services.specification.dynamic_component_mapper import get_dynamic_mapper, get_langflow_component_type


class FlowStructureAnalyzer:
    """Analyzes Langflow flows to extract specification elements"""

    def __init__(self):
        # Mapping of Langflow node types to specification components
        self.node_type_mapping = {
            "ChatOpenAI": {"type": "llm_provider", "model": "gpt-3.5-turbo"},
            "ChatAnthropic": {"type": "llm_provider", "model": "claude-3"},
            "ChatOllama": {"type": "llm_provider", "model": "ollama"},
            "Agent": {"type": "agent_core"},
            "APIChain": {"type": "tool", "category": "api"},
            "PythonFunction": {"type": "tool", "category": "custom"},
            "VectorStore": {"type": "knowledge", "category": "vector_db"},
            "TextInput": {"type": "input", "data_type": "string"},
            "NumberInput": {"type": "input", "data_type": "number"},
            "BooleanInput": {"type": "input", "data_type": "boolean"},
            "Output": {"type": "output"},
            "ChatInput": {"type": "genesis:chat_input"},
            "ChatOutput": {"type": "genesis:chat_output"},
        }

    def analyze_flow(self, flow: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specification elements from flow structure"""
        if not flow.get("data"):
            return {"error": "Invalid flow structure"}

        nodes = flow["data"].get("nodes", [])
        edges = flow["data"].get("edges", [])

        analysis = {
            "models": self._extract_models(nodes),
            "tools": self._extract_tools(nodes),
            "variables": self._extract_variables(nodes),
            "inputs": self._extract_inputs(nodes),
            "outputs": self._extract_outputs(nodes),
            "flow_complexity": self._calculate_complexity(nodes, edges),
            "estimated_kpis": self._estimate_kpis(nodes, edges),
            "components": self._extract_components(nodes),
            "workflow_type": self._detect_workflow_type(nodes, edges),
        }

        return analysis

    def _extract_models(self, nodes: List[Dict]) -> List[Dict]:
        """Extract LLM model configurations"""
        models = []
        for node in nodes:
            node_type = node.get("type", "")
            if node_type in ["ChatOpenAI", "ChatAnthropic", "ChatOllama"]:
                template = node.get("data", {}).get("node", {}).get("template", {})
                model_config = {
                    "provider": self._map_provider(node_type),
                    "model": template.get("model_name", {}).get("value", "unknown"),
                    "temperature": template.get("temperature", {}).get("value", 0.7),
                    "max_tokens": template.get("max_tokens", {}).get("value", 1000),
                }
                models.append(model_config)
        return models

    def _extract_tools(self, nodes: List[Dict]) -> List[Dict]:
        """Extract tool configurations"""
        tools = []
        for node in nodes:
            node_type = node.get("type", "")
            if node_type in ["APIChain", "PythonFunction", "WebSearchTool"]:
                tool_config = {
                    "type": self._map_tool_type(node_type),
                    "name": node.get("data", {}).get("node", {}).get("display_name", "unknown"),
                    "description": node.get("data", {}).get("node", {}).get("description", ""),
                    "parameters": self._extract_tool_parameters(node),
                }
                tools.append(tool_config)
        return tools

    def _extract_variables(self, nodes: List[Dict]) -> List[Dict]:
        """Extract input variables from input nodes"""
        variables = []
        for node in nodes:
            if node.get("type") in ["TextInput", "NumberInput", "BooleanInput"]:
                template = node.get("data", {}).get("node", {}).get("template", {})
                variable = {
                    "name": template.get("input_value", {}).get("name", "unknown"),
                    "type": self._map_input_type(node.get("type")),
                    "description": template.get("input_value", {}).get("description", ""),
                    "required": template.get("input_value", {}).get("required", False),
                    "default": template.get("input_value", {}).get("value"),
                }
                variables.append(variable)
        return variables

    def _extract_inputs(self, nodes: List[Dict]) -> List[Dict]:
        """Extract input nodes"""
        inputs = []
        for node in nodes:
            if node.get("type") in ["ChatInput", "TextInput", "NumberInput"]:
                inputs.append({
                    "id": node.get("id"),
                    "type": node.get("type"),
                    "name": node.get("data", {}).get("node", {}).get("display_name", "Input"),
                })
        return inputs

    def _extract_outputs(self, nodes: List[Dict]) -> List[Dict]:
        """Extract output nodes"""
        outputs = []
        for node in nodes:
            if node.get("type") in ["ChatOutput", "Output"]:
                outputs.append({
                    "id": node.get("id"),
                    "type": node.get("type"),
                    "name": node.get("data", {}).get("node", {}).get("display_name", "Output"),
                })
        return outputs

    def _extract_components(self, nodes: List[Dict]) -> List[Dict]:
        """Extract components in specification format"""
        components = []
        for node in nodes:
            node_type = node.get("type", "")
            node_data = node.get("data", {}).get("node", {})

            # Map to Genesis component type
            genesis_type = self._map_to_genesis_type(node_type)

            component = {
                "id": node.get("id", str(uuid4())),
                "name": node_data.get("display_name", node_type),
                "type": genesis_type,
                "description": node_data.get("description", ""),
                "config": self._extract_node_config(node),
            }

            components.append(component)

        return components

    def _calculate_complexity(self, nodes: List[Dict], edges: List[Dict]) -> Dict:
        """Calculate flow complexity metrics"""
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "max_depth": self._calculate_max_depth(nodes, edges),
            "branching_factor": len(edges) / max(len(nodes) - 1, 1) if len(nodes) > 1 else 0,
            "has_loops": self._detect_loops(nodes, edges),
        }

    def _estimate_kpis(self, nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
        """Generate estimated KPIs based on flow structure"""
        kpis = [
            {
                "name": "Response Time",
                "description": "Average response time for agent execution",
                "category": "Performance",
                "value_type": "duration",
                "target": "< 5 seconds",
                "unit": "seconds",
            },
            {
                "name": "Success Rate",
                "description": "Percentage of successful executions",
                "category": "Quality",
                "value_type": "percentage",
                "target": "> 95%",
                "unit": "percent",
            },
        ]

        # Add tool-specific KPIs
        tool_nodes = [n for n in nodes if n.get("type") in ["APIChain", "PythonFunction"]]
        if tool_nodes:
            kpis.append({
                "name": "Tool Success Rate",
                "description": "Success rate of tool executions",
                "category": "Performance",
                "value_type": "percentage",
                "target": "> 90%",
                "unit": "percent",
            })

        return kpis

    def _detect_workflow_type(self, nodes: List[Dict], edges: List[Dict]) -> str:
        """Detect the type of workflow"""
        # Simple heuristics
        if len(nodes) <= 3:
            return "simple"
        elif any(n.get("type") == "Agent" for n in nodes):
            return "agent_based"
        elif len([n for n in nodes if n.get("type") in ["APIChain", "PythonFunction"]]) > 2:
            return "tool_heavy"
        else:
            return "complex"

    def _map_provider(self, node_type: str) -> str:
        mapping = {
            "ChatOpenAI": "OpenAI",
            "ChatAnthropic": "Anthropic",
            "ChatOllama": "Ollama",
        }
        return mapping.get(node_type, "Unknown")

    def _map_tool_type(self, node_type: str) -> str:
        mapping = {
            "APIChain": "api_tool",
            "PythonFunction": "python_function",
            "WebSearchTool": "web_search",
        }
        return mapping.get(node_type, "custom_tool")

    def _map_input_type(self, node_type: str) -> str:
        mapping = {
            "TextInput": "string",
            "NumberInput": "number",
            "BooleanInput": "boolean",
        }
        return mapping.get(node_type, "string")

    def _map_to_genesis_type(self, node_type: str) -> str:
        """Map Langflow node type to Genesis component type"""
        mapping = {
            "ChatInput": "genesis:chat_input",
            "ChatOutput": "genesis:chat_output",
            "Agent": "genesis:agent",
            "ChatOpenAI": "genesis:llm_openai",
            "ChatAnthropic": "genesis:llm_anthropic",
            "APIChain": "genesis:api_component",
            "PythonFunction": "genesis:python_function",
            "TextInput": "genesis:text_input",
            "NumberInput": "genesis:number_input",
        }
        return mapping.get(node_type, f"genesis:{node_type.lower()}")

    def _extract_node_config(self, node: Dict) -> Dict:
        """Extract configuration from a node"""
        template = node.get("data", {}).get("node", {}).get("template", {})
        config = {}

        for key, value in template.items():
            if isinstance(value, dict) and "value" in value:
                config[key] = value["value"]

        return config

    def _extract_tool_parameters(self, node: Dict) -> Dict:
        """Extract tool parameters from node"""
        return self._extract_node_config(node)

    def _calculate_max_depth(self, nodes: List[Dict], edges: List[Dict]) -> int:
        """Calculate maximum depth of the flow"""
        # Simplified calculation
        return min(len(nodes), 10)  # Cap at 10 for simplicity

    def _detect_loops(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """Detect if there are loops in the flow"""
        # Simplified detection
        node_ids = {node["id"] for node in nodes}
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source == target:
                return True
        return False


class EnhancedBidirectionalConverter:
    """Advanced converter supporting multiple conversion strategies"""

    def __init__(self):
        self.analyzer = FlowStructureAnalyzer()

    async def flow_to_spec(self, flow: Dict[str, Any]) -> ConversionResult:
        """Convert flow to specification using best available method"""

        # Detect conversion strategy
        strategy = self._detect_conversion_strategy(flow)

        if strategy.strategy_type == "metadata_restoration":
            return self._restore_from_metadata(flow, strategy)
        elif strategy.strategy_type == "hybrid":
            return self._hybrid_conversion(flow, strategy)
        else:  # reverse_engineering
            return self._infer_from_structure(flow, strategy)

    def _detect_conversion_strategy(self, flow: Dict) -> ConversionStrategy:
        """Determine best conversion approach based on flow metadata"""

        metadata = flow.get("data", {}).get("metadata", {})
        genesis_spec = metadata.get("genesis_spec", {})

        if genesis_spec and "original_yaml" in genesis_spec:
            return ConversionStrategy(
                strategy_type="metadata_restoration",
                confidence_score=0.95,
                available_metadata=genesis_spec,
                detected_patterns=["embedded_specification"],
            )
        elif genesis_spec:
            return ConversionStrategy(
                strategy_type="hybrid",
                confidence_score=0.75,
                available_metadata=genesis_spec,
                detected_patterns=["partial_metadata"],
            )
        else:
            # Analyze flow structure for patterns
            analysis = self.analyzer.analyze_flow(flow)
            patterns = self._detect_patterns(analysis)

            return ConversionStrategy(
                strategy_type="reverse_engineering",
                confidence_score=0.6,
                available_metadata={},
                detected_patterns=patterns,
            )

    def _restore_from_metadata(self, flow: Dict, strategy: ConversionStrategy) -> ConversionResult:
        """Restore specification from embedded metadata"""

        try:
            genesis_spec = strategy.available_metadata
            original_yaml = genesis_spec.get("original_yaml")

            if original_yaml:
                # Perfect restoration from original YAML
                spec = EnhancedAgentSpec.from_yaml(original_yaml)
                return ConversionResult(
                    success=True,
                    specification=spec,
                    strategy_used=strategy,
                    warnings=[],
                    errors=[],
                )
            else:
                # Partial restoration from metadata fields
                spec = EnhancedAgentSpec(**genesis_spec)
                return ConversionResult(
                    success=True,
                    specification=spec,
                    strategy_used=strategy,
                    warnings=["Restored from partial metadata"],
                    errors=[],
                )

        except Exception as e:
            return ConversionResult(
                success=False,
                specification=None,
                strategy_used=strategy,
                warnings=[],
                errors=[f"Failed to restore from metadata: {str(e)}"],
            )

    def _hybrid_conversion(self, flow: Dict, strategy: ConversionStrategy) -> ConversionResult:
        """Hybrid approach combining metadata with flow analysis"""

        warnings = []
        errors = []

        try:
            # Start with available metadata
            genesis_spec = strategy.available_metadata

            # Analyze flow structure for missing parts
            analysis = self.analyzer.analyze_flow(flow)

            # Build specification combining both sources
            spec_data = {
                "id": genesis_spec.get("id", f"urn:agent:genesis:imported:{flow.get('name', 'unknown')}:1"),
                "name": genesis_spec.get("name", flow.get("name", "Imported Agent")),
                "description": genesis_spec.get("description", flow.get("description", "Auto-generated from Langflow flow")),
                "version": genesis_spec.get("version", "1.0.0"),
                "domain": genesis_spec.get("domain", "imported"),
                "owner": genesis_spec.get("owner", "unknown@genesis.ai"),
                "goal": genesis_spec.get("goal", self._extract_goal(analysis)),
                "value_generation": genesis_spec.get("value_generation", "ProcessAutomation"),
                "interaction_mode": genesis_spec.get("interaction_mode", "RequestResponse"),
                "run_mode": genesis_spec.get("run_mode", "RealTime"),
                "agency_level": genesis_spec.get("agency_level", "ModelDrivenWorkflow"),
                "components": self._convert_analysis_to_components(analysis),
                "variables": self._convert_variables(analysis.get("variables", [])),
                "kpis": self._convert_kpis(analysis.get("estimated_kpis", [])),
                "tags": genesis_spec.get("tags", ["imported", "hybrid"]),
            }

            spec = EnhancedAgentSpec(**spec_data)

            return ConversionResult(
                success=True,
                specification=spec,
                strategy_used=strategy,
                warnings=warnings,
                errors=errors,
            )

        except Exception as e:
            errors.append(f"Hybrid conversion failed: {str(e)}")
            return ConversionResult(
                success=False,
                specification=None,
                strategy_used=strategy,
                warnings=warnings,
                errors=errors,
            )

    def _infer_from_structure(self, flow: Dict, strategy: ConversionStrategy) -> ConversionResult:
        """Infer specification from flow structure (reverse engineering)"""

        warnings = ["Generated via reverse engineering", "Accuracy may vary"]
        errors = []

        try:
            analysis = self.analyzer.analyze_flow(flow)

            # Find primary agent node for goal extraction
            agent_goal = self._extract_goal(analysis)

            # Build specification from analysis
            spec_data = {
                "id": f"urn:agent:genesis:imported:{self._sanitize_name(flow.get('name', 'unknown'))}:1",
                "name": flow.get("name", "Imported Agent"),
                "description": flow.get("description", "Auto-generated from Langflow flow"),
                "version": "1.0.0",
                "domain": "imported",
                "owner": "unknown@genesis.ai",
                "goal": agent_goal,
                "value_generation": "ProcessAutomation",  # Default assumption
                "interaction_mode": "RequestResponse",  # Default assumption
                "run_mode": "RealTime",  # Default assumption
                "agency_level": "ModelDrivenWorkflow",  # Default assumption
                "components": self._convert_analysis_to_components(analysis),
                "variables": self._convert_variables(analysis.get("variables", [])),
                "kpis": self._convert_kpis(analysis.get("estimated_kpis", [])),
                "tags": ["imported", "auto-generated"],
                "security_info": SecurityInfo(
                    confidence=strategy.confidence_score,
                    source="langflow_reverse_engineering",
                    analysis_metadata=analysis,
                ),
            }

            spec = EnhancedAgentSpec(**spec_data)

            return ConversionResult(
                success=True,
                specification=spec,
                strategy_used=strategy,
                warnings=warnings,
                errors=errors,
            )

        except Exception as e:
            errors.append(f"Reverse engineering failed: {str(e)}")
            return ConversionResult(
                success=False,
                specification=None,
                strategy_used=strategy,
                warnings=warnings,
                errors=errors,
            )

    async def spec_to_flow(self, spec: EnhancedAgentSpec) -> Dict[str, Any]:
        """Convert Agent Specification to Langflow Flow with embedded metadata"""

        # Initialize dynamic mapper if not already done
        if not hasattr(self, 'dynamic_mapper') or not self.dynamic_mapper:
            self.dynamic_mapper = await get_dynamic_mapper()

        # Build nodes and edges
        nodes = await self._build_nodes(spec)
        edges = await self._build_edges(spec, nodes)

        # Create flow structure
        flow = {
            "data": {
                "nodes": nodes,
                "edges": edges,
                "viewport": {"x": 0, "y": 0, "zoom": 0.5}
            },
            "name": getattr(spec, "name", "Untitled Flow"),
            "description": getattr(spec, "description", ""),
            "is_component": False,
            "updated_at": datetime.utcnow().isoformat(),
            "folder": None,
            "id": None,
            "user_id": None,
            "webhook": False,
            "endpoint_name": None
        }

        # Add metadata for enhanced specs
        if hasattr(spec, 'goal'):
            flow["metadata"] = {
                "agentGoal": getattr(spec, "goal", ""),
                "targetUser": getattr(spec, "target_user", ""),
                "valueGeneration": getattr(spec, "value_generation", ""),
                "kind": getattr(spec, "kind", ""),
                "tags": getattr(spec, "tags", []),
                "kpis": [kpi.dict() if hasattr(kpi, 'dict') else kpi for kpi in getattr(spec, "kpis", [])]
            }

        return flow

    async def _build_nodes(self, spec: Any) -> List[Dict[str, Any]]:
        """Build nodes from specification components."""
        nodes = []

        # Extract components
        components = []
        if hasattr(spec, "components"):
            components = spec.components
        elif isinstance(spec, dict) and "components" in spec:
            components = spec["components"]

        # Build each component as a node
        for i, component in enumerate(components):
            node = await self._build_node(component, i)
            if node:
                nodes.append(node)

        return nodes

    async def _build_node(self, component: Union[Dict[str, Any], ComponentSpec], index: int) -> Optional[Dict[str, Any]]:
        """Build a single node from component specification."""
        # Handle both dict and ComponentSpec objects
        if hasattr(component, 'id'):
            comp_id = component.id
            comp_type = component.type
            comp_name = getattr(component, 'name', comp_id)
            comp_description = getattr(component, 'description', '')
            comp_config = getattr(component, 'config', {})
        else:
            comp_id = component.get("id", f"node-{uuid.uuid4().hex[:8]}")
            comp_type = component.get("type", "")
            comp_name = component.get("name", comp_id)
            comp_description = component.get("description", "")
            comp_config = component.get("config", {})

        # Map Genesis type to actual Genesis Studio component type
        if self.dynamic_mapper:
            langflow_type = self.dynamic_mapper.get_component_type(comp_type)
        else:
            langflow_type = get_langflow_component_type(comp_type)

        # Get raw component data from dynamic mapper
        comp_data = None
        if hasattr(self.dynamic_mapper, '_components_cache') and self.dynamic_mapper._components_cache:
            # Find the component in the cache
            for category, components in self.dynamic_mapper._components_cache.items():
                if isinstance(components, dict) and langflow_type in components:
                    comp_data = components[langflow_type]
                    break

        if not comp_data:
            print(f"⚠️  Component '{langflow_type}' not found in Genesis Studio, skipping")
            return None

        # Get category from the component's location in cache
        category = "custom"
        for cat, components in self.dynamic_mapper._components_cache.items():
            if isinstance(components, dict) and langflow_type in components:
                category = cat
                break

        # Calculate position
        position = self._calculate_position(index, category)

        # Check if this component is used as a tool
        is_tool = self._is_component_used_as_tool(component)

        # Deep copy component data to avoid modifying the cached version
        node_data = copy.deepcopy(comp_data)

        # Handle tool mode
        if is_tool:
            # Set tool mode
            node_data["tool_mode"] = True

            # Ensure we have the component_as_tool output
            if "outputs" in node_data:
                # Check if component_as_tool already exists
                has_tool_output = any(o.get("name") == "component_as_tool" for o in node_data["outputs"])

                if not has_tool_output:
                    # Add component_as_tool output
                    node_data["outputs"] = [{
                        "types": ["Tool"],
                        "selected": "Tool",
                        "name": "component_as_tool",
                        "display_name": "Toolset",
                        "method": "to_toolkit",
                        "value": "__UNDEFINED__",
                        "cache": True,
                        "allows_loop": False,
                        "tool_mode": True
                    }]

        # Build node structure using component data
        node = {
            "id": comp_id,
            "type": "genericNode",
            "position": position,
            "data": {
                "id": comp_id,
                "type": langflow_type,  # Use actual component type name
                "description": comp_description or node_data.get("description", ""),
                "display_name": comp_name,
                "node": node_data,  # Use the modified component data
                "outputs": node_data.get("outputs", [])
            },
            "dragging": False,
            "height": self._get_node_height(category),
            "selected": False,
            "positionAbsolute": position,
            "width": 384
        }

        # Update template with component config
        if "template" in node["data"]["node"] and comp_config:
            self._apply_config_to_template(node["data"]["node"]["template"], comp_config)

        return node

    async def _build_edges(self, spec: Any, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build edges from provides declarations."""
        edges = []
        node_map = {node["id"]: node for node in nodes}

        # Extract components with provides
        components = []
        if hasattr(spec, "components"):
            components = spec.components
        elif isinstance(spec, dict) and "components" in spec:
            components = spec["components"]

        # Process each component's provides declarations
        for component in components:
            # Handle both dict and ComponentSpec objects
            if hasattr(component, 'provides'):
                provides_list = component.provides
                source_id = component.id
            else:
                provides_list = component.get("provides", [])
                source_id = component.get("id")

            if not provides_list or not source_id:
                continue

            if source_id not in node_map:
                continue

            # Process each provides declaration
            for provide in provides_list:
                edge = self._create_edge_from_provides(
                    source_id,
                    provide,
                    node_map,
                    component
                )
                if edge:
                    edges.append(edge)

        return edges

    def _calculate_position(self, index: int, category: str) -> Dict[str, float]:
        """Calculate node position based on index and category."""
        # Basic grid layout
        row = index // 3
        col = index % 3
        return {
            "x": 100 + (col * 300),
            "y": 100 + (row * 200)
        }

    def _get_node_height(self, category: str) -> int:
        """Get node height based on category."""
        category_heights = {
            "agents": 350,
            "models": 300,
            "inputs": 250,
            "outputs": 250,
            "tools": 300,
            "custom": 267
        }
        return category_heights.get(category, 267)

    def _is_component_used_as_tool(self, component: Union[Dict[str, Any], ComponentSpec]) -> bool:
        """Check if component is used as a tool in other components."""
        # This would need more sophisticated analysis
        # For now, return False as a placeholder
        return False

    def _apply_config_to_template(self, template: Dict[str, Any], config: Dict[str, Any]):
        """Apply component config values to the template."""
        for key, value in config.items():
            if key in template and isinstance(template[key], dict):
                template[key]["value"] = value

    def _create_edge_from_provides(
        self,
        source_id: str,
        provide: Dict[str, Any],
        node_map: Dict[str, Dict[str, Any]],
        source_component: Union[Dict[str, Any], ComponentSpec]
    ) -> Optional[Dict[str, Any]]:
        """Create an edge from a provides declaration."""
        # Get target info
        if hasattr(provide, 'get'):
            target_id = provide.get("in")
            use_as = provide.get("use_as") or provide.get("useAs")
        else:
            target_id = getattr(provide, 'in', None)
            use_as = getattr(provide, 'use_as', None) or getattr(provide, 'useAs', None)

        if not target_id or not use_as:
            return None

        if target_id not in node_map:
            print(f"⚠️  Target node '{target_id}' not found for provides connection")
            return None

        # Get nodes
        source_node = node_map[source_id]
        target_node = node_map[target_id]

        # Get actual component types
        source_type = source_node["data"]["type"]
        target_type = target_node["data"]["type"]

        # Determine output field based on useAs and component outputs
        output_field = self._determine_output_field(use_as, source_node, source_type)

        # Determine input field
        input_field = self._map_use_as_to_field(use_as)

        # Determine output types based on the output field
        output_types = self._get_output_types(source_node, output_field)

        # Create handle objects
        source_handle = {
            "dataType": source_type,  # Use actual component type
            "id": source_id,
            "name": output_field,
            "output_types": output_types
        }

        # Determine input types based on the field
        input_types = self._get_input_types(target_node, input_field)

        # Validate type compatibility
        if not self._validate_type_compatibility(output_types, input_types, source_type, target_type):
            print(f"⚠️  Type mismatch: {source_type} outputs {output_types} but {target_type}.{input_field} expects {input_types}")
            print(f"   Consider using a different output component that accepts {output_types[0] if output_types else 'the output type'}")
            return None

        # Determine handle type based on Genesis Studio conventions
        handle_type = self._determine_handle_type(input_field, input_types)

        target_handle = {
            "fieldName": input_field,
            "id": target_id,
            "inputTypes": input_types,
            "type": handle_type
        }

        # Encode handles
        source_handle_encoded = json.dumps(source_handle, separators=(",", ":")).replace('"', "œ")
        target_handle_encoded = json.dumps(target_handle, separators=(",", ":")).replace('"', "œ")

        # Create edge
        edge = {
            "className": "",
            "data": {
                "sourceHandle": source_handle,
                "targetHandle": target_handle,
                "label": getattr(provide, 'description', '') if hasattr(provide, 'description') else provide.get('description', '')
            },
            "id": f"reactflow__edge-{source_id}{source_handle_encoded}-{target_id}{target_handle_encoded}",
            "selected": False,
            "source": source_id,
            "sourceHandle": source_handle_encoded,
            "target": target_id,
            "targetHandle": target_handle_encoded
        }

        return edge

    def _determine_output_field(self, use_as: str, source_node: Dict[str, Any], source_type: str) -> str:
        """Determine the output field based on useAs type and component."""
        # Special case for tools - they use component_as_tool
        if use_as in ["tool", "tools"]:
            return "component_as_tool"

        # Check if node has outputs defined
        outputs = source_node.get("data", {}).get("outputs", [])
        if outputs:
            # For agents, typically use "response"
            if "Agent" in source_type and any(o.get("name") == "response" for o in outputs):
                return "response"
            # For prompts, typically use "prompt"
            elif "Prompt" in source_type and any(o.get("name") == "prompt" for o in outputs):
                return "prompt"
            # Otherwise use first output
            return outputs[0].get("name", "output")

        # Default mappings
        output_mappings = {
            "input": "message",
            "tool": "component_as_tool",
            "tools": "component_as_tool",
            "system_prompt": "prompt",
            "prompt": "prompt",
            "llm": "text_output",
            "response": "response",
            "message": "message",
            "text": "text",
            "output": "output"
        }

        return output_mappings.get(use_as, "output")

    def _map_use_as_to_field(self, use_as: str) -> str:
        """Map useAs to input field name."""
        field_mappings = {
            "input": "input_value",
            "message": "input_value",
            "text": "input_value",
            "tool": "tools",
            "tools": "tools",
            "system_prompt": "system_prompt",
            "prompt": "prompt",
            "llm": "llm",
            "memory": "memory",
            "response": "input_value"
        }
        return field_mappings.get(use_as, "input_value")

    def _get_output_types(self, node: Dict[str, Any], output_field: str) -> List[str]:
        """Get output types for a specific output field."""
        outputs = node.get("data", {}).get("outputs", [])
        for output in outputs:
            if output.get("name") == output_field:
                return output.get("types", ["Data"])

        # Default types based on field name
        default_types = {
            "message": ["Message"],
            "response": ["Message"],
            "component_as_tool": ["Tool"],
            "prompt": ["PromptValue"],
            "text_output": ["Text"],
            "output": ["Data"]
        }
        return default_types.get(output_field, ["Data"])

    def _get_input_types(self, node: Dict[str, Any], input_field: str) -> List[str]:
        """Get input types for a specific input field."""
        template = node.get("data", {}).get("node", {}).get("template", {})
        field_def = template.get(input_field, {})

        if "input_types" in field_def:
            return field_def["input_types"]

        # Default types based on field name
        default_types = {
            "input_value": ["Data", "DataFrame", "Message"],
            "tools": ["Tool"],
            "system_prompt": ["Text"],
            "prompt": ["PromptValue"],
            "llm": ["BaseLanguageModel"],
            "memory": ["BaseChatMemory"]
        }
        return default_types.get(input_field, ["Data"])

    def _validate_type_compatibility(self, output_types: List[str], input_types: List[str], source_type: str, target_type: str) -> bool:
        """Validate that output types are compatible with input types."""
        # Check for direct type match
        for output_type in output_types:
            if output_type in input_types:
                return True

        # Check for compatible type hierarchies
        compatible_mappings = {
            "Message": ["Data", "DataFrame", "Message"],
            "Tool": ["Tool"],
            "PromptValue": ["Text", "PromptValue"],
            "Text": ["Data", "Text"],
            "Data": ["Data", "DataFrame"]
        }

        for output_type in output_types:
            if output_type in compatible_mappings:
                for compatible_type in compatible_mappings[output_type]:
                    if compatible_type in input_types:
                        return True

        return False

    def _determine_handle_type(self, input_field: str, input_types: List[str]) -> str:
        """Determine handle type based on input field and types."""
        if input_field in ["tools"]:
            return "target"
        return "other"

    def _detect_patterns(self, analysis: Dict) -> List[str]:
        """Detect patterns in flow analysis"""
        patterns = []

        if analysis.get("models"):
            patterns.append("llm_integration")

        if analysis.get("tools"):
            patterns.append("tool_usage")

        workflow_type = analysis.get("workflow_type", "")
        if workflow_type:
            patterns.append(f"workflow_{workflow_type}")

        complexity = analysis.get("flow_complexity", {})
        if complexity.get("node_count", 0) > 5:
            patterns.append("complex_flow")

        return patterns

    def _extract_goal(self, analysis: Dict) -> str:
        """Extract agent goal from analysis"""
        # Try to find agent nodes with system prompts
        components = analysis.get("components", [])
        for comp in components:
            if comp.get("type") == "genesis:agent":
                config = comp.get("config", {})
                if "system_prompt" in config:
                    return config["system_prompt"]

        # Fallback: generic goal based on workflow type
        workflow_type = analysis.get("workflow_type", "")
        if workflow_type == "tool_heavy":
            return "Process requests using multiple tools and APIs"
        elif workflow_type == "agent_based":
            return "Provide intelligent assistance using AI capabilities"
        else:
            return "Process and respond to user requests"

    def _convert_analysis_to_components(self, analysis: Dict) -> List[ComponentSpec]:
        """Convert analysis results to ComponentSpec objects"""
        components = []

        raw_components = analysis.get("components", [])
        for comp_data in raw_components:
            component = ComponentSpec(
                id=comp_data.get("id", str(uuid4())),
                name=comp_data.get("name"),
                type=comp_data.get("type", "unknown"),
                description=comp_data.get("description", ""),
                config=comp_data.get("config", {}),
            )
            components.append(component)

        return components

    def _convert_variables(self, variables: List[Dict]) -> List[VariableDefinition]:
        """Convert variables to VariableDefinition objects"""
        return [
            VariableDefinition(
                name=var["name"],
                type=var["type"],
                required=var.get("required", False),
                default=var.get("default"),
                description=var.get("description", ""),
            )
            for var in variables
        ]

    def _convert_kpis(self, kpis: List[Dict]) -> List[EnhancedKPI]:
        """Convert KPIs to EnhancedKPI objects"""
        return [
            EnhancedKPI(
                name=kpi["name"],
                description=kpi["description"],
                category=kpi.get("category"),
                value_type=kpi.get("value_type"),
                target=kpi.get("target"),
                unit=kpi.get("unit"),
            )
            for kpi in kpis
        ]

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use in ID"""
        return "".join(c.lower() if c.isalnum() else "_" for c in name)

    def _create_component_node(self, component: ComponentSpec, position: Dict) -> Dict:
        """Create a Langflow node from a component specification"""
        return {
            "id": component.id,
            "type": self._map_genesis_to_langflow_type(component.type),
            "data": {
                "node": {
                    "display_name": component.name or component.id,
                    "description": component.description,
                    "template": self._convert_config_to_template(component.config or {}),
                }
            },
            "position": {"x": position["x"], "y": position["y"]},
            "selected": False,
            "positionAbsolute": {"x": position["x"], "y": position["y"]},
        }

    def _find_node_by_id(self, nodes: List[Dict], node_id: str) -> Optional[Dict]:
        """Find node by ID"""
        for node in nodes:
            if node["id"] == node_id:
                return node
        return None

    def _create_edge(self, source_id: str, target_id: str) -> Dict:
        """Create an edge between two nodes"""
        return {
            "id": f"{source_id}-{target_id}",
            "source": source_id,
            "target": target_id,
            "sourceHandle": "output",
            "targetHandle": "input",
            "selected": False,
        }

    def _map_genesis_to_langflow_type(self, genesis_type: str) -> str:
        """Map Genesis component type to Langflow node type"""
        mapping = {
            "genesis:chat_input": "ChatInput",
            "genesis:chat_output": "ChatOutput",
            "genesis:agent": "Agent",
            "genesis:llm_openai": "ChatOpenAI",
            "genesis:llm_anthropic": "ChatAnthropic",
            "genesis:api_component": "APIChain",
            "genesis:python_function": "PythonFunction",
            "genesis:text_input": "TextInput",
            "genesis:number_input": "NumberInput",
        }
        return mapping.get(genesis_type, "CustomComponent")

    def _convert_config_to_template(self, config: Dict) -> Dict:
        """Convert component config to Langflow template format"""
        template = {}
        for key, value in config.items():
            template[key] = {"value": value}
        return template

    # ===== NEW ASYNC METHODS FOR SPEC TO FLOW CONVERSION =====

    async def spec_to_flow(self, spec: EnhancedAgentSpec) -> Dict[str, Any]:
        """Convert Genesis Agent Specification to Langflow format asynchronously."""
        try:
            # Initialize dynamic mapper if not already done
            if not hasattr(self, 'dynamic_mapper') or not self.dynamic_mapper:
                from langflow.services.specification.dynamic_component_mapper import get_dynamic_mapper
                try:
                    self.dynamic_mapper = await get_dynamic_mapper()
                except Exception as e:
                    print(f"⚠️  Error loading dynamic mapper: {e}")
                    # Create a fallback mapper
                    from langflow.services.specification.dynamic_component_mapper import DynamicComponentMapper
                    self.dynamic_mapper = DynamicComponentMapper()
                    self.dynamic_mapper._load_fallback_components()

            # Build nodes and edges
            nodes = await self._build_nodes(spec)
            edges = await self._build_edges(spec, nodes)

            # Create flow structure
            flow = {
                "data": {
                    "nodes": nodes,
                    "edges": edges,
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                    "metadata": {
                        "genesis_spec": spec.model_dump(),
                        "original_yaml": spec.to_yaml(),
                        "creation_timestamp": datetime.now().isoformat(),
                        "conversion_method": "specification_to_flow"
                    }
                },
                "name": spec.name,
                "description": spec.description,
                "is_component": False
            }

            return flow

        except Exception as e:
            raise Exception(f"Failed to convert specification to flow: {str(e)}")

    async def _build_nodes(self, spec: EnhancedAgentSpec) -> List[Dict[str, Any]]:
        """Build Langflow nodes from specification components."""
        nodes = []

        # Calculate positions
        positions = self._calculate_positions(len(spec.components))

        for i, component in enumerate(spec.components):
            position = positions[i]

            # Get the actual Langflow component type
            langflow_type = self.dynamic_mapper.get_component_type(component.type)

            # Get component data from dynamic mapper
            component_data = self.dynamic_mapper.get_component_data(langflow_type)
            category = self.dynamic_mapper.get_component_category(langflow_type)

            # Check if this component is used as a tool
            is_tool = self._is_component_used_as_tool(component)

            # Deep copy component data to avoid modifying the cached version
            if component_data:
                node_data_source = copy.deepcopy(component_data)
            else:
                node_data_source = {}

            # Handle tool mode
            if is_tool:
                # Set tool mode
                node_data_source["tool_mode"] = True

                # Ensure we have the component_as_tool output
                if "outputs" in node_data_source:
                    # Check if component_as_tool already exists
                    has_tool_output = any(o.get("name") == "component_as_tool" for o in node_data_source["outputs"])

                    if not has_tool_output:
                        # Add component_as_tool output
                        node_data_source["outputs"] = [{
                            "types": ["Tool"],
                            "selected": "Tool",
                            "name": "component_as_tool",
                            "display_name": "Toolset",
                            "method": "to_toolkit",
                            "value": "__UNDEFINED__",
                            "cache": True,
                            "allows_loop": False,
                            "tool_mode": True
                        }]

            # Build template from component config and schema
            template = await self._build_template(component, node_data_source)

            # Create node data structure
            node_data = {
                "display_name": component.name or component.id,
                "description": component.description or "",
                "template": template,
            }

            # Add component-specific data if available
            if node_data_source:
                # Add base classes and outputs from component schema
                if "base_classes" in node_data_source:
                    node_data["base_classes"] = node_data_source["base_classes"]
                if "outputs" in node_data_source:
                    node_data["outputs"] = node_data_source["outputs"]
                if "tool_mode" in node_data_source:
                    node_data["tool_mode"] = node_data_source["tool_mode"]

            # Create the node
            node = {
                "id": component.id,
                "type": "genericNode",  # Critical: UI expects this
                "position": position,
                "data": {
                    "type": langflow_type,  # Actual component type here
                    "node": node_data,
                },
                "width": 384,  # Required for UI
                "height": self._get_node_height(category),
                "selected": False,
                "positionAbsolute": position,
            }

            nodes.append(node)

        return nodes

    async def _build_edges(self, spec: EnhancedAgentSpec, nodes: List[Dict]) -> List[Dict[str, Any]]:
        """Build Langflow edges from specification provides patterns."""
        edges = []
        node_map = {node["id"]: node for node in nodes}

        try:
            # Build edges based on provides patterns
            for component in spec.components:
                # Handle both ComponentSpec objects and dict representations
                if isinstance(component, dict):
                    provides = component.get('provides', [])
                    source_id = component.get('id')
                else:
                    provides = getattr(component, 'provides', [])
                    source_id = getattr(component, 'id', None)

                if not provides or not source_id:
                    continue

                if source_id not in node_map:
                    continue

                for provide in provides:
                    try:
                        edge = await self._create_edge_from_provides(
                            source_id,
                            provide,
                            node_map,
                            component
                        )
                        if edge:
                            edges.append(edge)
                    except Exception as e:
                        print(f"⚠️  Error creating edge for {source_id}: {e}")
                        continue

        except Exception as e:
            print(f"⚠️  Error building edges: {e}")

        return edges

    async def _create_edge_from_provides(
        self,
        source_id: str,
        provide: Dict,
        node_map: Dict[str, Dict[str, Any]],
        source_component: ComponentSpec
    ) -> Optional[Dict]:
        """Create edge from provides pattern with proper Genesis Studio structure."""

        # Handle both naming conventions: use_as or useAs
        use_as = provide.get('use_as') or provide.get('useAs')
        target_id = provide.get('in')

        if not target_id or not use_as:
            return None

        if target_id not in node_map:
            print(f"⚠️  Target node '{target_id}' not found for provides connection")
            return None

        # Get nodes
        source_node = node_map[source_id]
        target_node = node_map[target_id]

        # Get actual component types
        source_type = source_node["data"]["type"]
        target_type = target_node["data"]["type"]

        # Determine output field based on use_as and component outputs
        output_field = self._determine_output_field(use_as, source_node, source_type)

        # Determine input field
        input_field = self._map_use_as_to_field(use_as)

        # Determine output types based on the output field
        output_types = self._get_output_types(source_node, output_field)

        # Create source handle (non-encoded for data object)
        source_handle = {
            "dataType": source_type,
            "id": source_id,
            "name": output_field,
            "output_types": output_types
        }

        # Determine input types based on the field
        input_types = self._get_input_types(target_node, input_field)

        # Validate type compatibility
        if not self._validate_type_compatibility(output_types, input_types, source_type, target_type):
            print(f"⚠️  Type mismatch: {source_type} outputs {output_types} but {target_type}.{input_field} expects {input_types}")
            return None

        # Determine handle type based on Genesis Studio conventions
        handle_type = self._determine_handle_type(input_field, input_types)

        # Create target handle (non-encoded for data object)
        target_handle = {
            "fieldName": input_field,
            "id": target_id,
            "inputTypes": input_types,
            "type": handle_type
        }

        # Encode handles for sourceHandle/targetHandle fields
        source_handle_encoded = json.dumps(source_handle, separators=(",", ":")).replace('"', "œ")
        target_handle_encoded = json.dumps(target_handle, separators=(",", ":")).replace('"', "œ")

        # Create edge with proper Genesis Studio structure
        edge = {
            "className": "",
            "data": {
                "sourceHandle": source_handle,
                "targetHandle": target_handle,
                "label": provide.get("description", "")
            },
            "id": f"reactflow__edge-{source_id}{source_handle_encoded}-{target_id}{target_handle_encoded}",
            "selected": False,
            "source": source_id,
            "sourceHandle": source_handle_encoded,
            "target": target_id,
            "targetHandle": target_handle_encoded
        }

        return edge

    async def _build_template(self, component: ComponentSpec, component_data: Optional[Dict]) -> Dict[str, Any]:
        """Build template from component config and component schema."""
        template = {}

        # Start with schema template if available
        if component_data and "template" in component_data:
            template.update(component_data["template"])

        # Apply component config values
        if component.config:
            for key, value in component.config.items():
                if key in template:
                    # Update existing template field
                    template[key]["value"] = value
                else:
                    # Create new template field
                    template[key] = {
                        "value": value,
                        "show": True,
                        "required": False,
                        "type": self._infer_type(value)
                    }

        return template

    def _infer_type(self, value: Any) -> str:
        """Infer template field type from value."""
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, list):
            return "list"
        elif isinstance(value, dict):
            return "dict"
        else:
            return "str"

    def _get_node_height(self, category: str) -> int:
        """Get node height based on component category."""
        height_map = {
            "agents": 400,
            "chains": 350,
            "retrievers": 300,
            "embeddings": 250,
            "vectorstores": 300,
            "memories": 250,
            "tools": 300,
            "custom": 350,
        }
        return height_map.get(category, 350)

    def _calculate_positions(self, count: int) -> List[Dict[str, int]]:
        """Calculate positions for nodes in a horizontal layout."""
        positions = []
        x_spacing = 450  # Spacing between nodes
        y_base = 100     # Base Y position

        for i in range(count):
            positions.append({
                "x": 100 + (i * x_spacing),
                "y": y_base
            })

        return positions

    def _determine_output_field(self, use_as: str, source_node: Dict[str, Any], source_type: str) -> str:
        """Determine the output field based on use_as type and component."""
        # Special case for tools - they use component_as_tool
        if use_as in ["tool", "tools"]:
            return "component_as_tool"

        # Check if node has outputs defined
        outputs = source_node.get("data", {}).get("outputs", [])
        if outputs:
            # For agents, typically use "response"
            if "Agent" in source_type and any(o.get("name") == "response" for o in outputs):
                return "response"
            # For prompts, typically use "prompt"
            elif "Prompt" in source_type and any(o.get("name") == "prompt" for o in outputs):
                return "prompt"
            # Otherwise use first output
            return outputs[0].get("name", "output")

        # Default mappings
        output_mappings = {
            "input": "message",
            "tool": "component_as_tool",
            "tools": "component_as_tool",
            "system_prompt": "prompt",
            "prompt": "prompt",
            "llm": "text_output",
            "response": "response",
            "message": "message",
            "text": "text",
            "output": "output"
        }

        return output_mappings.get(use_as, "output")

    def _map_use_as_to_field(self, use_as: str) -> str:
        """Map use_as value to Langflow field name."""
        field_mappings = {
            "input": "input_value",
            "tool": "tools",
            "tools": "tools",
            "system_prompt": "system_message",
            "prompt": "template",
            "llm": "llm",
            "response": "input_value",
            "message": "message",
            "text": "text",
            "output": "input_value"
        }

        return field_mappings.get(use_as, use_as)

    def _get_output_types(self, node: Dict[str, Any], output_field: str) -> List[str]:
        """Get output types for a specific output field."""
        # Special case for component_as_tool
        if output_field == "component_as_tool":
            return ["Tool"]

        # Check node outputs
        outputs = node.get("data", {}).get("outputs", [])
        for output in outputs:
            if output.get("name") == output_field:
                types = output.get("types", [])
                if types:
                    return types

        # Default types based on field name
        if "message" in output_field or "response" in output_field:
            return ["Message"]
        elif "prompt" in output_field:
            return ["Message", "str"]
        elif "tool" in output_field:
            return ["Tool"]
        else:
            return ["Message", "str"]

    def _get_input_types(self, node: Dict[str, Any], input_field: str) -> List[str]:
        """Get input types for a specific input field."""
        # Check template for input types
        template = node.get("data", {}).get("node", {}).get("template", {})
        if input_field in template:
            field_def = template[input_field]
            if isinstance(field_def, dict):
                input_types = field_def.get("input_types", [])
                if input_types:
                    return input_types

        # Default types based on field name
        if input_field == "tools":
            return ["Tool"]
        elif input_field == "input_value":
            return ["Data", "DataFrame", "Message"]
        elif "message" in input_field:
            return ["Message"]
        else:
            return ["Message", "str"]

    def _validate_type_compatibility(self, output_types: List[str], input_types: List[str],
                                   source_type: str, target_type: str) -> bool:
        """Validate if output types are compatible with input types."""
        # Tool connections are always valid
        if "Tool" in output_types and "Tool" in input_types:
            return True

        # Check for direct type matches
        if any(otype in input_types for otype in output_types):
            return True

        # Special case: Message -> Data incompatibility
        if "Message" in output_types and "Data" in input_types and "Message" not in input_types:
            # Specific components that cannot accept Message despite expecting Data
            incompatible_data_components = ["JSONOutput", "DataOutput", "ParseData"]
            if any(comp in target_type for comp in incompatible_data_components):
                return False

        # Check for compatible type conversions
        compatible_conversions = {
            "Message": ["str", "text", "Text"],
            "str": ["Message", "text", "Text"],
            "Data": ["dict", "object", "any"],
            "DataFrame": ["Data", "object", "any"]
        }

        for otype in output_types:
            if otype in compatible_conversions:
                if any(ctype in input_types for ctype in compatible_conversions[otype]):
                    return True

        # If input accepts "any" or "object", it's compatible
        if "any" in input_types or "object" in input_types:
            return True

        # Default to incompatible
        return False

    def _determine_handle_type(self, input_field: str, input_types: List[str]) -> str:
        """Determine the handle type based on Genesis Studio conventions."""
        # Tools always use "other"
        if input_field == "tools":
            return "other"

        # Multiple input types use "other"
        if len(input_types) > 1:
            return "other"

        # Single Message type uses "str"
        if input_types and input_types[0] == "Message":
            return "str"

        # Single type uses the type name
        if input_types:
            return input_types[0]

        # Default to "str"
        return "str"

    def _is_component_used_as_tool(self, component) -> bool:
        """Check if a component is used as a tool based on its provides declarations."""
        # Handle both ComponentSpec objects and dict representations
        if isinstance(component, dict):
            provides = component.get('provides', [])
        else:
            provides = getattr(component, 'provides', [])

        if not provides:
            return False

        for provide in provides:
            # Handle both naming conventions
            use_as = provide.get('use_as') or provide.get('useAs')
            if use_as in ["tool", "tools"]:
                return True
        return False
"""
Genesis Flow Converter - Refactored for AUTPE-6204 with database-first approach.

This converter removes all hardcoded tool mappings and uses dynamic discovery.
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging

from .models import AgentSpec, Component
from .mapper_refactored import ComponentMapper  # Use refactored mapper
from .resolver import VariableResolver

# Import for database-driven tool mapping
from langflow.services.component_mapping.capability_service import ComponentCapabilityService
from langflow.services.component_mapping.component_registry import ComponentRegistry
from langflow.services.deps import session_scope

logger = logging.getLogger(__name__)


class FlowConverter:
    """Converts Genesis agent specifications to Langflow flows using database mappings."""

    def __init__(self):
        """Initialize with database-driven services."""
        self.mapper = ComponentMapper()
        self.resolver = VariableResolver()

        # Initialize services for dynamic discovery
        try:
            self.capability_service = ComponentCapabilityService()
            self.component_registry = ComponentRegistry()

            # Initialize registry if not already done
            if not self.component_registry.is_initialized():
                self.component_registry.discover_components()

        except Exception as e:
            logger.warning(f"Could not initialize services: {e}")
            self.capability_service = None
            self.component_registry = None

        # Cache for tool server mappings (populated from database)
        self._tool_server_cache = {}

    async def convert_async(self, agent_spec: AgentSpec) -> Dict[str, Any]:
        """
        Convert agent specification to Langflow format with database mappings.

        Args:
            agent_spec: Genesis agent specification

        Returns:
            Langflow JSON structure
        """
        # Load tool server mappings from database
        await self._load_tool_server_mappings()

        # Resolve variables
        self.resolver.add_variables(agent_spec.variables)

        # Create flow structure
        flow = self._create_flow_structure(agent_spec)

        # Convert components
        nodes = {}
        edges = []

        for i, component in enumerate(agent_spec.components):
            # Get database mapping
            async with session_scope() as session:
                mapping = await self.mapper.map_component_async(component.type, session)

            node = await self._create_node(component, mapping, i)
            nodes[node["id"]] = node

            # Create edges based on provides
            if component.provides:
                for provided_id in component.provides:
                    edges.extend(self._create_edges(component, provided_id, nodes))

        flow["data"]["nodes"] = list(nodes.values())
        flow["data"]["edges"] = edges

        return flow

    def convert(self, agent_spec: AgentSpec) -> Dict[str, Any]:
        """
        Synchronous conversion for backward compatibility.

        Args:
            agent_spec: Genesis agent specification

        Returns:
            Langflow JSON structure
        """
        # Resolve variables
        self.resolver.add_variables(agent_spec.variables)

        # Create flow structure
        flow = self._create_flow_structure(agent_spec)

        # Convert components
        nodes = {}
        edges = []

        for i, component in enumerate(agent_spec.components):
            # Use synchronous mapping
            mapping = self.mapper.map_component(component.type)

            node = self._create_node_sync(component, mapping, i)
            nodes[node["id"]] = node

            # Create edges
            if component.provides:
                for provided_id in component.provides:
                    edges.extend(self._create_edges(component, provided_id, nodes))

        flow["data"]["nodes"] = list(nodes.values())
        flow["data"]["edges"] = edges

        return flow

    async def _load_tool_server_mappings(self):
        """Load tool server mappings from database."""
        if not self.capability_service:
            return

        try:
            async with session_scope() as session:
                # Get tool server mappings from database
                mappings = await self.capability_service.get_tool_server_mappings(session)

                for mapping in mappings:
                    tool_name = mapping.get("tool_name")
                    server_info = {
                        "server_name": mapping.get("server_name"),
                        "tool_filter": mapping.get("tool_filter"),
                        "description": mapping.get("description"),
                        "config": mapping.get("config", {}),
                    }
                    self._tool_server_cache[tool_name] = server_info

                logger.info(f"Loaded {len(self._tool_server_cache)} tool server mappings from database")

        except Exception as e:
            logger.warning(f"Could not load tool server mappings: {e}")

    def _get_tool_server_mapping(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get tool server mapping from cache or database.

        Args:
            tool_name: Name of the tool

        Returns:
            Server mapping information or None
        """
        # Check cache first
        if tool_name in self._tool_server_cache:
            return self._tool_server_cache[tool_name]

        # Check component registry for tool capabilities
        if self.component_registry:
            components = self.component_registry.get_all_components()
            for comp_name, metadata in components.items():
                if tool_name in metadata.tags or tool_name == comp_name.lower():
                    return {
                        "server_name": f"{metadata.category}_server",
                        "tool_filter": tool_name,
                        "description": metadata.description,
                        "config": {},
                    }

        return None

    def _create_flow_structure(self, agent_spec: AgentSpec) -> Dict[str, Any]:
        """Create the base flow structure."""
        return {
            "name": agent_spec.metadata.get("name", "Genesis Flow"),
            "description": agent_spec.metadata.get("description", ""),
            "data": {
                "nodes": [],
                "edges": [],
                "viewport": {"x": 0, "y": 0, "zoom": 1}
            },
            "is_component": False,
            "endpoint_name": agent_spec.metadata.get("endpoint", None),
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "genesis_version": agent_spec.metadata.get("version", "1.0.0"),
                "converted_by": "genesis-converter-v2",
            }
        }

    async def _create_node(self, component: Component, mapping: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Create a node from component with async configuration loading."""
        node = self._create_base_node(component, mapping, index)

        # Handle MCP tools with database configuration
        if mapping["component"] == "MCPToolsComponent" and component.config.get("tool_name"):
            tool_name = component.config["tool_name"]
            server_mapping = self._get_tool_server_mapping(tool_name)

            if server_mapping:
                # Update config with server information
                node["data"]["node"]["template"]["command"]["value"] = (
                    f"npx @modelcontextprotocol/{server_mapping['server_name']}"
                )
                node["data"]["node"]["template"]["tool_filter"]["value"] = server_mapping["tool_filter"]

                # Apply additional config from database
                if server_mapping.get("config"):
                    for key, value in server_mapping["config"].items():
                        if key in node["data"]["node"]["template"]:
                            node["data"]["node"]["template"][key]["value"] = value

        return node

    def _create_node_sync(self, component: Component, mapping: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Create a node synchronously."""
        return self._create_base_node(component, mapping, index)

    def _create_base_node(self, component: Component, mapping: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Create the base node structure."""
        # Resolve configuration values
        config = {}
        for key, value in component.config.items():
            config[key] = self.resolver.resolve(value)

        # Merge with mapping config
        final_config = {**mapping.get("config", {}), **config}

        # Create node structure
        node_id = component.id or f"node_{index}_{uuid.uuid4().hex[:8]}"

        node = {
            "id": node_id,
            "type": "genericNode",
            "position": {
                "x": 100 + (index % 4) * 300,
                "y": 100 + (index // 4) * 200
            },
            "data": {
                "type": mapping["component"],
                "node": {
                    "template": self._create_template(mapping["component"], final_config),
                    "description": component.metadata.get("description", ""),
                    "base_classes": ["Data"] if "dataType" in mapping else ["Message"],
                    "display_name": component.metadata.get("display_name", mapping["component"]),
                },
                "id": node_id,
            }
        }

        return node

    def _create_template(self, component_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create component template from configuration."""
        template = {}

        # Add standard fields
        for key, value in config.items():
            template[key] = {
                "required": False,
                "placeholder": "",
                "show": True,
                "value": value,
                "name": key,
                "display_name": key.replace("_", " ").title(),
                "advanced": False,
                "input_types": ["Text"],
                "dynamic": False,
                "info": "",
                "title_case": False,
                "type": "str",
                "_input_type": "TextInput"
            }

        return template

    def _create_edges(self, source_component: Component, target_id: str, nodes: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create edges between components."""
        edges = []

        # Get source and target nodes
        source_node = nodes.get(source_component.id)
        target_node = None

        for node_id, node in nodes.items():
            if node_id == target_id or target_id in node_id:
                target_node = node
                break

        if not source_node or not target_node:
            logger.warning(f"Could not create edge: source={source_component.id}, target={target_id}")
            return edges

        # Get I/O mappings from registry
        source_io = self._get_io_mapping(source_node["data"]["type"])
        target_io = self._get_io_mapping(target_node["data"]["type"])

        # Create edge
        edge = {
            "source": source_node["id"],
            "target": target_node["id"],
            "sourceHandle": f"{source_node['id']}|{source_io['output_field']}|{source_io['output_types'][0]}",
            "targetHandle": f"{target_node['id']}|{target_io['input_field']}|{target_io['input_types'][0]}",
            "id": f"edge_{uuid.uuid4().hex[:8]}",
            "data": {
                "sourceHandle": {
                    "id": source_node["id"],
                    "name": source_io["output_field"],
                    "output_types": source_io["output_types"]
                },
                "targetHandle": {
                    "id": target_node["id"],
                    "name": target_io["input_field"],
                    "input_types": target_io["input_types"]
                }
            }
        }

        edges.append(edge)
        return edges

    def _get_io_mapping(self, component_type: str) -> Dict[str, Any]:
        """Get I/O mapping for a component type from registry."""
        if self.component_registry:
            component = self.component_registry.get_component_by_name(component_type)
            if component:
                return {
                    "input_field": self._get_primary_field(component.input_fields, "input"),
                    "output_field": self._get_primary_field(component.output_fields, "output"),
                    "input_types": component.input_fields.get("_input_types", ["Any"]),
                    "output_types": component.output_fields.get("_output_types", ["Any"]),
                }

        # Fallback
        return {
            "input_field": "input_value",
            "output_field": "output",
            "input_types": ["Any"],
            "output_types": ["Any"],
        }

    def _get_primary_field(self, fields: Dict[str, Any], field_type: str) -> str:
        """Get primary field name."""
        if not fields:
            return "input_value" if field_type == "input" else "output"

        # Look for standard names
        if field_type == "input":
            for name in ["input_value", "input", "query", "text", "data"]:
                if name in fields:
                    return name
        else:
            for name in ["output", "result", "response", "data", "text"]:
                if name in fields:
                    return name

        # Return first field
        public_fields = [k for k in fields.keys() if not k.startswith("_")]
        return public_fields[0] if public_fields else ("input_value" if field_type == "input" else "output")
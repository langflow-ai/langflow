"""
Genesis Flow Converter - Converts agent specifications to AI Studio flows.

This converter:
1. Maps Genesis types to AI Studio components
2. Creates connections using the provides pattern
3. Generates valid Langflow JSON with proper edge encoding
4. Fixes all critical edge connection issues
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging

from .models import AgentSpec, Component
from .mapper import ComponentMapper
from .resolver import VariableResolver

logger = logging.getLogger(__name__)


# Tool name to MCP server mapping registry
TOOL_NAME_TO_SERVER_MAPPING = {
    # Healthcare EHR Tools
    "ehr_patient_records": {
        "server_name": "healthcare_ehr_server",
        "tool_filter": "ehr_patient_records",
        "description": "Healthcare EHR system for patient records access"
    },
    "ehr_calendar_access": {
        "server_name": "healthcare_ehr_server",
        "tool_filter": "ehr_calendar_access",
        "description": "Healthcare EHR system for provider scheduling"
    },
    "ehr_care_plans": {
        "server_name": "healthcare_ehr_server",
        "tool_filter": "ehr_care_plans",
        "description": "Healthcare EHR system for care plans access"
    },

    # Pharmacy and Claims Tools
    "pharmacy_claims_ncpdp": {
        "server_name": "pharmacy_claims_server",
        "tool_filter": "pharmacy_claims_ncpdp",
        "description": "NCPDP pharmacy claims data access"
    },
    "medication_records": {
        "server_name": "pharmacy_claims_server",
        "tool_filter": "medication_records",
        "description": "Medication information and prescription access"
    },
    "healthcare_claims_database": {
        "server_name": "claims_analytics_server",
        "tool_filter": "healthcare_claims_database",
        "description": "Healthcare claims database for analytics"
    },

    # Insurance and Eligibility Tools
    "insurance_eligibility_check": {
        "server_name": "insurance_services_server",
        "tool_filter": "insurance_eligibility_check",
        "description": "Real-time insurance eligibility verification"
    },
    "insurance_plan_rules": {
        "server_name": "insurance_services_server",
        "tool_filter": "insurance_plan_rules",
        "description": "Insurance plan benefits and coverage information"
    },

    # Member Management Tools
    "member_management_system": {
        "server_name": "member_services_server",
        "tool_filter": "member_management_system",
        "description": "Member demographics and management system"
    },

    # Communication Tools
    "sms_gateway": {
        "server_name": "communication_services_server",
        "tool_filter": "sms_gateway",
        "description": "SMS messaging service"
    },
    "email_service": {
        "server_name": "communication_services_server",
        "tool_filter": "email_service",
        "description": "Email communication service"
    },

    # Analytics and Feedback Tools
    "call_center_logs": {
        "server_name": "analytics_server",
        "tool_filter": "call_center_logs",
        "description": "Call center logs and conversation analytics"
    },
    "survey_responses": {
        "server_name": "analytics_server",
        "tool_filter": "survey_responses",
        "description": "Patient survey response analytics"
    },
    "complaint_management": {
        "server_name": "analytics_server",
        "tool_filter": "complaint_management",
        "description": "Complaint and grievance management system"
    },
    "patient_feedback_analytics": {
        "server_name": "analytics_server",
        "tool_filter": "patient_feedback_analytics",
        "description": "Patient feedback and satisfaction analytics"
    },
    "appointment_analytics": {
        "server_name": "analytics_server",
        "tool_filter": "appointment_analytics",
        "description": "Appointment scheduling analytics and KPIs"
    },

    # Specialized Healthcare Tools
    "healthcare_nlp_sentiment": {
        "server_name": "healthcare_ai_server",
        "tool_filter": "healthcare_nlp_sentiment",
        "description": "Healthcare-specific NLP sentiment analysis"
    },
    "ml_theme_extraction": {
        "server_name": "healthcare_ai_server",
        "tool_filter": "ml_theme_extraction",
        "description": "Machine learning theme extraction for healthcare"
    },
    "symptom_checker_api": {
        "server_name": "healthcare_ai_server",
        "tool_filter": "symptom_checker_api",
        "description": "Clinical symptom analysis and triage"
    },
    "navigation_ml_analytics": {
        "server_name": "healthcare_ai_server",
        "tool_filter": "navigation_ml_analytics",
        "description": "ML-powered healthcare navigation analytics"
    },

    # Directory and Reference Tools
    "healthcare_facility_directory": {
        "server_name": "healthcare_directory_server",
        "tool_filter": "healthcare_facility_directory",
        "description": "Healthcare facility and provider directory"
    },

    # Care Coordination Tools
    "ehr_systems_integration": {
        "server_name": "care_coordination_server",
        "tool_filter": "ehr_systems_integration",
        "description": "Multi-EHR systems integration for care coordination"
    },
    "referral_management_systems": {
        "server_name": "care_coordination_server",
        "tool_filter": "referral_management_systems",
        "description": "Referral management and coordination systems"
    },
    "hie_integration": {
        "server_name": "care_coordination_server",
        "tool_filter": "hie_integration",
        "description": "Health Information Exchange integration"
    },
    "care_management_platforms": {
        "server_name": "care_coordination_server",
        "tool_filter": "care_management_platforms",
        "description": "Care management and coordination platforms"
    }
}


def _get_component_template_service():
    """Lazy import to avoid circular dependency."""
    try:
        from langflow.services.spec.component_template_service import component_template_service
        return component_template_service
    except ImportError:
        logger.warning("component_template_service not available")
        return None


class FlowConverter:
    """Converts agent specifications to AI Studio flows with corrected edge logic."""

    def __init__(self, mapper: Optional[ComponentMapper] = None,
                 resolver: Optional[VariableResolver] = None):
        """Initialize the flow converter."""
        self.mapper = mapper or ComponentMapper()
        self.resolver = resolver or VariableResolver()

    async def convert(self, spec_data: Dict[str, Any],
                     variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Convert a specification to AI Studio flow.

        Args:
            spec_data: Parsed YAML specification as dict
            variables: Runtime variables for resolution

        Returns:
            Complete flow structure for AI Studio
        """
        # Create spec object
        spec = AgentSpec.from_dict(spec_data)

        # Resolve variables if provided
        if variables:
            self.resolver.variables.update(variables)

        # Build nodes
        nodes = await self._build_nodes(spec)

        # Build edges using provides pattern
        edges = await self._build_edges(spec, nodes)

        # Create flow structure
        flow = {
            "data": {
                "nodes": nodes,
                "edges": edges,
                "viewport": {"x": 0, "y": 0, "zoom": 0.5}
            },
            "name": spec.name,
            "description": spec.description,
            "is_component": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "folder": None,
            "id": None,
            "user_id": None,
            "webhook": False,
            "endpoint_name": None
        }

        # Add metadata
        flow["metadata"] = {
            "agentGoal": spec.agentGoal,
            "targetUser": spec.targetUser,
            "valueGeneration": spec.valueGeneration,
            "kind": spec.kind,
            "tags": spec.tags or [],
            "kpis": [kpi.model_dump() for kpi in spec.kpis] if spec.kpis else []
        }

        return flow

    async def _build_nodes(self, spec: AgentSpec) -> List[Dict[str, Any]]:
        """Build nodes from agent specification."""
        # Store spec for position calculation
        self._current_spec = spec
        nodes = []

        for i, component in enumerate(spec.components):
            node = await self._build_node(component, i, spec)
            if node:
                nodes.append(node)

        return nodes

    async def _build_node(self, component: Component, index: int,
                         spec: AgentSpec = None) -> Optional[Dict[str, Any]]:
        """Build a single node from component specification."""
        logger.debug(f"Building node for component: {component.id} (type: {component.type})")

        # Map component type
        mapping = self.mapper.map_component(component.type)
        component_type = mapping["component"]
        # Use dataType for edge creation if specified, otherwise use component_type
        data_type = mapping.get("dataType", component_type)
        logger.debug(f"Mapped {component.type} → {component_type} (dataType: {data_type})")

        # Get component template (this would come from component registry in real implementation)
        template = await self._get_component_template(component_type)

        if not template:
            logger.error(f"Component template not found for: {component_type} (original: {component.type})")
            service = _get_component_template_service()
            if service:
                available = await service.load_components()
                logger.error(f"Available templates: {list(available or {})}")
            else:
                logger.error("Available templates: [service not available]")
            return None

        # Set current component ID for position calculation
        self._current_component_id = component.id

        # Calculate position based on component kind and role
        position = self._calculate_position(index, component.kind)

        # Check if this component is used as a tool
        is_tool = self._is_component_used_as_tool(component)

        # Deep copy template to avoid modifying cached version
        import copy
        node_data = copy.deepcopy(template)

        # Override template metadata with spec values
        if node_data and isinstance(node_data, dict):
            # Set display_name and description from spec
            node_data["display_name"] = component.name
            node_data["description"] = component.description or ""

        # Handle tool mode
        if is_tool:
            logger.info(f"🔨 Setting up tool mode for {component.id} (type: {component.type})")
            node_data["tool_mode"] = True

            # Initialize outputs if not present
            if "outputs" not in node_data:
                node_data["outputs"] = []

            # For tool mode, ensure component_as_tool is the FIRST output
            # Remove any existing non-tool outputs if this is being used as a tool
            if is_tool:
                # Check if component_as_tool already exists
                has_tool_output = any(o.get("name") == "component_as_tool"
                                    for o in node_data["outputs"])

                if not has_tool_output:
                    logger.info(f"  Adding component_as_tool output to {component.id}")
                    # Insert as first output for tools
                    node_data["outputs"].insert(0, {
                        "types": ["Tool"],
                        "selected": "Tool",
                        "name": "component_as_tool",
                        "display_name": "Toolset",
                        "method": "to_toolkit",
                        "value": "__UNDEFINED__",
                        "cache": True,
                        "allows_loop": False,
                        "tool_mode": True,
                        "hidden": None,
                        "required_inputs": None
                    })
                else:
                    logger.info(f"  Component {component.id} already has tool output")

                # Special handling for KnowledgeHubSearch and MCPTools - ensure they output Tool when used as tool
                if "KnowledgeHubSearch" in data_type or "MCPTools" in data_type:
                    logger.info(f"  Special handling for {data_type} as tool")
                    # Make sure the tool output is primary
                    for output in node_data["outputs"]:
                        if output.get("name") == "component_as_tool":
                            output["types"] = ["Tool"]
                            output["selected"] = "Tool"

        # Build node structure
        node = {
            "id": component.id,
            "type": "genericNode",
            "position": position,
            "data": {
                "id": component.id,
                "type": data_type,
                "description": component.description or "",
                "display_name": component.name,
                "node": node_data,
                "outputs": node_data.get("outputs", [])
            },
            "dragging": False,
            "height": self._get_node_height(component.kind),
            "selected": False,
            "positionAbsolute": position,
            "width": 384,
            "measured": {
                "width": 384,
                "height": self._get_node_height(component.kind)
            }
        }

        # Apply component configuration
        if component.config or mapping.get("config"):
            self._apply_config_to_template(
                node["data"]["node"].get("template", {}),
                {**(mapping.get("config") or {}), **(component.config or {})},
                component, spec
            )

        return node

    def _apply_config_to_template(self, template: Dict[str, Any],
                                 config: Dict[str, Any],
                                 component: Component = None,
                                 spec: AgentSpec = None):
        """Apply component config values to the template."""
        # Make a copy to avoid modifying original
        config = dict(config)

        # Component-specific field mappings for proper configuration
        FIELD_MAPPINGS = {
            "Agent": {
                "provider": "agent_llm",  # Map provider to agent_llm dropdown
                "azure_deployment": "azure_deployment_name",  # Azure specific
                "azure_endpoint": "azure_api_base",
                "api_key": "openai_api_key",
                "llm_model": "model_name",
                "max_tokens": "max_tokens",
                "temperature": "temperature",
                "streaming": "stream"
            },
            "AutonomizeAgent": {
                "provider": "agent_llm",
                "azure_deployment": "azure_deployment_name",
                "temperature": "temperature"
            },
            "LanguageModelComponent": {
                "provider": "provider",  # Direct mapping
                "azure_deployment": "azure_deployment",  # Direct mapping
                "azure_endpoint": "azure_endpoint",  # Direct mapping
                "api_key": "api_key",
                "temperature": "temperature",
                "max_tokens": "max_tokens",
                "stream": "stream"
            },
            "MCPTools": {
                "tool_name": "tool_names",
                "description": "tool_description"
            },
            "APIRequest": {
                "method": "method",
                "url": "url_input",
                "headers": "headers",
                "body": "body",
                "timeout": "timeout"
            }
        }

        # Get the component type from the component
        component_type = None
        if component:
            mapping = self.mapper.map_component(component.type)
            component_type = mapping.get("component", "")

            # Apply field mappings based on component type
            if component_type in FIELD_MAPPINGS:
                mappings = FIELD_MAPPINGS[component_type]
                for old_key, new_key in mappings.items():
                    if old_key in config and old_key != new_key:
                        config[new_key] = config.pop(old_key)
                        logger.debug(f"Mapped config field {old_key} -> {new_key} for {component_type}")

        # Special handling for Agent components - use agentGoal as system_prompt
        if (component and "agent" in component.type.lower() and
            "system_prompt" not in config and spec and spec.agentGoal):
            config["system_prompt"] = spec.agentGoal

        # Special handling for KnowledgeHubSearch - map collections to selected_hubs
        if (component and "knowledge_hub_search" in component.type.lower() and
            "collections" in config and "selected_hubs" not in config):
            collections = config.pop("collections", None)
            if collections:
                if isinstance(collections, list):
                    config["selected_hubs"] = collections
                elif isinstance(collections, str):
                    # Handle comma-separated string
                    config["selected_hubs"] = [c.strip() for c in collections.split(",") if c.strip()]

        # Resolve variables in config
        resolved_config = self.resolver.resolve(config)

        logger.debug(f"Applying config to template for {component.id if component else 'unknown'}")
        logger.debug(f"Config keys: {list(resolved_config.keys())}")
        logger.debug(f"Template keys: {list(template.keys()) if template else 'No template'}")

        # Track which configs were successfully applied
        applied_configs = []
        unmapped_configs = []

        for key, value in resolved_config.items():
            if key in template and isinstance(template[key], dict):
                # Keep unresolved variables for Langflow
                if (isinstance(value, str) and value.startswith("{") and
                    value.endswith("}")):
                    template[key]["value"] = value
                else:
                    template[key]["value"] = value
                applied_configs.append(key)
                logger.debug(f"✅ Set template[{key}][value] = {value}")
            else:
                unmapped_configs.append(key)
                logger.debug(f"⚠️ Config key '{key}' not found in template")

        # Validate required fields for specific components
        if component_type == "Agent" and "agent_llm" in template:
            # Ensure Azure OpenAI settings are present when using Azure
            if template.get("agent_llm", {}).get("value") == "Azure OpenAI":
                required_azure_fields = ["azure_deployment_name", "azure_api_base", "openai_api_key"]
                missing_fields = [f for f in required_azure_fields if f not in applied_configs and
                                 not template.get(f, {}).get("value")]
                if missing_fields:
                    logger.warning(f"Missing required Azure OpenAI fields for {component.id}: {missing_fields}")

        # Log summary of configuration application
        if applied_configs:
            logger.info(f"Applied {len(applied_configs)} configs to {component.id}: {applied_configs}")
        if unmapped_configs:
            logger.warning(f"Could not map {len(unmapped_configs)} configs for {component.id}: {unmapped_configs}")

    async def _build_edges(self, spec: AgentSpec,
                          nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build edges from provides declarations with fixed logic."""
        logger.debug(f"Building edges for {len(nodes)} nodes")
        edges = []
        node_map = {node["id"]: node for node in nodes}
        logger.debug(f"Node map created with IDs: {list(node_map.keys())}")

        # Process each component's provides declarations
        for component in spec.components:
            if not component.provides:
                logger.debug(f"Component {component.id} has no provides declarations")
                continue

            source_id = component.id
            if source_id not in node_map:
                logger.warning(f"Source node '{source_id}' not found in node map")
                continue

            logger.debug(f"Processing {len(component.provides)} provides for component {source_id}")

            # Process each provides declaration
            for provide in component.provides:
                logger.debug(f"Creating edge: {source_id} → {provide.in_} (useAs: {provide.useAs})")
                edge = self._create_edge_from_provides(
                    source_id, provide, node_map, component
                )
                if edge:
                    edges.append(edge)
                    logger.debug(f"Edge created: {edge['id']}")
                else:
                    logger.warning(f"Failed to create edge: {source_id} → {provide.in_}")

        logger.info(f"Created {len(edges)} edges from {len(spec.components)} components")
        return edges

    def _create_edge_from_provides(self, source_id: str, provide: Any,
                                  node_map: Dict[str, Dict[str, Any]],
                                  source_component: Component) -> Optional[Dict[str, Any]]:
        """Create an edge from provides declaration with FIXED logic."""
        # CRITICAL FIX: Handle Pydantic field alias correctly for "in" field
        # The field is named `in_` but aliased as `in` in YAML
        target_id = provide.in_  # Direct access to the field
        use_as = provide.useAs

        # Debug logging for data access
        logger.debug(f"Provides data access: target_id={target_id}, use_as={use_as}")
        logger.debug(f"Provide object type: {type(provide)}")
        logger.debug(f"Provide object attributes: {dir(provide) if hasattr(provide, '__dict__') else 'No attributes'}")

        if not target_id or not use_as:
            logger.error(f"Invalid provides: target_id={target_id}, use_as={use_as}")
            logger.error(f"Provide object dump: {provide}")
            return None

        if target_id not in node_map:
            logger.error(f"Target node '{target_id}' not found for provides connection")
            logger.debug(f"Available nodes: {list(node_map.keys())}")
            return None

        # Get nodes
        source_node = node_map[source_id]
        target_node = node_map[target_id]

        # Get actual component types
        source_type = source_node["data"]["type"]
        target_type = target_node["data"]["type"]

        # FIXED: Determine output field with improved logic
        output_field = self._determine_output_field_fixed(
            use_as, source_node, source_type, provide
        )
        logger.debug(f"Determined output field: {output_field} for {source_type}")

        # FIXED: Map useAs to correct input field
        input_field = self._map_use_as_to_field_fixed(use_as, target_type)
        logger.debug(f"Mapped useAs '{use_as}' to input field: {input_field} for {target_type}")

        # Get output types
        output_types = self._get_output_types_fixed(source_node, output_field, source_type)
        logger.debug(f"Output types: {output_types}")

        # Get input types
        input_types = self._get_input_types_fixed(target_node, input_field)
        logger.debug(f"Input types: {input_types}")

        # Validate type compatibility with enhanced logging for tool connections
        is_tool_connection = (use_as == "tools" or "Tool" in output_types)

        if is_tool_connection:
            logger.info(f"🔧 Tool Connection Attempt:")
            logger.info(f"  Source: {source_type} ({source_id})")
            logger.info(f"  Target: {target_type} ({target_id})")
            logger.info(f"  UseAs: {use_as}")
            logger.info(f"  Output field: {output_field}")
            logger.info(f"  Output types: {output_types}")
            logger.info(f"  Input field: {input_field}")
            logger.info(f"  Input types: {input_types}")

        validation_result = self._validate_type_compatibility_fixed(
            output_types, input_types, source_type, target_type
        )

        if not validation_result:
            if is_tool_connection:
                logger.error(f"❌ Tool Connection FAILED: {source_type}.{output_field} ({output_types}) "
                           f"-> {target_type}.{input_field} ({input_types})")
                logger.error(f"  Validation details: output_types={output_types}, input_types={input_types}")
            else:
                logger.warning(
                    f"Type mismatch: {source_type}.{output_field} ({output_types}) "
                    f"-> {target_type}.{input_field} ({input_types})"
                )
            return None

        if is_tool_connection:
            logger.info(f"✅ Tool Connection PASSED validation")

        # FIXED: Determine handle type correctly
        handle_type = self._determine_handle_type_fixed(input_field, input_types)

        # Create handle objects
        source_handle = {
            "dataType": source_type,
            "id": source_id,
            "name": output_field,
            "output_types": output_types
        }

        target_handle = {
            "fieldName": input_field,
            "id": target_id,
            "inputTypes": input_types,
            "type": handle_type
        }

        # CRITICAL FIX: Different JSON encoding for edge ID vs handle strings
        # Edge ID: Use compact format (no spaces) - for the ID string
        source_handle_id = json.dumps(source_handle, separators=(",", ":")).replace('"', "œ")
        target_handle_id = json.dumps(target_handle, separators=(",", ":")).replace('"', "œ")

        # Handle strings: Use compact format for sourceHandle/targetHandle fields (FIXED)
        source_handle_encoded = json.dumps(source_handle, separators=(",", ":")).replace('"', "œ")
        target_handle_encoded = json.dumps(target_handle, separators=(",", ":")).replace('"', "œ")

        # CRITICAL FIX: Use correct Langflow edge ID format with full encoded handles
        edge = {
            "className": "",
            "data": {
                "sourceHandle": source_handle,
                "targetHandle": target_handle,
                "label": provide.description or ""
            },
            "id": f"xy-edge__{source_id}{source_handle_encoded}-{target_id}{target_handle_encoded}",
            "selected": False,
            "source": source_id,
            "sourceHandle": source_handle_encoded,
            "target": target_id,
            "targetHandle": target_handle_encoded
        }

        return edge

    def _determine_output_field_fixed(self, use_as: str, source_node: Dict[str, Any],
                                     source_type: str, provide: Any) -> str:
        """FIXED output field determination logic."""
        # Check if specific output is requested
        if provide.fromOutput:
            return provide.fromOutput

        # Get actual outputs from node data first
        outputs = self._get_component_outputs_fixed(source_node)

        # Special case for tools - find the Tool output
        if use_as in ["tool", "tools"]:
            # Look for Tool type output in the component's outputs
            if outputs:
                for output in outputs:
                    if "Tool" in output.get("types", []):
                        return output.get("name", "component_as_tool")
            return "component_as_tool"

        if outputs:
            # For single output, use it
            if len(outputs) == 1:
                return outputs[0].get("name", "output")

            # For multiple outputs, intelligent selection
            if use_as == "input" and any(o.get("name") == "message" for o in outputs):
                return "message"
            elif use_as == "system_prompt" and any(o.get("name") == "prompt" for o in outputs):
                return "prompt"
            elif any(o.get("name") == "response" for o in outputs):
                return "response"
            else:
                return outputs[0].get("name", "output")

        # Component-specific defaults with AutonomizeModel support
        if "ChatInput" in source_type:
            return "message"
        elif "AutonomizeModel" in source_type:
            return "prediction"  # FIXED: AutonomizeModel outputs prediction
        elif "Agent" in source_type:
            return "response"
        elif "Prompt" in source_type or "GenesisPrompt" in source_type:
            return "prompt"
        elif "Memory" in source_type:
            return "memory"
        else:
            return "output"

    def _map_use_as_to_field_fixed(self, use_as: str, target_type: str) -> str:
        """FIXED field mapping with AutonomizeModel support."""
        # Component-specific mappings
        if "AutonomizeModel" in target_type:
            if use_as in ["input", "query", "text"]:
                return "search_query"  # FIXED: AutonomizeModel uses search_query

        # Standard mappings
        field_mappings = {
            "input": "input_value",
            "tool": "tools",
            "tools": "tools",
            "system_prompt": "system_prompt",  # CRITICAL FIX: Agent uses system_prompt, not system_message
            "prompt": "template",
            "query": "search_query",  # For AutonomizeModel
            "llm": "llm",
            "response": "input_value",
            "message": "input_value",
            "text": "input_value",
            "output": "input_value",
            "memory": "memory"
        }

        return field_mappings.get(use_as, use_as)

    def _get_component_outputs_fixed(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """FIXED: Get outputs from correct locations."""
        # Try multiple locations
        outputs = (
            node.get("data", {}).get("outputs", []) or
            node.get("data", {}).get("node", {}).get("outputs", []) or
            []
        )
        return outputs

    def _get_output_types_fixed(self, node: Dict[str, Any], output_field: str,
                               source_type: str) -> List[str]:
        """FIXED output types determination."""
        # Special cases - ALWAYS return Tool for component_as_tool
        if output_field == "component_as_tool":
            return ["Tool"]

        # Check if node is in tool mode - if so, and we're looking at component_as_tool, return Tool
        node_data = node.get("data", {})
        if node_data.get("node", {}).get("tool_mode") and output_field == "component_as_tool":
            return ["Tool"]

        # Check actual outputs
        outputs = self._get_component_outputs_fixed(node)
        for output in outputs:
            if output.get("name") == output_field:
                types = output.get("types", [])
                if types:
                    return types

        # Component-specific defaults
        if "AutonomizeModel" in source_type:
            return ["Data"]  # FIXED: AutonomizeModel outputs Data
        elif "ChatInput" in source_type or "ChatOutput" in source_type:
            return ["Message"]
        elif "Agent" in source_type:
            return ["Message"]
        elif "Prompt" in source_type:
            return ["Message"]
        elif "Tool" in output_field:
            return ["Tool"]
        else:
            return ["Message"]

    def _get_input_types_fixed(self, node: Dict[str, Any], input_field: str) -> List[str]:
        """FIXED input types determination."""
        # Check template for input types
        template = node.get("data", {}).get("node", {}).get("template", {})
        if input_field in template and isinstance(template[input_field], dict):
            input_types = template[input_field].get("input_types", [])
            if input_types:
                return input_types

        # Default types based on field name
        field_type_map = {
            "tools": ["Tool"],
            "input_value": ["Data", "DataFrame", "Message"],  # ChatOutput accepts multiple
            "search_query": ["Message", "str"],  # AutonomizeModel
            "system_prompt": ["Message"],
            "template": ["Message", "str"],
            "memory": ["Message"]
        }

        return field_type_map.get(input_field, ["Message", "str"])

    def _determine_handle_type_fixed(self, input_field: str, input_types: List[str]) -> str:
        """FIXED handle type determination - CRITICAL FIX."""
        # Tools always use "other"
        if input_field == "tools" or "Tool" in input_types:
            return "other"

        # CRITICAL FIX: ChatOutput input_value accepts multiple types -> "other" not "str"
        if input_field == "input_value" and len(input_types) > 1:
            return "other"

        # Multiple types use "other"
        if len(input_types) > 1:
            return "other"

        # Single Message type uses "str"
        if input_types == ["Message"]:
            return "str"

        # Data/DataFrame use "other"
        if "Data" in input_types or "DataFrame" in input_types:
            return "other"

        # Single type uses the type name
        if len(input_types) == 1:
            return input_types[0].lower()

        return "str"

    def _validate_type_compatibility_fixed(self, output_types: List[str],
                                          input_types: List[str],
                                          source_type: str, target_type: str) -> bool:
        """FIXED type compatibility validation with detailed logging."""
        # Log validation attempt
        is_tool_validation = "Tool" in output_types or "Tool" in input_types
        if is_tool_validation:
            logger.debug(f"🔍 Validating Tool compatibility:")
            logger.debug(f"   Output types: {output_types}")
            logger.debug(f"   Input types: {input_types}")

        # Tool connections
        if "Tool" in output_types and "Tool" in input_types:
            if is_tool_validation:
                logger.debug(f"   ✓ Tool-to-Tool match found")
            return True

        # Direct type matches
        if any(otype in input_types for otype in output_types):
            if is_tool_validation:
                logger.debug(f"   ✓ Direct type match found")
            return True

        # AutonomizeModel Data -> input_value compatibility
        if "Data" in output_types and "input_value" in str(input_types):
            if is_tool_validation:
                logger.debug(f"   ✓ Data-to-input_value compatibility")
            return True

        # Compatible conversions
        compatible = {
            "Message": ["str", "text", "Text", "Data"],
            "str": ["Message", "text", "Text"],
            "Data": ["dict", "object", "any", "Message"],
            "DataFrame": ["Data", "object", "any"]
        }

        for otype in output_types:
            if otype in compatible:
                if any(ctype in input_types for ctype in compatible[otype]):
                    if is_tool_validation:
                        logger.debug(f"   ✓ Compatible conversion: {otype} -> {[c for c in compatible[otype] if c in input_types]}")
                    return True

        # Accept any/object inputs
        if "any" in input_types or "object" in input_types:
            if is_tool_validation:
                logger.debug(f"   ✓ Any/object input accepts all")
            return True

        if is_tool_validation:
            logger.debug(f"   ✗ No compatibility found")
            logger.debug(f"   Checked: Tool match, Direct match, Data compatibility, Conversions, Any/object")

        return False

    def _calculate_position(self, index: int, kind: str) -> Dict[str, int]:
        """Calculate node position based on intelligent graph-based layout algorithm."""
        # If positions haven't been pre-calculated, calculate them now
        if not hasattr(self, '_component_positions'):
            self._calculate_all_positions()

        # Use pre-calculated positions from graph-based layout
        component_id = getattr(self, '_current_component_id', None)
        if component_id and component_id in self._component_positions:
            return self._component_positions[component_id]

        # Fallback to simple positioning
        return self._calculate_simple_position(index, kind)

    def _calculate_all_positions(self):
        """Calculate positions for all components using graph-based layout algorithm."""
        from collections import defaultdict, deque

        if not hasattr(self, '_current_spec'):
            self._component_positions = {}
            return

        spec = self._current_spec
        components = {comp.id: comp for comp in spec.components}

        # Build dependency graph from provides relationships
        graph = defaultdict(list)
        reverse_graph = defaultdict(list)

        for component in spec.components:
            comp_id = component.id
            provides = component.provides or []

            for provide in provides:
                target = provide.in_
                graph[comp_id].append(target)
                reverse_graph[target].append(comp_id)

        # Calculate topological layers using Kahn's algorithm
        in_degree = {comp_id: 0 for comp_id in components}
        for comp_id in components:
            for target in graph[comp_id]:
                if target in in_degree:
                    in_degree[target] += 1

        # Assign components to layers
        layers = {}
        queue = deque([(comp_id, 0) for comp_id, degree in in_degree.items() if degree == 0])

        while queue:
            comp_id, layer = queue.popleft()
            layers[comp_id] = layer

            for target in graph[comp_id]:
                if target in in_degree:
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append((target, layer + 1))

        # Group components by layer
        layer_groups = defaultdict(list)
        for comp_id, layer in layers.items():
            layer_groups[layer].append(comp_id)

        # Calculate positions using layout rules
        self._component_positions = {}

        # Layout parameters based on starter project analysis
        BASE_X = 100
        LAYER_GAP = 400  # 400px between layers (matches starter projects)
        BASE_Y = 100     # Start from top
        VERTICAL_BUFFER = 150  # Optimized gap between nodes for compact layout
        SPREAD_GAP = 80  # Horizontal spread within layer

        for layer_num in sorted(layer_groups.keys()):
            layer_comps = layer_groups[layer_num]
            layer_x = BASE_X + layer_num * LAYER_GAP

            # Sort components by kind for consistent vertical order
            kind_order = ['Prompt', 'Data', 'Tool', 'Model', 'Agent']
            by_kind = defaultdict(list)
            for comp_id in layer_comps:
                component = components[comp_id]
                by_kind[component.kind].append(comp_id)

            # Position components within the layer using actual heights
            current_y = BASE_Y

            for kind in kind_order:
                if kind not in by_kind:
                    continue

                kind_comps = by_kind[kind]

                for i, comp_id in enumerate(kind_comps):
                    component = components[comp_id]

                    # Get actual node height for this component
                    node_height = self._get_node_height(component.kind)

                    # For multiple components of same kind, spread horizontally
                    spread_offset = i * SPREAD_GAP if len(kind_comps) > 1 else 0

                    self._component_positions[comp_id] = {
                        'x': layer_x + spread_offset,
                        'y': current_y
                    }

                    # Move current_y down for next component (node height + buffer)
                    current_y += node_height + VERTICAL_BUFFER

    def _calculate_simple_position(self, index: int, kind: str) -> Dict[str, int]:
        """Fallback positioning with improved coordinates and spacing."""
        # Detect if this is an output component based on ID
        component_id = getattr(self, '_current_component_id', '')
        is_output = 'output' in component_id.lower() or 'result' in component_id.lower()

        # Use larger coordinate system similar to working starter projects
        category_columns = {
            "Data": 1700 if is_output else 150,  # Outputs on far right, inputs on left
            "Tool": 350,      # Tools slightly right of inputs
            "Prompt": 900,    # Prompts positioned above/near agents
            "Agent": 1300,    # Agents in center-right
            "Model": 1300,    # Models same as agents
        }

        base_x = category_columns.get(kind, 500)
        base_y = 350  # Center vertically

        # Improved spacing for multiple components of same type
        HORIZONTAL_SPREAD = 120  # Spread multiple tools horizontally
        VERTICAL_SPREAD = 500    # Stack vertically with larger gaps

        # For stacking: alternate above/below center, then move outward
        if index == 0:
            offset_x, offset_y = 0, 0
        elif index == 1:
            offset_x, offset_y = HORIZONTAL_SPREAD, -VERTICAL_SPREAD
        elif index == 2:
            offset_x, offset_y = HORIZONTAL_SPREAD * 2, VERTICAL_SPREAD
        elif index == 3:
            offset_x, offset_y = HORIZONTAL_SPREAD * 3, -VERTICAL_SPREAD * 2
        else:
            # For many components, use grid pattern
            offset_x = (index % 4) * HORIZONTAL_SPREAD
            offset_y = ((index // 4) - 1) * VERTICAL_SPREAD

        return {
            "x": base_x + offset_x,
            "y": base_y + offset_y
        }

    def _get_node_height(self, kind: str) -> int:
        """Get node height based on kind - optimized for compact layout."""
        heights = {
            "Agent": 300,  # Reduced from 500px
            "Prompt": 180, # Reduced from 300px
            "Tool": 200,   # Reduced from 350px
            "Model": 180,  # Reduced from 400px
            "Data": 150    # Reduced from 250px
        }
        return heights.get(kind, 200)  # Default reduced from 350px

    def _is_component_used_as_tool(self, component: Component) -> bool:
        """Check if component is used as a tool based on provides declarations and asTools flag."""
        # Check asTools flag first
        if hasattr(component, 'asTools') and component.asTools:
            return True

        # Check provides declarations
        if component.provides:
            return any(p.useAs in ["tool", "tools"] for p in component.provides)

        return False

    async def _get_component_template(self, component_type: str) -> Optional[Dict[str, Any]]:
        """Get real component template from Langflow component registry."""
        try:
            # Get template from the real component template service
            service = _get_component_template_service()
            if not service:
                return None
            template = await service.get_component_template(component_type)

            if template:
                logger.debug(f"Found template for component: {component_type}")
                return template
            else:
                logger.warning(f"No template found for component type: {component_type}, creating fallback")
                # Return a robust fallback template based on component type
                return self._create_fallback_template(component_type)

        except Exception as e:
            logger.error(f"Error getting component template for {component_type}: {e}")
            # Return basic fallback on error
            return self._create_fallback_template(component_type)

    def _create_fallback_template(self, component_type: str) -> Dict[str, Any]:
        """Create a fallback template for unknown components with comprehensive fields."""
        # Component-specific fallbacks with proper fields
        if "Input" in component_type:
            return {
                "outputs": [{"name": "message", "types": ["Message"]}],
                "template": {
                    "input_value": {"input_types": [], "type": "str", "display_name": "Text"},
                    "sender": {"input_types": [], "type": "str", "display_name": "Sender"},
                    "sender_name": {"input_types": [], "type": "str", "display_name": "Sender Name"},
                    "should_store_message": {"input_types": [], "type": "bool", "display_name": "Store Messages"}
                },
                "base_classes": [component_type],
                "description": f"Input component: {component_type}",
                "display_name": component_type
            }
        elif "Output" in component_type:
            return {
                "outputs": [{"name": "message", "types": ["Message"]}],
                "template": {
                    "input_value": {"input_types": ["Message", "Text"], "display_name": "Input"},
                    "sender": {"input_types": [], "type": "str", "display_name": "Sender"},
                    "sender_name": {"input_types": [], "type": "str", "display_name": "Sender Name"},
                    "should_store_message": {"input_types": [], "type": "bool", "display_name": "Store Messages"}
                },
                "base_classes": [component_type],
                "description": f"Output component: {component_type}",
                "display_name": component_type
            }
        elif "Agent" in component_type or "AutonomizeAgent" in component_type:
            # Comprehensive agent template with all LLM configuration fields
            return {
                "outputs": [{"name": "response", "types": ["Message"]}],
                "template": {
                    # Core inputs
                    "input_value": {"input_types": ["Message"], "display_name": "Input"},
                    "system_prompt": {"input_types": ["Message"], "display_name": "System Prompt", "value": ""},
                    "tools": {"input_types": ["Tool"], "display_name": "Tools", "list": True},

                    # LLM Configuration - Model selection
                    "agent_llm": {"type": "str", "display_name": "Model Provider", "value": "Azure OpenAI"},

                    # Azure OpenAI specific fields
                    "azure_deployment_name": {"type": "str", "display_name": "Azure Deployment", "value": ""},
                    "azure_api_base": {"type": "str", "display_name": "Azure Endpoint", "value": ""},
                    "azure_api_version": {"type": "str", "display_name": "API Version", "value": "2024-02-15-preview"},

                    # OpenAI fields
                    "openai_api_key": {"type": "str", "display_name": "API Key", "password": True, "value": ""},
                    "model_name": {"type": "str", "display_name": "Model Name", "value": "gpt-4"},

                    # Common LLM parameters
                    "temperature": {"type": "float", "display_name": "Temperature", "value": 0.7},
                    "max_tokens": {"type": "int", "display_name": "Max Tokens", "value": 2000},
                    "top_p": {"type": "float", "display_name": "Top P", "value": 1.0},
                    "frequency_penalty": {"type": "float", "display_name": "Frequency Penalty", "value": 0.0},
                    "presence_penalty": {"type": "float", "display_name": "Presence Penalty", "value": 0.0},
                    "stream": {"type": "bool", "display_name": "Stream", "value": False},

                    # Memory settings
                    "memory": {"input_types": [], "display_name": "Memory", "value": None}
                },
                "base_classes": [component_type],
                "description": f"Agent component: {component_type}",
                "display_name": component_type
            }
        elif "Prompt" in component_type or "prompt" in component_type.lower():
            # Prompt template with proper fields
            return {
                "outputs": [{"name": "prompt", "types": ["Message"]}],
                "template": {
                    "template": {"type": "str", "display_name": "Template", "value": ""},
                    "input_variables": {"type": "list", "display_name": "Input Variables", "value": []},
                    "partial_variables": {"type": "dict", "display_name": "Partial Variables", "value": {}},
                    "validate_template": {"type": "bool", "display_name": "Validate Template", "value": True}
                },
                "base_classes": [component_type],
                "description": f"Prompt component: {component_type}",
                "display_name": component_type
            }
        elif "Tool" in component_type or "MCP" in component_type:
            # Comprehensive MCP/Tool template
            return {
                "outputs": [{"name": "component_as_tool", "types": ["Tool"]}],
                "template": {
                    # MCP Tool specific fields
                    "tool_names": {"type": "str", "display_name": "Tool Name", "value": ""},
                    "tool_description": {"type": "str", "display_name": "Tool Description", "value": ""},

                    # STDIO mode fields
                    "command": {"type": "str", "display_name": "Command", "value": ""},
                    "args": {"type": "list", "display_name": "Arguments", "value": []},
                    "env": {"type": "dict", "display_name": "Environment", "value": {}},

                    # SSE mode fields
                    "connection_mode": {"type": "str", "display_name": "Connection Mode", "value": "stdio"},
                    "url": {"type": "str", "display_name": "URL", "value": ""},
                    "headers": {"type": "dict", "display_name": "Headers", "value": {}},
                    "timeout_seconds": {"type": "int", "display_name": "Timeout", "value": 30},
                    "sse_read_timeout_seconds": {"type": "int", "display_name": "SSE Timeout", "value": 60},

                    # Mock response for development
                    "mock_response": {"type": "dict", "display_name": "Mock Response", "value": {}}
                },
                "base_classes": [component_type],
                "description": f"Tool component: {component_type}",
                "display_name": component_type
            }
        elif "API" in component_type or "Request" in component_type or "HTTP" in component_type:
            # API Request template with all HTTP fields
            return {
                "outputs": [{"name": "response", "types": ["Data"]}],
                "template": {
                    "method": {"type": "str", "display_name": "Method", "value": "GET"},
                    "url_input": {"type": "str", "display_name": "URL", "value": ""},
                    "headers": {"type": "list", "display_name": "Headers", "value": []},
                    "body": {"type": "dict", "display_name": "Body", "value": {}},
                    "params": {"type": "dict", "display_name": "Query Params", "value": {}},
                    "timeout": {"type": "int", "display_name": "Timeout", "value": 30},
                    "follow_redirects": {"type": "bool", "display_name": "Follow Redirects", "value": True},
                    "verify": {"type": "bool", "display_name": "Verify SSL", "value": True}
                },
                "base_classes": [component_type],
                "description": f"API component: {component_type}",
                "display_name": component_type
            }
        elif "File" in component_type or "Document" in component_type:
            # File/Document component template
            return {
                "outputs": [{"name": "data", "types": ["Data"]}],
                "template": {
                    "file_path": {"type": "str", "display_name": "File Path", "value": ""},
                    "file_type": {"type": "str", "display_name": "File Type", "value": ""},
                    "parse_content": {"type": "bool", "display_name": "Parse Content", "value": True}
                },
                "base_classes": [component_type],
                "description": f"File component: {component_type}",
                "display_name": component_type
            }
        else:
            # Generic fallback with common fields
            return {
                "outputs": [{"name": "output", "types": ["Any"]}],
                "template": {
                    "input_value": {"input_types": ["Any"], "display_name": "Input"},
                    "config": {"type": "dict", "display_name": "Configuration", "value": {}}
                },
                "base_classes": [component_type],
                "description": f"Generic component: {component_type}",
                "display_name": component_type
            }
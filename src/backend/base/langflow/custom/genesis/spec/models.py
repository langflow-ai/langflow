"""Agent Specification Models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ComponentProvides(BaseModel):
    """Declares how a component provides data to other components."""

    useAs: str = Field(
        ...,
        description="The field name in the target component (e.g., 'tools', 'input', 'system_prompt')"
    )
    in_: str = Field(
        ...,
        alias="in",
        description="The ID of the target component"
    )
    description: Optional[str] = Field(
        None,
        description="Human-readable description of this connection"
    )
    fromOutput: Optional[str] = Field(
        None,
        description="Specific output to use when component has multiple outputs"
    )

    class Config:
        """Allow 'in' as field name."""
        populate_by_name = True


class Component(BaseModel):
    """Component definition in agent specification."""

    id: str
    name: str
    kind: str
    type: str
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    provides: Optional[List[ComponentProvides]] = None
    asTools: Optional[bool] = Field(
        False,
        description="Whether this component can be used as a tool"
    )
    modelEndpoint: Optional[str] = None


class Variable(BaseModel):
    """Variable definition for runtime configuration."""

    name: str
    type: str = "string"
    required: bool = False
    default: Optional[Any] = None
    description: Optional[str] = None


class KPI(BaseModel):
    """Key Performance Indicator definition."""

    name: str
    category: str
    valueType: str
    target: Any
    unit: Optional[str] = None
    description: Optional[str] = None


class SecurityInfo(BaseModel):
    """Security and compliance information."""

    visibility: str = "Private"
    confidentiality: str = "High"
    gdprSensitive: bool = False


class ReusabilityInfo(BaseModel):
    """Reusability configuration."""

    asTools: bool = False
    standalone: bool = True
    provides: Optional[Dict[str, Any]] = None
    dependencies: Optional[List[Dict[str, str]]] = None


class AgentSpec(BaseModel):
    """Complete agent specification model."""

    id: str
    name: str
    fullyQualifiedName: Optional[str] = None
    description: str
    domain: Optional[str] = None
    subDomain: Optional[str] = None
    version: Optional[str] = "1.0.0"
    environment: Optional[str] = "production"
    agentOwner: Optional[str] = None
    agentOwnerDisplayName: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = "ACTIVE"

    # Core configuration
    kind: str = "Single Agent"  # Single Agent, Multi Agent, Orchestrator
    agentGoal: str
    targetUser: Optional[str] = "internal"
    valueGeneration: Optional[str] = "ProcessAutomation"
    interactionMode: Optional[str] = "RequestResponse"
    runMode: Optional[str] = "RealTime"
    agencyLevel: Optional[str] = "ModelDrivenWorkflow"
    toolsUse: Optional[bool] = False
    learningCapability: Optional[str] = "None"

    # Components and configuration
    components: List[Component]
    variables: Optional[List[Variable]] = None
    tags: Optional[List[str]] = None

    # Performance and compliance
    kpis: Optional[List[KPI]] = None
    securityInfo: Optional[SecurityInfo] = None
    outputs: Optional[List[str]] = None

    # Reusability
    reusability: Optional[ReusabilityInfo] = None

    # Sample data
    sampleInput: Optional[Dict[str, Any]] = None
    promptConfiguration: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSpec":
        """Create AgentSpec from dictionary."""
        # Generate ID if not present
        if "id" not in data:
            import uuid
            data["id"] = str(uuid.uuid4())

        # Handle components - support both list and dict formats
        if "components" in data:
            if isinstance(data["components"], list):
                # List format: components are already in list form
                data["components"] = [
                    cls._create_component_from_dict(comp) if isinstance(comp, dict) else comp
                    for comp in data["components"]
                ]
            elif isinstance(data["components"], dict):
                # Dict format: components are keyed by ID (YAML format)
                components_list = []
                for comp_id, comp_data in data["components"].items():
                    if isinstance(comp_data, dict):
                        # Add the ID to the component data
                        comp_dict = dict(comp_data)
                        comp_dict["id"] = comp_id
                        # Add name if not present (use ID as fallback)
                        if "name" not in comp_dict:
                            comp_dict["name"] = comp_id
                        components_list.append(cls._create_component_from_dict(comp_dict))
                    else:
                        components_list.append(comp_data)
                data["components"] = components_list

        # Handle variables
        if "variables" in data and isinstance(data["variables"], list):
            data["variables"] = [
                Variable(**var) if isinstance(var, dict) else var
                for var in data["variables"]
            ]

        # Handle KPIs
        if "kpis" in data and isinstance(data["kpis"], list):
            data["kpis"] = [
                KPI(**kpi) if isinstance(kpi, dict) else kpi
                for kpi in data["kpis"]
            ]

        # Handle security info
        if "securityInfo" in data and isinstance(data["securityInfo"], dict):
            data["securityInfo"] = SecurityInfo(**data["securityInfo"])

        # Handle reusability
        if "reusability" in data and isinstance(data["reusability"], dict):
            data["reusability"] = ReusabilityInfo(**data["reusability"])

        # Helper function to parse JSON strings
        import json
        import logging
        logger = logging.getLogger(__name__)

        def parse_json_field(field_name: str) -> None:
            """Parse a field that might be a JSON string into a dict."""
            if field_name in data and data[field_name]:
                field_value = data[field_name]
                if isinstance(field_value, str):
                    try:
                        data[field_name] = json.loads(field_value)
                        logger.debug(f"Parsed {field_name} from JSON string to dict")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse {field_name} JSON string: {e}")
                        data[field_name] = None

        # Parse JSON string fields that expect dicts
        parse_json_field("sampleInput")
        parse_json_field("promptConfiguration")

        return cls(**data)

    @classmethod
    def _create_component_from_dict(cls, comp_dict: Dict[str, Any]) -> Component:
        """Create a Component from dict, mapping type to kind."""
        # Create a copy to avoid modifying the original
        comp_data = dict(comp_dict)

        # Map type to kind for positioning and categorization
        comp_type = comp_data.get("type", "")
        kind = cls._map_type_to_kind(comp_type)
        comp_data["kind"] = kind

        # Handle provides field - convert string format to object format
        if "provides" in comp_data and comp_data["provides"]:
            provides_list = comp_data["provides"]
            if isinstance(provides_list, list):
                normalized_provides = []
                for provide_item in provides_list:
                    if isinstance(provide_item, str):
                        # Convert shorthand string format to object format
                        # String format like 'text' or 'json' means output type
                        # We'll create a minimal ComponentProvides object
                        # The actual target component will be resolved during edge creation
                        normalized_provides.append({
                            "useAs": provide_item,
                            "in": "_auto_"  # Placeholder, will be resolved by converter
                        })
                    elif isinstance(provide_item, dict):
                        # Already in object format, keep as-is
                        normalized_provides.append(provide_item)
                comp_data["provides"] = normalized_provides

        return Component(**comp_data)

    @classmethod
    def _map_type_to_kind(cls, comp_type: str) -> str:
        """Map component type to kind for positioning."""
        # Extract base type (remove genesis: prefix)
        base_type = comp_type.replace("genesis:", "") if comp_type.startswith("genesis:") else comp_type

        # Mapping from type to kind
        type_to_kind = {
            # Data/Input components
            "chat_input": "Data",
            "json_input": "Data",
            "file_input": "Data",
            "chat_output": "Data",
            "json_output": "Data",

            # Agent components
            "agent": "Agent",
            "autonomize_agent": "Agent",

            # Prompt components
            "prompt": "Prompt",
            "prompt_template": "Prompt",
            "genesis_prompt": "Prompt",

            # Tool components
            "calculator": "Tool",
            "knowledge_hub_search": "Tool",
            "pa_lookup": "Tool",
            "eligibility_component": "Tool",
            "encoder_pro": "Tool",
            "qnext_auth_history": "Tool",
            "api_component": "Tool",
            "form_recognizer": "Tool",

            # Model components
            "rxnorm": "Model",
            "icd10": "Model",
            "cpt": "Model",
            "cpt_code": "Model",
            "clinical_llm": "Model",
            "clinical_note_classifier": "Model",
            "combined_entity_linking": "Model",
            "openai": "Model",
            "azure_openai": "Model",
            "anthropic": "Model",

            # MCP components
            "mcp_tool": "Tool",
            "mcp_client": "Tool",
            "mcp_server": "Tool",

            # Memory components
            "memory": "Data",
            "conversation_memory": "Data",

            # Vector store components
            "vector_store": "Data",
            "qdrant": "Data",
            "faiss": "Data",

            # CrewAI components
            "sequential_crew": "Agent",
            "hierarchical_crew": "Agent"
        }

        return type_to_kind.get(base_type, "Data")  # Default to Data for unknown types

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump(exclude_none=True, by_alias=True)
# Path: src/backend/base/langflow/services/specification/models.py

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class VariableDefinition(BaseModel):
    """Runtime variable definition with type safety"""
    name: str
    type: Literal["string", "integer", "float", "boolean", "array", "object"]
    required: bool = False
    default: Optional[Any] = None
    description: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None  # JSON Schema validation


class EnhancedKPI(BaseModel):
    """KPI with full metadata"""
    name: str
    description: str
    category: Optional[Literal["Quality", "Performance", "Business", "Efficiency"]] = None
    value_type: Optional[Literal["percentage", "numeric", "boolean", "duration"]] = None
    target: Optional[Union[str, float, int]] = None
    unit: Optional[str] = None
    aggregation: Optional[Literal["sum", "avg", "max", "min", "p95", "p99"]] = None


class ComponentSpec(BaseModel):
    """Component specification with provides pattern"""
    id: str
    name: Optional[str] = None
    kind: Optional[str] = None
    type: str
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    provides: Optional[List[Dict[str, Any]]] = None


class ReusabilityConfig(BaseModel):
    """Reusability configuration"""
    as_tools: Optional[bool] = None
    standalone: Optional[bool] = None
    provides: Optional[Dict[str, Any]] = None
    dependencies: Optional[List[str]] = None


class SecurityInfo(BaseModel):
    """Security configuration"""
    data_classification: Optional[str] = None
    hipaa_compliant: Optional[bool] = None
    encryption_required: Optional[bool] = None
    access_controls: Optional[List[str]] = None
    confidence: Optional[float] = None
    source: Optional[str] = None
    analysis_metadata: Optional[Dict[str, Any]] = None


class EnhancedAgentSpec(BaseModel):
    """Enhanced agent specification model compatible with genesis-agent-cli"""

    # Core Identity
    id: str = Field(..., pattern=r"^urn:agent:genesis:[a-z0-9_]+:[0-9]+$")
    name: str
    description: str
    version: str = Field(default="1.0.0", pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")

    # Ownership & Classification
    domain: str
    subdomain: Optional[str] = None
    owner: str  # Email address
    fully_qualified_name: Optional[str] = None
    status: Literal["ACTIVE", "INACTIVE", "DEPRECATED"] = "ACTIVE"

    # Agent Configuration
    goal: str  # Agent's primary objective
    kind: Literal["Single Agent", "Multi Agent", "Orchestrator"] = "Single Agent"
    target_user: Literal["internal", "external", "both"] = "internal"
    value_generation: Literal["ProcessAutomation", "InsightGeneration", "DecisionSupport", "ContentCreation"]
    interaction_mode: Literal["RequestResponse", "MultiTurnConversation", "Streaming", "Batch"]
    run_mode: Literal["RealTime", "Scheduled", "EventDriven"]
    agency_level: Literal["StaticWorkflow", "ModelDrivenWorkflow", "AdaptiveWorkflow", "Autonomous"]
    uses_tools: bool = True
    learning_capability: Literal["None", "Contextual", "Persistent", "Continuous"] = "None"

    # Components using the "provides" pattern
    components: List[ComponentSpec] = []
    variables: Optional[List[VariableDefinition]] = None
    sample_input: Optional[Dict[str, Any]] = None
    expected_output: Optional[Dict[str, Any]] = None

    # Multi-agent Support
    reusability: Optional[ReusabilityConfig] = None
    dependencies: Optional[List[str]] = None

    # Metrics & Outputs
    outputs: Optional[List[str]] = None
    kpis: Optional[List[EnhancedKPI]] = None

    # Metadata
    tags: List[str] = []
    security_info: Optional[SecurityInfo] = None

    # Search & Discovery (computed fields)
    search_keywords: Optional[List[str]] = None
    reusability_score: Optional[float] = None
    complexity_score: Optional[float] = None

    def to_yaml(self) -> str:
        """Convert specification to YAML format"""
        import yaml
        return yaml.dump(self.model_dump(exclude_none=True), default_flow_style=False)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "EnhancedAgentSpec":
        """Create specification from YAML content"""
        import yaml
        data = yaml.safe_load(yaml_content)
        return cls(**data)


class SpecificationQuery(BaseModel):
    """Advanced search query with multiple filter types"""
    text_query: Optional[str] = None
    domains: Optional[List[str]] = None
    kinds: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    component_types: Optional[List[str]] = None
    min_reusability_score: Optional[float] = None
    target_users: Optional[List[str]] = None
    value_generations: Optional[List[str]] = None
    interaction_modes: Optional[List[str]] = None
    run_modes: Optional[List[str]] = None
    sort_by: str = "relevance"  # relevance, created_at, reusability_score, name
    sort_order: Literal["asc", "desc"] = "desc"
    limit: int = 20
    offset: int = 0


class SpecificationSummary(BaseModel):
    """Summarized specification for search results"""
    id: UUID
    name: str
    version: str
    description: Optional[str]
    domain: str
    subdomain: Optional[str]
    owner: str
    goal: str
    kind: str
    target_user: str
    tags: List[str]
    reusability_score: Optional[float]
    complexity_score: Optional[float]
    created_at: datetime
    updated_at: datetime
    component_count: Optional[int] = None
    usage_count: Optional[int] = None


class SimilarityMatch(BaseModel):
    """Similar specification match"""
    specification: SpecificationSummary
    similarity_score: float
    match_reasons: List[str]
    shared_components: List[str]
    shared_tags: List[str]


class ComponentPattern(BaseModel):
    """Reusable component pattern"""
    component_type: str
    usage_frequency: int
    common_configs: Dict[str, Any]
    typical_provides: List[Dict[str, Any]]
    description: str
    domains: List[str]


class WorkflowPattern(BaseModel):
    """Common workflow pattern"""
    pattern_name: str
    description: str
    component_sequence: List[str]
    usage_frequency: int
    domains: List[str]
    example_specs: List[str]


class ReusableComponent(BaseModel):
    """Reusable component definition"""
    component_id: str
    component_type: str
    config_template: Dict[str, Any]
    provides_template: List[Dict[str, Any]]
    reusability_score: float
    usage_count: int
    source_specs: List[str]


class ResearchResults(BaseModel):
    """Results from specification research"""
    similar_agents: List[SpecificationSummary]
    available_tools: List[Dict[str, Any]]
    flow_patterns: List[WorkflowPattern]
    healthcare_patterns: List[ComponentPattern]
    reusable_components: List[ReusableComponent]


class AgentRequirements(BaseModel):
    """Agent requirements extracted from natural language"""
    primary_goal: str
    domain: str
    use_case: str
    integration_points: List[str]
    required_tools: List[str]
    workflow_type: str
    performance_requirements: Dict[str, Any]
    critical_components: List[str]


class ConversionStrategy(BaseModel):
    """Strategy for converting flows to specifications"""
    strategy_type: Literal["metadata_restoration", "reverse_engineering", "hybrid"]
    confidence_score: float
    available_metadata: Dict[str, Any]
    detected_patterns: List[str]


class ConversionResult(BaseModel):
    """Result of flow to specification conversion"""
    success: bool
    specification: Optional[EnhancedAgentSpec]
    strategy_used: ConversionStrategy
    warnings: List[str]
    errors: List[str]


class ConversionRequest(BaseModel):
    """Request model for specification to flow conversion."""
    specification: Dict[str, Any]
    name: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    tweaks: Optional[Dict[str, Any]] = None


class SpecificationAnalytics(BaseModel):
    """Analytics for a specification"""
    spec_id: UUID
    total_views: int
    total_copies: int
    total_reuses: int
    reusability_score: float
    complexity_score: float
    popular_components: List[str]
    usage_trends: Dict[str, Any]
    similar_specs: List[UUID]
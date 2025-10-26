"""
Component Models for the Dynamic Agent Specification Framework.

This module defines data models for component mappings, component definitions,
and component-related metadata with comprehensive type safety.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Union
from dataclasses import dataclass, field
from enum import Enum


class ComponentKind(Enum):
    """Standard component kinds in the specification framework."""
    AGENT = "Agent"
    TOOL = "Tool"
    DATA = "Data"
    PROMPT = "Prompt"
    MODEL = "Model"
    MEMORY = "Memory"
    CUSTOM = "Custom"
    CONNECTOR = "Connector"
    PROCESSOR = "Processor"


class ComponentStatus(Enum):
    """Component status for tracking lifecycle."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"
    BETA = "beta"
    STABLE = "stable"


@dataclass
class ComponentMapping:
    """
    Represents the mapping between Genesis component types and Langflow components.

    Attributes:
        genesis_type: Genesis component type identifier
        langflow_component: Target Langflow component class
        base_classes: Langflow base classes for the component
        input_types: Supported input data types
        output_types: Supported output data types
        template_fields: Default template field configurations
        configuration_schema: JSON schema for component configuration
        io_mapping: Input/output field mappings
        constraints: Component usage constraints
        performance_hints: Performance optimization hints
        healthcare_compliant: Whether component is healthcare/HIPAA compliant
        metadata: Additional component metadata
    """
    genesis_type: str
    langflow_component: str
    base_classes: List[str] = field(default_factory=lambda: ["Component"])
    input_types: List[str] = field(default_factory=lambda: ["Message", "Data"])
    output_types: List[str] = field(default_factory=lambda: ["Message", "Data"])
    template_fields: Dict[str, Any] = field(default_factory=dict)
    configuration_schema: Dict[str, Any] = field(default_factory=dict)
    io_mapping: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    performance_hints: Dict[str, str] = field(default_factory=dict)
    healthcare_compliant: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert component mapping to dictionary representation."""
        return {
            "genesis_type": self.genesis_type,
            "langflow_component": self.langflow_component,
            "base_classes": self.base_classes,
            "input_types": self.input_types,
            "output_types": self.output_types,
            "template_fields": self.template_fields,
            "configuration_schema": self.configuration_schema,
            "io_mapping": self.io_mapping,
            "constraints": self.constraints,
            "performance_hints": self.performance_hints,
            "healthcare_compliant": self.healthcare_compliant,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentMapping':
        """Create ComponentMapping from dictionary."""
        return cls(
            genesis_type=data["genesis_type"],
            langflow_component=data["langflow_component"],
            base_classes=data.get("base_classes", ["Component"]),
            input_types=data.get("input_types", ["Message", "Data"]),
            output_types=data.get("output_types", ["Message", "Data"]),
            template_fields=data.get("template_fields", {}),
            configuration_schema=data.get("configuration_schema", {}),
            io_mapping=data.get("io_mapping", {}),
            constraints=data.get("constraints", []),
            performance_hints=data.get("performance_hints", {}),
            healthcare_compliant=data.get("healthcare_compliant", False),
            metadata=data.get("metadata", {})
        )


@dataclass
class WorkflowComponent:
    """
    Represents a component within a workflow specification.

    Attributes:
        id: Unique component identifier
        name: Human-readable component name
        type: Genesis component type
        kind: Component kind/category
        description: Component description
        config: Component configuration
        provides: List of output relationships
        metadata: Component metadata
        position: Position information for UI layout
        as_tools: Whether component can be used as tools
        status: Component lifecycle status
        created_at: Component creation timestamp
        updated_at: Component last update timestamp
    """
    id: str
    type: str
    name: Optional[str] = None
    kind: Union[ComponentKind, str] = ComponentKind.CUSTOM
    description: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    provides: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    position: Optional[Dict[str, Union[int, float]]] = None
    as_tools: bool = False
    status: Union[ComponentStatus, str] = ComponentStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Post-initialization processing."""
        if isinstance(self.kind, str):
            try:
                self.kind = ComponentKind(self.kind)
            except ValueError:
                pass  # Keep as string if not in enum

        if isinstance(self.status, str):
            try:
                self.status = ComponentStatus(self.status)
            except ValueError:
                pass  # Keep as string if not in enum

        if self.name is None:
            self.name = self.id

    @property
    def provides_count(self) -> int:
        """Get number of output relationships."""
        return len(self.provides)

    @property
    def has_configuration(self) -> bool:
        """Check if component has configuration."""
        return bool(self.config)

    @property
    def is_healthcare_component(self) -> bool:
        """Check if component is healthcare-related."""
        healthcare_indicators = ["ehr", "medical", "patient", "phi", "healthcare", "clinical"]
        return any(indicator in self.type.lower() for indicator in healthcare_indicators)

    def get_provides_by_type(self, use_as: str) -> List[Dict[str, Any]]:
        """Get provides relationships of a specific type."""
        return [p for p in self.provides if p.get("useAs") == use_as]

    def get_target_components(self) -> Set[str]:
        """Get set of component IDs this component provides to."""
        return {p.get("in") for p in self.provides if p.get("in")}

    def add_provides(self, use_as: str, target_id: str, description: Optional[str] = None) -> None:
        """Add a provides relationship."""
        provides_entry = {
            "useAs": use_as,
            "in": target_id
        }
        if description:
            provides_entry["description"] = description

        self.provides.append(provides_entry)
        self.updated_at = datetime.utcnow()

    def remove_provides(self, target_id: str, use_as: Optional[str] = None) -> bool:
        """Remove provides relationships to a target."""
        original_count = len(self.provides)

        if use_as:
            self.provides = [p for p in self.provides
                           if not (p.get("in") == target_id and p.get("useAs") == use_as)]
        else:
            self.provides = [p for p in self.provides if p.get("in") != target_id]

        if len(self.provides) < original_count:
            self.updated_at = datetime.utcnow()
            return True
        return False

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update component configuration."""
        self.config.update(new_config)
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert component to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "kind": self.kind.value if isinstance(self.kind, ComponentKind) else self.kind,
            "description": self.description,
            "config": self.config,
            "provides": self.provides,
            "metadata": self.metadata,
            "position": self.position,
            "asTools": self.as_tools,
            "status": self.status.value if isinstance(self.status, ComponentStatus) else self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowComponent':
        """Create WorkflowComponent from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.utcnow()

        return cls(
            id=data["id"],
            name=data.get("name"),
            type=data["type"],
            kind=data.get("kind", ComponentKind.CUSTOM),
            description=data.get("description"),
            config=data.get("config", {}),
            provides=data.get("provides", []),
            metadata=data.get("metadata", {}),
            position=data.get("position"),
            as_tools=data.get("asTools", False),
            status=data.get("status", ComponentStatus.ACTIVE),
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class ComponentDiscoveryResult:
    """
    Result of component discovery process.

    Attributes:
        component_mappings: Discovered component mappings
        discovered_count: Number of components discovered
        mapped_count: Number of components successfully mapped
        unmapped_components: Components that couldn't be mapped
        discovery_errors: Errors encountered during discovery
        discovery_time_seconds: Time taken for discovery
        metadata: Additional discovery metadata
    """
    component_mappings: Dict[str, ComponentMapping] = field(default_factory=dict)
    discovered_count: int = 0
    mapped_count: int = 0
    unmapped_components: List[str] = field(default_factory=list)
    discovery_errors: List[str] = field(default_factory=list)
    discovery_time_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def mapping_success_rate(self) -> float:
        """Calculate mapping success rate."""
        if self.discovered_count == 0:
            return 100.0
        return (self.mapped_count / self.discovered_count) * 100

    @property
    def has_errors(self) -> bool:
        """Check if discovery had errors."""
        return len(self.discovery_errors) > 0

    def add_mapping(self, component_id: str, mapping: ComponentMapping) -> None:
        """Add a component mapping."""
        self.component_mappings[component_id] = mapping
        self.mapped_count = len(self.component_mappings)

    def add_unmapped_component(self, component_id: str) -> None:
        """Add an unmapped component."""
        if component_id not in self.unmapped_components:
            self.unmapped_components.append(component_id)

    def add_error(self, error_message: str) -> None:
        """Add a discovery error."""
        self.discovery_errors.append(error_message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert discovery result to dictionary representation."""
        return {
            "component_mappings": {k: v.to_dict() for k, v in self.component_mappings.items()},
            "discovered_count": self.discovered_count,
            "mapped_count": self.mapped_count,
            "unmapped_components": self.unmapped_components,
            "discovery_errors": self.discovery_errors,
            "discovery_time_seconds": self.discovery_time_seconds,
            "mapping_success_rate": round(self.mapping_success_rate, 2),
            "has_errors": self.has_errors,
            "metadata": self.metadata
        }


@dataclass
class ComponentRepository:
    """
    Repository for managing component mappings and definitions.

    Attributes:
        name: Repository name
        description: Repository description
        mappings: Component mappings by Genesis type
        supported_types: Set of supported Genesis types
        version: Repository version
        metadata: Repository metadata
        created_at: Repository creation timestamp
        updated_at: Repository last update timestamp
    """
    name: str
    description: str = ""
    mappings: Dict[str, ComponentMapping] = field(default_factory=dict)
    supported_types: Set[str] = field(default_factory=set)
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Post-initialization processing."""
        self.supported_types = set(self.mappings.keys())

    @property
    def mapping_count(self) -> int:
        """Get number of mappings in repository."""
        return len(self.mappings)

    @property
    def healthcare_mapping_count(self) -> int:
        """Get number of healthcare-compliant mappings."""
        return len([m for m in self.mappings.values() if m.healthcare_compliant])

    def add_mapping(self, mapping: ComponentMapping) -> None:
        """Add a component mapping to the repository."""
        self.mappings[mapping.genesis_type] = mapping
        self.supported_types.add(mapping.genesis_type)
        self.updated_at = datetime.utcnow()

    def remove_mapping(self, genesis_type: str) -> bool:
        """Remove a component mapping from the repository."""
        if genesis_type in self.mappings:
            del self.mappings[genesis_type]
            self.supported_types.discard(genesis_type)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def get_mapping(self, genesis_type: str) -> Optional[ComponentMapping]:
        """Get a component mapping by Genesis type."""
        return self.mappings.get(genesis_type)

    def has_mapping(self, genesis_type: str) -> bool:
        """Check if repository has mapping for Genesis type."""
        return genesis_type in self.mappings

    def get_mappings_by_langflow_component(self, langflow_component: str) -> List[ComponentMapping]:
        """Get all mappings for a specific Langflow component."""
        return [m for m in self.mappings.values() if m.langflow_component == langflow_component]

    def get_healthcare_mappings(self) -> Dict[str, ComponentMapping]:
        """Get all healthcare-compliant mappings."""
        return {k: v for k, v in self.mappings.items() if v.healthcare_compliant}

    def search_mappings(self, search_term: str) -> Dict[str, ComponentMapping]:
        """Search mappings by term."""
        search_lower = search_term.lower()
        results = {}

        for genesis_type, mapping in self.mappings.items():
            if (search_lower in genesis_type.lower() or
                search_lower in mapping.langflow_component.lower() or
                any(search_lower in constraint.lower() for constraint in mapping.constraints)):
                results[genesis_type] = mapping

        return results

    def validate_repository(self) -> List[str]:
        """Validate repository consistency."""
        errors = []

        # Check for duplicate Langflow components with different configurations
        langflow_components = {}
        for genesis_type, mapping in self.mappings.items():
            lf_component = mapping.langflow_component
            if lf_component in langflow_components:
                existing_mapping = langflow_components[lf_component]
                if existing_mapping.template_fields != mapping.template_fields:
                    errors.append(f"Inconsistent template fields for {lf_component} between {existing_mapping.genesis_type} and {genesis_type}")
            else:
                langflow_components[lf_component] = mapping

        # Check for missing required fields
        for genesis_type, mapping in self.mappings.items():
            if not mapping.langflow_component:
                errors.append(f"Missing langflow_component for {genesis_type}")

            if not mapping.base_classes:
                errors.append(f"Missing base_classes for {genesis_type}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert repository to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "mappings": {k: v.to_dict() for k, v in self.mappings.items()},
            "supported_types": list(self.supported_types),
            "version": self.version,
            "mapping_count": self.mapping_count,
            "healthcare_mapping_count": self.healthcare_mapping_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComponentRepository':
        """Create ComponentRepository from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.utcnow()

        mappings = {}
        for genesis_type, mapping_data in data.get("mappings", {}).items():
            mappings[genesis_type] = ComponentMapping.from_dict(mapping_data)

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            mappings=mappings,
            supported_types=set(data.get("supported_types", [])),
            version=data.get("version", "1.0.0"),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at
        )
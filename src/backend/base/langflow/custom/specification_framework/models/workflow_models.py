"""
Workflow Models for the Dynamic Agent Specification Framework.

This module defines data models for Langflow workflows, nodes, edges,
and workflow conversion results with comprehensive type safety.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum


class WorkflowStatus(Enum):
    """Workflow execution status."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"


class NodeType(Enum):
    """Standard Langflow node types."""
    GENERIC_NODE = "genericNode"
    GROUP_NODE = "groupNode"
    CUSTOM_NODE = "customNode"


class EdgeType(Enum):
    """Standard Langflow edge types."""
    DEFAULT = "default"
    STRAIGHT = "straight"
    STEP = "step"
    SMOOTH_STEP = "smoothstep"
    BEZIER = "bezier"


@dataclass
class WorkflowNode:
    """
    Represents a node in a Langflow workflow.

    Attributes:
        id: Unique node identifier
        type: Node type (typically "genericNode")
        position: Node position coordinates
        data: Node data including component type and template
        selected: Whether node is selected in UI
        width: Node width in pixels
        height: Node height in pixels
        z_index: Z-index for layering
        metadata: Additional node metadata
        created_at: Node creation timestamp
        updated_at: Node last update timestamp
    """
    id: str
    type: Union[NodeType, str] = NodeType.GENERIC_NODE
    position: Dict[str, Union[int, float]] = field(default_factory=lambda: {"x": 0, "y": 0})
    data: Dict[str, Any] = field(default_factory=dict)
    selected: bool = False
    width: int = 384
    height: int = 256
    z_index: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Post-initialization processing."""
        if isinstance(self.type, str):
            try:
                self.type = NodeType(self.type)
            except ValueError:
                pass  # Keep as string if not in enum

    @property
    def component_type(self) -> Optional[str]:
        """Get the component type from node data."""
        return self.data.get("type")

    @property
    def display_name(self) -> Optional[str]:
        """Get the display name from node data."""
        return self.data.get("display_name")

    @property
    def description(self) -> Optional[str]:
        """Get the description from node data."""
        return self.data.get("description")

    @property
    def template(self) -> Dict[str, Any]:
        """Get the template from node data."""
        return self.data.get("template", {})

    @property
    def genesis_metadata(self) -> Dict[str, Any]:
        """Get Genesis-specific metadata."""
        return self.data.get("metadata", {})

    def update_position(self, x: Union[int, float], y: Union[int, float]) -> None:
        """Update node position."""
        self.position = {"x": x, "y": y}
        self.updated_at = datetime.utcnow()

    def update_size(self, width: int, height: int) -> None:
        """Update node size."""
        self.width = width
        self.height = height
        self.updated_at = datetime.utcnow()

    def update_data(self, new_data: Dict[str, Any]) -> None:
        """Update node data."""
        self.data.update(new_data)
        self.updated_at = datetime.utcnow()

    def set_template_field(self, field_name: str, field_config: Dict[str, Any]) -> None:
        """Set a template field."""
        if "template" not in self.data:
            self.data["template"] = {}
        self.data["template"][field_name] = field_config
        self.updated_at = datetime.utcnow()

    def get_template_field(self, field_name: str) -> Optional[Dict[str, Any]]:
        """Get a template field."""
        return self.template.get(field_name)

    def remove_template_field(self, field_name: str) -> bool:
        """Remove a template field."""
        if field_name in self.template:
            del self.data["template"][field_name]
            self.updated_at = datetime.utcnow()
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary representation."""
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, NodeType) else self.type,
            "position": self.position,
            "data": self.data,
            "selected": self.selected,
            "width": self.width,
            "height": self.height,
            "z_index": self.z_index,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowNode':
        """Create WorkflowNode from dictionary."""
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
            type=data.get("type", NodeType.GENERIC_NODE),
            position=data.get("position", {"x": 0, "y": 0}),
            data=data.get("data", {}),
            selected=data.get("selected", False),
            width=data.get("width", 384),
            height=data.get("height", 256),
            z_index=data.get("z_index", 1),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class WorkflowEdge:
    """
    Represents an edge (connection) in a Langflow workflow.

    Attributes:
        id: Unique edge identifier
        source: Source node ID
        target: Target node ID
        type: Edge type
        animated: Whether edge is animated in UI
        style: Edge styling properties
        source_handle: Source connection handle
        target_handle: Target connection handle
        data: Edge data and metadata
        label: Optional edge label
        selected: Whether edge is selected in UI
        metadata: Additional edge metadata
        created_at: Edge creation timestamp
        updated_at: Edge last update timestamp
    """
    id: str
    source: str
    target: str
    type: Union[EdgeType, str] = EdgeType.DEFAULT
    animated: bool = False
    style: Dict[str, Any] = field(default_factory=dict)
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    label: Optional[str] = None
    selected: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Post-initialization processing."""
        if isinstance(self.type, str):
            try:
                self.type = EdgeType(self.type)
            except ValueError:
                pass  # Keep as string if not in enum

    @property
    def use_as(self) -> Optional[str]:
        """Get the useAs type from edge data."""
        return self.data.get("useAs")

    @property
    def description(self) -> Optional[str]:
        """Get the description from edge data."""
        return self.data.get("description")

    def update_handles(self, source_handle: Optional[str], target_handle: Optional[str]) -> None:
        """Update edge handles."""
        self.source_handle = source_handle
        self.target_handle = target_handle
        self.updated_at = datetime.utcnow()

    def update_style(self, new_style: Dict[str, Any]) -> None:
        """Update edge style."""
        self.style.update(new_style)
        self.updated_at = datetime.utcnow()

    def update_data(self, new_data: Dict[str, Any]) -> None:
        """Update edge data."""
        self.data.update(new_data)
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to dictionary representation."""
        result = {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "type": self.type.value if isinstance(self.type, EdgeType) else self.type,
            "animated": self.animated,
            "style": self.style,
            "data": self.data,
            "selected": self.selected,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

        if self.source_handle is not None:
            result["sourceHandle"] = self.source_handle

        if self.target_handle is not None:
            result["targetHandle"] = self.target_handle

        if self.label is not None:
            result["label"] = self.label

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowEdge':
        """Create WorkflowEdge from dictionary."""
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
            source=data["source"],
            target=data["target"],
            type=data.get("type", EdgeType.DEFAULT),
            animated=data.get("animated", False),
            style=data.get("style", {}),
            source_handle=data.get("sourceHandle"),
            target_handle=data.get("targetHandle"),
            data=data.get("data", {}),
            label=data.get("label"),
            selected=data.get("selected", False),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class LangflowWorkflow:
    """
    Represents a complete Langflow workflow.

    Attributes:
        id: Unique workflow identifier
        name: Workflow name
        description: Workflow description
        nodes: List of workflow nodes
        edges: List of workflow edges
        viewport: Viewport configuration
        status: Workflow status
        tags: Workflow tags
        metadata: Workflow metadata
        folder_id: Optional folder ID
        endpoint_name: Optional endpoint name
        is_component: Whether workflow is a component
        flows: Nested flows
        last_tested_version: Last tested version
        created_at: Workflow creation timestamp
        updated_at: Workflow last update timestamp
    """
    id: str
    name: str
    description: str = ""
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    viewport: Dict[str, Union[int, float]] = field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1})
    status: Union[WorkflowStatus, str] = WorkflowStatus.DRAFT
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    folder_id: Optional[str] = None
    endpoint_name: Optional[str] = None
    is_component: bool = False
    flows: List[Dict[str, Any]] = field(default_factory=list)
    last_tested_version: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Post-initialization processing."""
        if isinstance(self.status, str):
            try:
                self.status = WorkflowStatus(self.status)
            except ValueError:
                pass  # Keep as string if not in enum

    @property
    def node_count(self) -> int:
        """Get number of nodes in workflow."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Get number of edges in workflow."""
        return len(self.edges)

    @property
    def node_ids(self) -> List[str]:
        """Get list of all node IDs."""
        return [node.id for node in self.nodes]

    @property
    def edge_ids(self) -> List[str]:
        """Get list of all edge IDs."""
        return [edge.id for edge in self.edges]

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_edge(self, edge_id: str) -> Optional[WorkflowEdge]:
        """Get an edge by ID."""
        for edge in self.edges:
            if edge.id == edge_id:
                return edge
        return None

    def get_edges_for_node(self, node_id: str) -> List[WorkflowEdge]:
        """Get all edges connected to a node."""
        return [edge for edge in self.edges
                if edge.source == node_id or edge.target == node_id]

    def get_incoming_edges(self, node_id: str) -> List[WorkflowEdge]:
        """Get incoming edges for a node."""
        return [edge for edge in self.edges if edge.target == node_id]

    def get_outgoing_edges(self, node_id: str) -> List[WorkflowEdge]:
        """Get outgoing edges for a node."""
        return [edge for edge in self.edges if edge.source == node_id]

    def add_node(self, node: WorkflowNode) -> None:
        """Add a node to the workflow."""
        # Check for duplicate ID
        if self.get_node(node.id) is not None:
            raise ValueError(f"Node with ID {node.id} already exists")

        self.nodes.append(node)
        self.updated_at = datetime.utcnow()

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its connected edges."""
        node = self.get_node(node_id)
        if node is None:
            return False

        # Remove connected edges
        self.edges = [edge for edge in self.edges
                     if edge.source != node_id and edge.target != node_id]

        # Remove node
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.updated_at = datetime.utcnow()
        return True

    def add_edge(self, edge: WorkflowEdge) -> None:
        """Add an edge to the workflow."""
        # Check for duplicate ID
        if self.get_edge(edge.id) is not None:
            raise ValueError(f"Edge with ID {edge.id} already exists")

        # Validate source and target nodes exist
        if self.get_node(edge.source) is None:
            raise ValueError(f"Source node {edge.source} does not exist")

        if self.get_node(edge.target) is None:
            raise ValueError(f"Target node {edge.target} does not exist")

        self.edges.append(edge)
        self.updated_at = datetime.utcnow()

    def remove_edge(self, edge_id: str) -> bool:
        """Remove an edge from the workflow."""
        original_count = len(self.edges)
        self.edges = [edge for edge in self.edges if edge.id != edge_id]

        if len(self.edges) < original_count:
            self.updated_at = datetime.utcnow()
            return True
        return False

    def update_viewport(self, x: Union[int, float], y: Union[int, float], zoom: Union[int, float]) -> None:
        """Update viewport configuration."""
        self.viewport = {"x": x, "y": y, "zoom": zoom}
        self.updated_at = datetime.utcnow()

    def add_tag(self, tag: str) -> None:
        """Add a tag to the workflow."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.utcnow()

    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from the workflow."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def validate_structure(self) -> List[str]:
        """Validate workflow structure and return any errors."""
        errors = []

        # Check for duplicate node IDs
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            duplicates = [nid for nid in set(node_ids) if node_ids.count(nid) > 1]
            errors.append(f"Duplicate node IDs: {duplicates}")

        # Check for duplicate edge IDs
        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            duplicates = [eid for eid in set(edge_ids) if edge_ids.count(eid) > 1]
            errors.append(f"Duplicate edge IDs: {duplicates}")

        # Check edge references
        valid_node_ids = set(node_ids)
        for edge in self.edges:
            if edge.source not in valid_node_ids:
                errors.append(f"Edge {edge.id} references non-existent source node: {edge.source}")
            if edge.target not in valid_node_ids:
                errors.append(f"Edge {edge.id} references non-existent target node: {edge.target}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow to dictionary representation (Langflow format)."""
        return {
            "description": self.description,
            "name": self.name,
            "id": self.id,
            "data": {
                "edges": [edge.to_dict() for edge in self.edges],
                "nodes": [node.to_dict() for node in self.nodes],
                "viewport": self.viewport
            },
            "endpoint_name": self.endpoint_name,
            "is_component": self.is_component,
            "updated_at": self.updated_at.isoformat(),
            "folder_id": self.folder_id,
            "flows": self.flows,
            "last_tested_version": self.last_tested_version,
            "status": self.status.value if isinstance(self.status, WorkflowStatus) else self.status,
            "tags": self.tags,
            "metadata": {
                **self.metadata,
                "created_at": self.created_at.isoformat(),
                "node_count": self.node_count,
                "edge_count": self.edge_count
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LangflowWorkflow':
        """Create LangflowWorkflow from dictionary."""
        created_at = datetime.utcnow()
        updated_at_str = data.get("updated_at")
        if updated_at_str:
            updated_at = datetime.fromisoformat(updated_at_str)
        else:
            updated_at = datetime.utcnow()

        # Handle metadata with creation timestamp
        metadata = data.get("metadata", {})
        if "created_at" in metadata:
            created_at = datetime.fromisoformat(metadata["created_at"])

        # Parse nodes and edges
        workflow_data = data.get("data", {})
        nodes = [WorkflowNode.from_dict(node_data) for node_data in workflow_data.get("nodes", [])]
        edges = [WorkflowEdge.from_dict(edge_data) for edge_data in workflow_data.get("edges", [])]

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            nodes=nodes,
            edges=edges,
            viewport=workflow_data.get("viewport", {"x": 0, "y": 0, "zoom": 1}),
            status=data.get("status", WorkflowStatus.DRAFT),
            tags=data.get("tags", []),
            metadata=metadata,
            folder_id=data.get("folder_id"),
            endpoint_name=data.get("endpoint_name"),
            is_component=data.get("is_component", False),
            flows=data.get("flows", []),
            last_tested_version=data.get("last_tested_version"),
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class WorkflowConversionResult:
    """
    Result of workflow conversion process.

    Attributes:
        success: Whether conversion was successful
        workflow: Generated workflow (if successful)
        conversion_time_seconds: Time taken for conversion
        node_count: Number of nodes created
        edge_count: Number of edges created
        conversion_errors: Errors encountered during conversion
        performance_metrics: Performance metrics
        langflow_compatibility_score: Compatibility score with Langflow
        metadata: Additional conversion metadata
    """
    success: bool
    workflow: Optional[Dict[str, Any]] = None
    conversion_time_seconds: float = 0.0
    node_count: int = 0
    edge_count: int = 0
    conversion_errors: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    langflow_compatibility_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        """Get number of conversion errors."""
        return len(self.conversion_errors)

    @property
    def has_errors(self) -> bool:
        """Check if conversion had errors."""
        return len(self.conversion_errors) > 0

    def add_error(self, error_message: str) -> None:
        """Add a conversion error."""
        self.conversion_errors.append(error_message)
        self.success = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert conversion result to dictionary representation."""
        return {
            "success": self.success,
            "workflow": self.workflow,
            "conversion_time_seconds": self.conversion_time_seconds,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "error_count": self.error_count,
            "has_errors": self.has_errors,
            "conversion_errors": self.conversion_errors,
            "performance_metrics": self.performance_metrics,
            "langflow_compatibility_score": self.langflow_compatibility_score,
            "metadata": self.metadata
        }

    @classmethod
    def create_success(cls,
                      workflow: Dict[str, Any],
                      conversion_time: float = 0.0,
                      node_count: int = 0,
                      edge_count: int = 0,
                      performance_metrics: Optional[Dict[str, Any]] = None,
                      compatibility_score: float = 1.0) -> 'WorkflowConversionResult':
        """Create a successful conversion result."""
        return cls(
            success=True,
            workflow=workflow,
            conversion_time_seconds=conversion_time,
            node_count=node_count,
            edge_count=edge_count,
            performance_metrics=performance_metrics or {},
            langflow_compatibility_score=compatibility_score
        )

    @classmethod
    def create_error(cls,
                    error_message: str,
                    conversion_time: float = 0.0,
                    conversion_errors: Optional[List[str]] = None) -> 'WorkflowConversionResult':
        """Create a failed conversion result."""
        errors = conversion_errors or []
        if error_message and error_message not in errors:
            errors.append(error_message)

        return cls(
            success=False,
            conversion_time_seconds=conversion_time,
            conversion_errors=errors
        )
from typing import TYPE_CHECKING, NamedTuple

from typing_extensions import NotRequired, TypedDict

from langflow.graph.edge.schema import EdgeData
from langflow.graph.vertex.schema import NodeData

if TYPE_CHECKING:
    from langflow.graph.schema import ResultData
    from langflow.graph.vertex.base import Vertex


class ViewPort(TypedDict):
    x: float
    y: float
    zoom: float


class GraphData(TypedDict):
    nodes: list[NodeData]
    edges: list[EdgeData]
    viewport: NotRequired[ViewPort]


class GraphDump(TypedDict, total=False):
    data: GraphData
    is_component: bool
    name: str
    description: str
    endpoint_name: str


class VertexBuildResult(NamedTuple):
    result_dict: "ResultData"
    params: str
    valid: bool
    artifacts: dict
    vertex: "Vertex"

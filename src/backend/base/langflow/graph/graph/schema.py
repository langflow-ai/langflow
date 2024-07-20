from typing import TYPE_CHECKING, Dict, List, NamedTuple

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


class VertexBuildResult(NamedTuple):
    result_dict: Dict
    params: str
    valid: bool
    artifacts: List
    vertex: "Vertex"

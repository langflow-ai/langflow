from typing import Dict

from typing_extensions import NotRequired, TypedDict


class Position(TypedDict):
    x: float
    y: float


class NodeData(TypedDict):
    id: str
    data: Dict
    dragging: NotRequired[bool]
    height: NotRequired[int]
    width: NotRequired[int]
    position: NotRequired[Position]
    positionAbsolute: NotRequired[Position]
    selected: NotRequired[bool]
    parent_node_id: NotRequired[str]

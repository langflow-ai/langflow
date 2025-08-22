from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.graph.schema import CHAT_COMPONENTS

if TYPE_CHECKING:
    from lfx.graph.vertex.base import Vertex
    from lfx.graph.vertex.vertex_types import CustomComponentVertex


class Finish:
    def __bool__(self) -> bool:
        return True

    def __eq__(self, /, other):
        return isinstance(other, Finish)


def _import_vertex_types():
    from lfx.graph.vertex import vertex_types

    return vertex_types


class VertexTypesDict:
    def __init__(self) -> None:
        self._all_types_dict = None
        self._types = _import_vertex_types

    @property
    def all_types_dict(self):
        if self._all_types_dict is None:
            self._all_types_dict = self._build_dict()
        return self._all_types_dict

    @property
    def vertex_type_map(self) -> dict[str, type[Vertex]]:
        return self.all_types_dict

    def _build_dict(self):
        langchain_types_dict = self.get_type_dict()
        return {
            **langchain_types_dict,
            "Custom": ["Custom Tool", "Python Function"],
        }

    def get_type_dict(self) -> dict[str, type[Vertex]]:
        types = self._types()
        return {
            "CustomComponent": types.CustomComponentVertex,
            "Component": types.ComponentVertex,
            **dict.fromkeys(CHAT_COMPONENTS, types.InterfaceVertex),
        }

    def get_custom_component_vertex_type(self) -> type[CustomComponentVertex]:
        return self._types().CustomComponentVertex


lazy_load_vertex_dict = VertexTypesDict()

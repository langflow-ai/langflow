from __future__ import annotations

from typing import TYPE_CHECKING, override

from langflow_execution.graph.schema import CHAT_COMPONENTS
from langflow_execution.services.manager import ServiceManager

if TYPE_CHECKING:
    from langflow_execution.graph.vertex.base import Vertex
    from langflow_execution.graph.vertex.vertex_types import CustomComponentVertex


class Finish:
    def __bool__(self) -> bool:
        return True

    def __eq__(self, /, other):
        return isinstance(other, Finish)


def _import_vertex_types():
    from langflow_execution.graph.vertex import vertex_types

    return vertex_types

class LazyLoadDictBase:
    def __init__(self) -> None:
        self._all_types_dict = None

    @property
    def all_types_dict(self):
        if self._all_types_dict is None:
            self._all_types_dict = self._build_dict()
        return self._all_types_dict

    def _build_dict(self):
        raise NotImplementedError

    def get_type_dict(self):
        raise NotImplementedError


class VertexTypesDict(LazyLoadDictBase):
    def __init__(self) -> None:
        self._all_types_dict = None
        self._types = _import_vertex_types

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

class AllTypesDict(LazyLoadDictBase):
    def __init__(self) -> None:
        self._all_types_dict = None

    def _build_dict(self):
        langchain_types_dict = self.get_type_dict()
        return {
            **langchain_types_dict,
            "Custom": ["Custom Tool", "Python Function"],
        }

    @override
    def get_type_dict(self):
        from langflow_execution.components.custom.utils import get_all_types_dict

        settings_service = ServiceManager.get_instance().get_settings_service()
        return get_all_types_dict(settings_service.settings.components_path)


lazy_load_vertex_dict = VertexTypesDict()
lazy_load_dict = AllTypesDict()


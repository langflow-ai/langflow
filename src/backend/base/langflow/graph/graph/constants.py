from langflow.graph.schema import CHAT_COMPONENTS
from langflow.utils.lazy_load import LazyLoadDictBase


class Finish:
    def __bool__(self):
        return True

    def __eq__(self, other):
        return isinstance(other, Finish)


def _import_vertex_types():
    from langflow.graph.vertex import types

    return types


class VertexTypesDict(LazyLoadDictBase):
    def __init__(self):
        self._all_types_dict = None
        self._types = _import_vertex_types()

    @property
    def VERTEX_TYPE_MAP(self):
        return self.all_types_dict

    def _build_dict(self):
        langchain_types_dict = self.get_type_dict()
        return {
            **langchain_types_dict,
            "Custom": ["Custom Tool", "Python Function"],
        }

    def get_type_dict(self):
        return {
            **{t: self._types.CustomComponentVertex for t in ["CustomComponent"]},
            **{t: self._types.ComponentVertex for t in ["Component"]},
            **{t: self._types.InterfaceVertex for t in CHAT_COMPONENTS},
        }

    def get_custom_component_vertex_type(self):
        return self._types.CustomComponentVertex


lazy_load_vertex_dict = VertexTypesDict()

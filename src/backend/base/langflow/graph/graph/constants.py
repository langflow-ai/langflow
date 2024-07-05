from langflow.graph.schema import CHAT_COMPONENTS
from langflow.graph.vertex import types
from langflow.utils.lazy_load import LazyLoadDictBase


class VertexTypesDict(LazyLoadDictBase):
    def __init__(self):
        self._all_types_dict = None

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
            **{t: types.CustomComponentVertex for t in ["CustomComponent"]},
            **{t: types.ComponentVertex for t in ["Component"]},
            **{t: types.InterfaceVertex for t in CHAT_COMPONENTS},
        }

    def get_custom_component_vertex_type(self):
        return types.CustomComponentVertex


lazy_load_vertex_dict = VertexTypesDict()

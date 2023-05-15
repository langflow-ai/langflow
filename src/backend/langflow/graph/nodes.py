from typing import Any, Dict

from langflow.graph.base import Node
from langflow.interface.connectors.custom import ConnectorFunction


class ConnectorNode(Node):
    _built_object: Any = None
    _built: bool = False

    def __init__(self, data: Dict) -> None:
        super().__init__(data, base_type="connectors")

    def _build(self) -> None:
        func = None
        for param, value in self.params.items():
            if param == "code":
                conn_func = ConnectorFunction(code=value)
                func = conn_func.get_function()

        if func is None:
            raise ValueError("Connector function not found")
        self._built_object = func
        self._built = True

from langflow.graph.base import Node


from typing import Dict


class ConnectorNode(Node):
    def __init__(self, data: Dict):
        super().__init__(data, base_type="connectors")

    def _build(self) -> None:
        def connector(input):
            return input

        self._built_object = connector
        self._built = True

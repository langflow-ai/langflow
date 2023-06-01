from typing import Dict, List, Optional

from langflow.custom.customs import get_custom_nodes
from langflow.interface.base import Creator
from langflow.utils.logger import logger

# Assuming necessary imports for Field, Template, and FrontendNode classes


class ConnectorCreator(Creator):
    type_name: str = "connectors"

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            # Filter according to settings.connectors
            from langflow.interface.connectors.custom import CONNECTORS

            self.type_dict = CONNECTORS
        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        try:
            nodes = get_custom_nodes(self.type_name)
            if name in nodes.keys():
                return nodes[name]
            else:
                raise ValueError("Connector not found")
        except ValueError as exc:
            raise ValueError("Connector not found") from exc
        except AttributeError as exc:
            logger.error(f"Connector {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return list(self.type_to_loader_dict.keys())


connector_creator = ConnectorCreator()

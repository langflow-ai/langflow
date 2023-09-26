from typing import Callable, Dict, List, Optional

from langchain.agents import agent_toolkits

from langflow.interface.base import LangChainTypeCreator
from langflow.interface.importing.utils import import_class, import_module
from langflow.services.getters import get_settings_service

from loguru import logger
from langflow.utils.util import build_template_from_class


class ToolkitCreator(LangChainTypeCreator):
    type_name: str = "toolkits"
    all_types: List[str] = agent_toolkits.__all__
    create_functions: Dict = {
        "JsonToolkit": [],
        "SQLDatabaseToolkit": [],
        "OpenAPIToolkit": ["create_openapi_agent"],
        "VectorStoreToolkit": [
            "create_vectorstore_agent",
            "create_vectorstore_router_agent",
            "VectorStoreInfo",
        ],
        "ZapierToolkit": [],
        "PandasToolkit": ["create_pandas_dataframe_agent"],
        "CSVToolkit": ["create_csv_agent"],
    }

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            settings_service = get_settings_service()
            self.type_dict = {
                toolkit_name: import_class(
                    f"langchain.agents.agent_toolkits.{toolkit_name}"
                )
                # if toolkit_name is not lower case it is a class
                for toolkit_name in agent_toolkits.__all__
                if not toolkit_name.islower()
                and toolkit_name in settings_service.settings.TOOLKITS
            }

        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        try:
            template = build_template_from_class(name, self.type_to_loader_dict)
            # add Tool to base_classes
            if "toolkit" in name.lower() and template:
                template["base_classes"].append("Tool")
            return template
        except ValueError as exc:
            raise ValueError("Toolkit not found") from exc
        except AttributeError as exc:
            logger.error(f"Toolkit {name} not loaded: {exc}")
            return None

    def to_list(self) -> List[str]:
        return list(self.type_to_loader_dict.keys())

    def get_create_function(self, name: str) -> Callable:
        if loader_name := self.create_functions.get(name):
            return import_module(
                f"from langchain.agents.agent_toolkits import {loader_name[0]}"
            )
        else:
            raise ValueError("Toolkit not found")

    def has_create_function(self, name: str) -> bool:
        # check if the function list is not empty
        return bool(self.create_functions.get(name, None))


toolkits_creator = ToolkitCreator()

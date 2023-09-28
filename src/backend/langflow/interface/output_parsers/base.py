from typing import Dict, List, Optional, Type

from langchain import output_parsers

from langflow.interface.base import LangChainTypeCreator
from langflow.interface.importing.utils import import_class
from langflow.services.getters import get_settings_service

from langflow.template.frontend_node.output_parsers import OutputParserFrontendNode
from loguru import logger
from langflow.utils.util import build_template_from_class, build_template_from_method


class OutputParserCreator(LangChainTypeCreator):
    type_name: str = "output_parsers"
    from_method_nodes = {
        "StructuredOutputParser": "from_response_schemas",
    }

    @property
    def frontend_node_class(self) -> Type[OutputParserFrontendNode]:
        return OutputParserFrontendNode

    @property
    def type_to_loader_dict(self) -> Dict:
        if self.type_dict is None:
            settings_service = get_settings_service()
            self.type_dict = {
                output_parser_name: import_class(
                    f"langchain.output_parsers.{output_parser_name}"
                )
                # if output_parser_name is not lower case it is a class
                for output_parser_name in output_parsers.__all__
            }
            self.type_dict = {
                name: output_parser
                for name, output_parser in self.type_dict.items()
                if name in settings_service.settings.OUTPUT_PARSERS
                or settings_service.settings.DEV
            }
        return self.type_dict

    def get_signature(self, name: str) -> Optional[Dict]:
        try:
            if name in self.from_method_nodes:
                return build_template_from_method(
                    name,
                    type_to_cls_dict=self.type_to_loader_dict,
                    method_name=self.from_method_nodes[name],
                )
            else:
                return build_template_from_class(
                    name,
                    type_to_cls_dict=self.type_to_loader_dict,
                )
        except ValueError as exc:
            # raise ValueError("OutputParser not found") from exc
            logger.error(f"OutputParser {name} not found: {exc}")
        except AttributeError as exc:
            logger.error(f"OutputParser {name} not loaded: {exc}")
        return None

    def to_list(self) -> List[str]:
        return list(self.type_to_loader_dict.keys())


output_parser_creator = OutputParserCreator()

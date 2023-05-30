from typing import Dict, List, Optional, Type

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode

class TextSplittersFrontNode(FrontendNode):
    
    def add_extra_fields(self) -> None:
        pass
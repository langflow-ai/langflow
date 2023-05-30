from typing import Dict, List, Optional, Type

from langflow.template.field.base import TemplateField
from langflow.template.frontend_node.base import FrontendNode

class VectorStoreFrontendNode(FrontendNode):
    
    def add_extra_fields(self) -> None:
        pass

        """
        signature["template"]["documents"] = {
                "type": "BaseLoader",
                "required": True,
                "show": True,
                "name": "documents",
            }

            signature["template"]["separator"] = {
                "type": "str",
                "required": True,
                "show": True,
                "value": ".",
                "name": "separator",
                "display_name": "Separator",
            }

            signature["template"]["chunk_size"] = {
                "type": "int",
                "required": True,
                "show": True,
                "value": 4000,
                "name": "chunk_size",
                "display_name": "Chunk Size",
            }

            signature["template"]["chunk_overlap"] = {
                "type": "int",
                "required": True,
                "show": True,
                "value": 200,
                "name": "chunk_overlap",
                "display_name": "Chunk Overlap",
            }
        """
   
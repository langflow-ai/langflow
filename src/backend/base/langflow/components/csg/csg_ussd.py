import json
from typing import Any

import requests
from loguru import logger
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langchain.tools import StructuredTool
from langflow.field_typing import Tool
from langflow.inputs import MultilineInput, SecretStrInput, StrInput
from langflow.schema import Data
from langflow.io import Output


class CsgUssd(LCToolComponent):
    category: str = "tools"
    display_name: str = "USSD Gateway"
    description: str = "Interrogate and control the USSD Gateway"
#    documentation: str = "https://docs-totogi-ontology.redoc.ly/openapi/product/operation/retrieveProduct/"
    icon = "csg"

    inputs = [
        # ChoiceInput(
        #     name="ussd_action",
        #     display_name="USSD Action",
        #     info="The action to perform on the USSD Gateway.",
        #     required=True,
        #     choices=[
        #         'initiateUSSD', 
        #         'sendUSSD', 
        #         'endUSSD', 
        #         'receiveUSSD', 
        #         'routeUSSD', 
        #         'registerShortCode', 
        #         'setTimeout', 
        #         'getSessionStatus', 
        #         'checkAvailability', 
        #         'getUsageMetrics', 
        #         'createMenu', 
        #         'captureInput', 
        #         'chargeUSSD', 
        #         'authenticateUser', 
        #         'handleInvalidInput', 
        #         'logError'
        #     ],
        # ),
        StrInput(
            name="gateway_address",
            display_name="Gateway Address",
            info="Location of the USSD Gateway.",
            required=True,
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_tool"),
    ]

    class CsgUssdSchema(BaseModel):
        # ussd_action: str = Field(..., description="Action to perform on the USSD Gateway.")
        gateway_address: str = Field(..., description="Connection string for the USSD Gateway.")

    def run_model(self) -> Data:
        result = self._add_content_to_page(self.markdown_text, self.block_id)
        return Data(data=result, text=json.dumps(result))

    def build_tool(self) -> Tool:
        logger.info(f"Building Csg tool: {self.display_name}")
        return StructuredTool.from_function(
            name="csg_ussd",
            description="Tool for the CSG USSD Gateway",
            func=self._ussd_action,
            args_schema=self.CsgOntologyProductDetailSchema,
        )

    def _ussd_action(self, ussd_action: str, gateway_address: str) -> dict[str, Any] | str:
        logger.info(f"Performing USSD action: {ussd_action} on gateway: {gateway_address}")
        return {"status": "success", "message": f"USSD action {ussd_action} performed successfully on gateway {gateway_address}"}

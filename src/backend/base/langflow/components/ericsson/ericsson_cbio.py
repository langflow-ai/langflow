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

class EricssonBilling(LCToolComponent):
    display_name: str = "Ericsson Billing"
    description: str = "Configure and retrieve information from the Ericsson Billing."
    documentation: str = "https://docs-totogi-ontology.redoc.ly/openapi/customer/operation/retrieveCustomer/"
    icon = "Ericsson"

    inputs = [
        StrInput(
            name="customer_id",
            display_name="Customer ID",
            info="Identifier of the Customer.",
            required=True,
        ),
        SecretStrInput(
            name="customer_fields",
            display_name="Fields",
            info="Comma-separated properties to provide in response.",
        ),
        
    ]

    outputs = [
        Output(name="Billing_info", display_name="Tool", method="build_tool"),
    ]

    class EricssonBillingSchema(BaseModel):
        customer_id: str = Field(..., description="Identifier of the Customer.")
        customer_fields: str = Field(..., description="Comma-separated properties to provide in response.")

    def run_model(self) -> Data:
        result = self._add_content_to_page(self.markdown_text, self.block_id)
        return Data(data=result, text=json.dumps(result))

    def build_tool(self) -> Tool:
        logger.info(f"Building Totogi Ontology tool: {self.display_name}")
        return StructuredTool.from_function(
            name="ericsson_Billing",
            description="Retrieve information from the Ericsson Billing.",
            func=self._get_Billing_info,
            args_schema=self.EricssonBillingSchema,
        )

    def _get_Billing_info(self, customer_id: str, fields: str) -> dict[str, Any] | str:
        try:

            url = f"https://bss.totogi.com/customerManagement/v4/customer/{customer_id}?fields={fields}"
            headers = {
                "Authorization": f"Bearer <YOUR_TOKEN_HERE>",
            }

            response = requests.get(url, headers=headers)
            response.raise_for_status()

            return response.json()
        except requests.exceptions.RequestException as e:
            error_message = f"Error: Failed to get customer {customer_id} from Totogi Ontology GET Customer. {e}"
            if hasattr(e, "response") and e.response is not None:
                error_message += f" Status code: {e.response.status_code}, Response: {e.response.text}"
            return error_message
        except Exception as e:  # noqa: BLE001
            logger.opt(exception=True).debug("Error getting customer detail from Totogi Ontology")
            return f"Error: An unexpected error occurred while looking up customer {customer_id}. {e}"

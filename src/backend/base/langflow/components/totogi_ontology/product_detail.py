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


class TotogiOntologyProductDetail(LCToolComponent):
    display_name: str = "Product Detail - GET"
    description: str = "Retrieve product details from the Totogi Ontology by product ID."
    documentation: str = "https://docs-totogi-ontology.redoc.ly/openapi/product/operation/retrieveProduct/"
    icon = "Totogi"

    inputs = [
        StrInput(
            name="product_id",
            display_name="Product ID",
            info="Identifier of the Product.",
            required=True,
        ),
        SecretStrInput(
            name="product_fields",
            display_name="Fields",
            info="Comma-separated properties to provide in response.",
        ),
    ]

    class TotogiOntologyProductDetailSchema(BaseModel):
        product_id: str = Field(..., description="Identifier of the Product.")
        product_fields: str = Field(..., description="Comma-separated properties to provide in response.")

    def run_model(self) -> Data:
        result = self._add_content_to_page(self.markdown_text, self.block_id)
        return Data(data=result, text=json.dumps(result))

    def build_tool(self) -> Tool:
        logger.info(f"Building Totogi Ontology tool: {self.display_name}")
        return StructuredTool.from_function(
            name="totogi_ontology_product_detail_get",
            description="Retrieve product details from the Totogi Ontology by product ID.",
            func=self._get_product_detail,
            args_schema=self.TotogiOntologyProductDetailSchema,
        )

    def _get_product_detail(self, product_id: str, fields: str) -> dict[str, Any] | str:
        try:

            url = f"https://bss.totogi.com/productManagement/v4/product/{product_id}?fields={fields}"
            headers = {
                "Authorization": f"Bearer <YOUR_TOKEN_HERE>",
            }

            response = requests.get(url, headers=headers)
            response.raise_for_status()

            return response.json()
        except requests.exceptions.RequestException as e:
            error_message = f"Error: Failed to get product {product_id} from Totogi Ontology GET Product. {e}"
            if hasattr(e, "response") and e.response is not None:
                error_message += f" Status code: {e.response.status_code}, Response: {e.response.text}"
            return error_message
        except Exception as e:  # noqa: BLE001
            logger.opt(exception=True).debug("Error getting product detail from Totogi Ontology")
            return f"Error: An unexpected error occurred while looking up product {product_id}. {e}"

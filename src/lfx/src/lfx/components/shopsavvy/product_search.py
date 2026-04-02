import httpx
from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel, Field

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data

SHOPSAVVY_API_URL = "https://api.shopsavvy.com/v1"


class ShopSavvySearchSchema(BaseModel):
    query: str = Field(..., description="Product name, keyword, or description to search for.")
    max_results: int = Field(5, description="Maximum number of results to return (1-100).", ge=1, le=100)


class ShopSavvyProductSearchComponent(LCToolComponent):
    display_name = "ShopSavvy Product Search"
    description = (
        "Search for products by keyword across millions of products and "
        "thousands of retailers using the ShopSavvy Data API."
    )
    icon = "ShoppingCart"
    name = "ShopSavvyProductSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="ShopSavvy API Key",
            required=True,
            info="Your ShopSavvy API key. Get one at shopsavvy.com/data",
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info='Product name, keyword, or description (e.g. "sony headphones", "iphone 15 pro").',
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Maximum number of search results to return (1-100).",
            value=5,
            advanced=True,
        ),
    ]

    def _search_products(self, query: str, max_results: int = 5) -> list[Data]:
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{SHOPSAVVY_API_URL}/products/search",
                    params={"q": query, "limit": str(max_results)},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "application/json",
                    },
                )
            response.raise_for_status()
            result = response.json()

            data_results = []
            for product in result.get("data", []):
                text = f"{product.get('title', 'Unknown Product')}"
                if product.get("brand"):
                    text += f" by {product['brand']}"
                if product.get("category"):
                    text += f" ({product['category']})"

                data_results.append(
                    Data(
                        text=text,
                        data={
                            "title": product.get("title"),
                            "shopsavvy_id": product.get("shopsavvy"),
                            "brand": product.get("brand"),
                            "category": product.get("category"),
                            "barcode": product.get("barcode"),
                            "asin": product.get("amazon"),
                            "model": product.get("model"),
                            "description": product.get("description"),
                            "images": product.get("images"),
                        },
                    )
                )

            self.status = data_results  # type: ignore[assignment]
            return data_results

        except httpx.TimeoutException as e:
            error_message = "ShopSavvy API request timed out."
            raise ToolException(error_message) from e
        except httpx.HTTPStatusError as e:
            error_message = f"ShopSavvy API error: {e.response.status_code} - {e.response.text}"
            raise ToolException(error_message) from e
        except Exception as e:
            error_message = f"ShopSavvy search error: {e}"
            raise ToolException(error_message) from e

    def run_model(self) -> list[Data]:
        return self._search_products(self.query, max_results=self.max_results)

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="shopsavvy_product_search",
            description=(
                "Search for products by keyword. Returns product details including "
                "title, brand, category, barcode, and identifiers."
            ),
            func=self._search_products,
            args_schema=ShopSavvySearchSchema,
        )

import json

import httpx
from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel, Field

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data

SHOPSAVVY_API_URL = "https://api.shopsavvy.com/v1"


class ShopSavvyPriceComparisonSchema(BaseModel):
    identifier: str = Field(
        ..., description="Product identifier: barcode/UPC, ASIN, URL, model number, or product name."
    )
    retailer: str | None = Field(
        None, description='Optional retailer domain to filter by (e.g. "amazon.com").'
    )


class ShopSavvyPriceComparisonComponent(LCToolComponent):
    display_name = "ShopSavvy Price Comparison"
    description = (
        "Compare current prices for a product across retailers using the "
        "ShopSavvy Data API. Returns offers sorted by price."
    )
    icon = "ShoppingCart"
    name = "ShopSavvyPriceComparison"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="ShopSavvy API Key",
            required=True,
            info="Your ShopSavvy API key. Get one at shopsavvy.com/data",
        ),
        MessageTextInput(
            name="identifier",
            display_name="Product Identifier",
            info="Barcode/UPC, Amazon ASIN, product URL, model number, or product name.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="retailer",
            display_name="Retailer",
            info='Optional retailer domain to filter by (e.g. "amazon.com", "walmart.com").',
            advanced=True,
        ),
    ]

    def _compare_prices(self, identifier: str, retailer: str | None = None) -> list[Data]:
        try:
            params: dict[str, str] = {"ids": identifier}
            if retailer:
                params["retailer"] = retailer

            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{SHOPSAVVY_API_URL}/products/offers",
                    params=params,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "application/json",
                    },
                )
            response.raise_for_status()
            result = response.json()

            data_results = []
            for product in result.get("data", []):
                product_title = product.get("title", "Unknown Product")
                for offer in product.get("offers", []):
                    price = offer.get("price")
                    retailer_name = offer.get("retailer", "Unknown")
                    currency = offer.get("currency", "USD")

                    text = f"{retailer_name}: "
                    if price is not None:
                        text += f"{currency} {price}"
                    else:
                        text += "Price unavailable"
                    text += f" - {product_title}"

                    data_results.append(
                        Data(
                            text=text,
                            data={
                                "product_title": product_title,
                                "retailer": retailer_name,
                                "price": price,
                                "currency": currency,
                                "availability": offer.get("availability"),
                                "condition": offer.get("condition"),
                                "url": offer.get("URL"),
                                "seller": offer.get("seller"),
                                "last_updated": offer.get("timestamp"),
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
            error_message = f"ShopSavvy price comparison error: {e}"
            raise ToolException(error_message) from e

    def run_model(self) -> list[Data]:
        return self._compare_prices(
            self.identifier,
            retailer=self.retailer if hasattr(self, "retailer") and self.retailer else None,
        )

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="shopsavvy_price_comparison",
            description=(
                "Compare current prices for a product across retailers. "
                "Returns offers with retailer name, price, availability, and product page URL."
            ),
            func=self._compare_prices,
            args_schema=ShopSavvyPriceComparisonSchema,
        )

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

ADANOS_API_BASE_URL = "https://api.adanos.org"
ADANOS_REQUEST_TIMEOUT = httpx.Timeout(95.0, connect=10.0)
MAX_RESULT_LIMIT = 100
MIN_NUMERIC_STOCK_SYMBOL_LENGTH = 3

_OPERATION_PATHS = {
    "Asset sentiment": "asset",
    "Trending assets": "trending",
    "Market sentiment": "market-sentiment",
}
_STOCK_SOURCES = {
    "Reddit": "reddit",
    "X / FinTwit": "x",
    "News": "news",
    "Polymarket": "polymarket",
}
_STOCK_SYMBOL_PATTERN = re.compile(r"^(?:[A-Z0-9]{1,10}|[A-Z0-9]{1,8}[.-][A-Z])$")
_CRYPTO_SYMBOL_PATTERN = re.compile(r"^\$?[A-Z0-9]{1,20}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AdanosMarketSentimentComponent(Component):
    display_name = "Adanos Market Sentiment"
    description = "Retrieve stock and crypto market sentiment from Adanos."
    documentation = "https://api.adanos.org/docs"
    name = "AdanosMarketSentiment"
    icon = "TrendingUp"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Adanos API Key",
            info="Create an API key at https://adanos.org/register",
            password=True,
            required=True,
        ),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=list(_OPERATION_PATHS),
            value="Asset sentiment",
        ),
        DropdownInput(
            name="asset_type",
            display_name="Asset Type",
            options=["Stocks", "Crypto"],
            value="Stocks",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="source",
            display_name="Stock Source",
            options=list(_STOCK_SOURCES),
            value="Reddit",
            info="Used for stocks. Crypto sentiment is currently sourced from Reddit.",
            dynamic=True,
            show=True,
        ),
        MessageTextInput(
            name="symbol",
            display_name="Ticker or Symbol",
            value="AAPL",
            info="Required for Asset sentiment, for example AAPL or BTC.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="start_date",
            display_name="From Date",
            value="",
            info="Optional inclusive UTC date in YYYY-MM-DD format.",
            advanced=True,
        ),
        MessageTextInput(
            name="end_date",
            display_name="To Date",
            value="",
            info="Optional inclusive UTC date in YYYY-MM-DD format.",
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Result Limit",
            value=20,
            info="Maximum number of results for Trending assets (1-100).",
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Data", name="data", method="fetch_sentiment")]

    @staticmethod
    def _secret_value(value: Any) -> str:
        """Return a normalized API key from string or secret input values."""
        if hasattr(value, "get_secret_value"):
            value = value.get_secret_value()
        return str(value or "").strip()

    @staticmethod
    def _parse_date(value: str, field_name: str) -> str | None:
        """Validate and normalize an optional ISO calendar date."""
        normalized = (value or "").strip()
        if not normalized:
            return None
        if not _DATE_PATTERN.fullmatch(normalized):
            msg = f"{field_name} must use YYYY-MM-DD format."
            raise ValueError(msg)
        try:
            parsed_date = date.fromisoformat(normalized)
        except ValueError as exc:
            msg = f"{field_name} must use YYYY-MM-DD format."
            raise ValueError(msg) from exc
        return parsed_date.isoformat()

    def _request_parts(self) -> tuple[str, dict[str, str | int]]:
        """Build the API path and query parameters for the selected operation."""
        if self.operation not in _OPERATION_PATHS:
            msg = "Unsupported Adanos operation."
            raise ValueError(msg)
        if self.asset_type not in {"Stocks", "Crypto"}:
            msg = "Asset Type must be Stocks or Crypto."
            raise ValueError(msg)

        start_date = self._parse_date(self.start_date, "From Date")
        end_date = self._parse_date(self.end_date, "To Date")
        if start_date and end_date and start_date > end_date:
            msg = "From Date cannot be after To Date."
            raise ValueError(msg)

        params: dict[str, str | int] = {}
        if start_date:
            params["from"] = start_date
        if end_date:
            params["to"] = end_date

        if self.asset_type == "Crypto":
            prefix = "/reddit/crypto/v1"
            asset_segment = "token"
        else:
            source = _STOCK_SOURCES.get(self.source)
            if source is None:
                msg = "Unsupported Adanos stock source."
                raise ValueError(msg)
            prefix = f"/{source}/stocks/v1"
            asset_segment = "stock"

        operation = _OPERATION_PATHS[self.operation]
        if operation == "asset":
            symbol = (self.symbol or "").strip().upper()
            normalized_symbol = symbol.removeprefix("$")
            is_valid_stock = bool(
                _STOCK_SYMBOL_PATTERN.fullmatch(normalized_symbol)
                and (
                    any(character.isalpha() for character in normalized_symbol)
                    or len(normalized_symbol) >= MIN_NUMERIC_STOCK_SYMBOL_LENGTH
                )
            )
            is_valid_crypto = bool(_CRYPTO_SYMBOL_PATTERN.fullmatch(symbol))
            is_valid_symbol = is_valid_crypto if self.asset_type == "Crypto" else is_valid_stock
            if not symbol or not is_valid_symbol:
                msg = "Enter a valid ticker or crypto symbol for Asset sentiment."
                raise ValueError(msg)
            path = f"{prefix}/{asset_segment}/{quote(normalized_symbol, safe='.-')}"
        else:
            path = f"{prefix}/{operation}"
            if operation == "trending":
                if not isinstance(self.limit, int) or not 1 <= self.limit <= MAX_RESULT_LIMIT:
                    msg = "Result Limit must be between 1 and 100."
                    raise ValueError(msg)
                params["limit"] = self.limit

        return path, params

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Show the stock source only when the selected asset type is Stocks."""
        if field_name == "asset_type":
            build_config["source"]["show"] = field_value == "Stocks"
        return build_config

    def fetch_sentiment(self) -> Data:
        """Fetch market sentiment from Adanos and return it as Langflow Data."""
        api_key = self._secret_value(self.api_key)
        if not api_key:
            msg = "Adanos API key is required."
            raise ValueError(msg)

        path, params = self._request_parts()
        try:
            response = httpx.get(
                f"{ADANOS_API_BASE_URL}{path}",
                headers={"X-API-Key": api_key, "Accept": "application/json"},
                params=params,
                timeout=ADANOS_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            msg = f"Adanos API request failed with status {exc.response.status_code}."
            raise ValueError(msg) from exc
        except (httpx.RequestError, ValueError) as exc:
            msg = "Could not retrieve market sentiment from Adanos."
            raise ValueError(msg) from exc

        data = payload if isinstance(payload, dict) else {"results": payload}
        result = Data(data=data)
        self.status = result
        return result

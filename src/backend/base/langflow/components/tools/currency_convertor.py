from datetime import datetime

import requests

from langflow.custom import Component
from langflow.inputs import DropdownInput, StrInput, IntInput, SecretStrInput, MessageTextInput
from langflow.io import Output
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message

class CurrencyMode:
    LIVE = "live"
    HISTORICAL = "historical"

class CurrencyConverterComponent(Component):
    display_name = "Currency Converter"
    description = (
        "Fetches live or historical exchange rates from exchangerate.host API. "
        "Supports JSON format and returns structured rates with timestamps."
    )
    icon = "dollar-sign"

    inputs = [
        DropdownInput(
            name="mode",
            display_name="Mode",
            info="Select 'live' for current rates or 'historical' for a past date.",
            options=[CurrencyMode.LIVE, CurrencyMode.HISTORICAL],
            value=CurrencyMode.LIVE,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Your https://exchangerate.host access key.",
            value="",
        ),
        StrInput(
            name="base_currency",
            display_name="Base Currency",
            info="ISO code of the base currency (e.g., USD, EUR).",
            value="USD",
        ),
        StrInput(
            name="target_currencies",
            display_name="Target Currencies",
            info="Comma-separated ISO codes (e.g., EUR,GBP,JPY).",
            value="EUR",
        ),
        MessageTextInput(
            name="amount",
            display_name="Amount",
            info="The arithmetic expression to evaluate (e.g., '4*4*(33/22)+12-20').",
            tool_mode=True,
        ),
        StrInput(
            name="date",
            display_name="Historical Date",
            info="Date for historical rates (YYYY-MM-DD). Required if mode is 'historical'.",
            value=datetime.now().strftime("%Y-%m-%d"),
        ),
    ]

    outputs = [
        Output(display_name="Raw Data", name="data", method="fetch_content"),
        Output(display_name="Text", name="text", method="fetch_content_text"),
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    def run_model(self) -> list[Data]:
        return self.fetch_content()

    def fetch_content_text(self) -> Message:
        data = self.fetch_content()
        lines = [
            f"{self.amount} {self.base_currency} → {item.data['converted']} {item.data['currency']}" for item in data
        ]
        lines.append(f"Timestamp: {data[0].data['timestamp']}")
        return Message(text="\n".join(lines))

    def fetch_content(self) -> list[Data]:
        params = {
            "access_key": self.api_key,
            "source": self.base_currency,
            "currencies": self.target_currencies,
            "format": 1,
        }
        if self.mode == CurrencyMode.LIVE:
            url = "http://api.exchangerate.host/live"
        else:
            url = "http://api.exchangerate.host/historical"
            params["date"] = self.date

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success", False):
            error_message = payload.get("error")
            raise ValueError(f"API error: {error_message}")

        timestamp = datetime.fromtimestamp(payload.get("timestamp")).isoformat() + "Z"
        quotes = payload.get("quotes", {})

        try:
            amount_val = float(self.amount)
        except (TypeError, ValueError):
            raise ValueError("❌ ‘amount’ must be a number (e.g., 12 or 12.34).")

        result = []
        for pair, rate in quotes.items():
            target_currency = pair.replace(self.base_currency, "")
            converted = rate * amount_val
            result.append(
                Data(
                    text=f"{pair}: rate={rate}, converted={converted}",
                    data={
                        "currency": target_currency,
                        "rate": rate,
                        "amount": amount_val,
                        "converted": converted,
                        "timestamp": timestamp,
                    },
                )
            )
        return result

    def as_dataframe(self) -> DataFrame:
        data = self.fetch_content()
        return DataFrame(data)
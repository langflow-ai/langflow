from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data

DEFAULT_BILIG_BASE_URL = "https://bilig.proompteng.ai"


class BiligWorkPaperFormulaReadbackComponent(Component):
    """Verify one Bilig WorkPaper formula recalculation through a Langflow component."""

    display_name = "Bilig WorkPaper Formula Readback"
    description = "Edit one WorkPaper input cell, recalculate formulas, and return verified readback proof."
    documentation = "https://github.com/proompteng/bilig"
    icon = "table2"
    name = "BiligWorkPaperFormulaReadback"
    metadata = {"keywords": ["bilig", "workpaper", "spreadsheet", "formula", "xlsx", "excel"]}

    inputs = [
        MessageTextInput(
            name="base_url",
            display_name="Bilig API Base URL",
            info="Hosted, local, or self-hosted Bilig app base URL.",
            value=DEFAULT_BILIG_BASE_URL,
            advanced=True,
        ),
        MessageTextInput(
            name="sheet_name",
            display_name="Sheet Name",
            info="Worksheet containing the input cell.",
            value="Inputs",
            tool_mode=True,
        ),
        MessageTextInput(
            name="address",
            display_name="Cell Address",
            info="Input cell to update before formula readback, for example B3.",
            value="B3",
            tool_mode=True,
        ),
        FloatInput(
            name="value",
            display_name="Input Value",
            info="Numeric value to write before recalculation.",
            value=0.4,
            tool_mode=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="HTTP timeout in seconds.",
            value=30,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="JSON", name="proof", type_=Data, method="verify_formula_readback"),
    ]

    def verify_formula_readback(self) -> Data:
        """Write one input cell and return compact readback proof or an error payload."""
        try:
            proof = call_bilig_forecast(
                base_url=self.base_url or DEFAULT_BILIG_BASE_URL,
                sheet_name=self.sheet_name or "Inputs",
                address=(self.address or "B3").upper(),
                value=self.value,
                timeout=self.timeout or 30,
            )
            compact = compact_proof(proof)
            self.status = compact
            return Data(data=compact)
        except (httpx.HTTPError, TimeoutError, TypeError, ValueError) as error:
            message = f"Bilig WorkPaper formula readback failed: {error}"
            self.status = message
            return Data(data={"error": message})


def call_bilig_forecast(
    *,
    base_url: str,
    sheet_name: str,
    address: str,
    value: Any,
    timeout: int,
) -> dict[str, Any]:
    """Call the Bilig forecast endpoint and require a verified JSON proof object."""
    if not base_url.startswith(("http://", "https://")):
        msg = "base_url must start with http:// or https://"
        raise ValueError(msg)

    endpoint = urljoin(base_url.rstrip("/") + "/", "api/workpaper/n8n/forecast")
    with httpx.Client(
        timeout=timeout,
        headers={
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "langflow-bilig-workpaper/0.1.0",
        },
    ) as client:
        response = client.post(endpoint, json={"sheetName": sheet_name, "address": address, "value": value})
        response.raise_for_status()

    parsed = response.json()
    if not isinstance(parsed, dict):
        msg = f"Expected JSON object response, received {type(parsed).__name__}"
        raise TypeError(msg)
    if parsed.get("verified") is not True:
        proof_id = parsed.get("workpaper_id") or parsed.get("id") or "unknown"
        msg = f"Unverified WorkPaper response (verified={parsed.get('verified')}) for workpaper_id={proof_id}"
        raise ValueError(msg)
    return parsed


def compact_proof(proof: dict[str, Any]) -> dict[str, Any]:
    """Keep only stable, UI-friendly formula readback fields from the full proof."""
    before = proof.get("before") if isinstance(proof.get("before"), dict) else {}
    after = proof.get("after") if isinstance(proof.get("after"), dict) else {}
    checks = proof.get("checks") if isinstance(proof.get("checks"), dict) else {}

    return {
        "verified": proof.get("verified") is True,
        "editedCell": proof.get("editedCell"),
        "before": {
            "expectedArr": before.get("expectedArr"),
            "targetGap": before.get("targetGap"),
        },
        "after": {
            "expectedArr": after.get("expectedArr"),
            "targetGap": after.get("targetGap"),
        },
        "checks": {
            "formulasPersisted": checks.get("formulasPersisted") is True,
            "restoredMatchesAfter": checks.get("restoredMatchesAfter") is True,
            "computedOutputChanged": checks.get("computedOutputChanged") is True,
        },
        "source": "Bilig WorkPaper",
        "github": "https://github.com/proompteng/bilig",
    }

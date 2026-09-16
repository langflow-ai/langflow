import json
import os
from typing import Any
from urllib.parse import urlparse
import requests

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from .opticparse_tool import normalize_target_url, resolve_portal_url


class PhishVisionToolComponent(LCToolComponent):
    display_name: str = "PhishVision Threat Scanner"
    description: str = (
        "Real-time zero-day cybersecurity threat intelligence scanner. "
        "Audits URLs and domains for credential harvesting, brand impersonation, and wallet drainers."
    )
    name: str = "PhishVisionTool"
    icon: str = "shield-alert"

    inputs = [
        MessageTextInput(
            name="target",
            display_name="Target URL or Domain",
            info="The website URL or bare domain to inspect (e.g. 'example.com' or 'https://suspicious-login.xyz').",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="PhishVision API Key",
            info="Optional API key for higher throughput. Free trial quota available by default.",
            required=False,
        ),
        MessageTextInput(
            name="portal_url",
            display_name="Portal URL",
            info="PhishVision API Portal URL.",
            value="https://opticparse-api.onrender.com",
            advanced=True,
        ),
    ]

    class PhishVisionToolSchema(BaseModel):
        target: str = Field(..., description="The website URL or bare domain to audit.")

    def _scan_threat(self, target: str) -> str:
        target_url = normalize_target_url(target)
        api_key_str = self.api_key if hasattr(self, "api_key") and self.api_key else ""
        portal = resolve_portal_url(getattr(self, "portal_url", ""), api_key_str)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Langflow-PhishVision-Tool/1.0.0",
        }
        if api_key_str:
            headers["Authorization"] = f"Bearer {api_key_str}"
            headers["X-API-Key"] = api_key_str

        endpoint = f"{portal}/phishvision/scan"
        payload = {"url": target_url}

        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=45,
            allow_redirects=False,
        )

        if response.status_code in (404, 405):
            mcp_endpoint = f"{portal}/mcp"
            rpc_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "phishvision_detect",
                    "arguments": {"target_url": target_url},
                },
            }
            response = requests.post(
                mcp_endpoint,
                json=rpc_payload,
                headers=headers,
                timeout=45,
                allow_redirects=False,
            )

        if response.status_code in (301, 302, 307, 308):
            return "Error: Gateway returned an unexpected redirect. Scan aborted to protect integrity."

        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return json.dumps(data, indent=2)
        return str(data)

    def run_model(self) -> list[Data]:
        audit_json = self._scan_threat(self.target)
        return [Data(data={"result": audit_json}, text=audit_json)]

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="phishvision_scan",
            description="Real-time zero-day cybersecurity phishing and impersonation threat scanner.",
            func=self._scan_threat,
            args_schema=self.PhishVisionToolSchema,
        )

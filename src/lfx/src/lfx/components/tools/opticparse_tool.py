import json
from urllib.parse import urlparse

import requests
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import MessageTextInput, MultilineInput, SecretStrInput
from lfx.schema.data import Data


def normalize_target_url(target: str) -> str:
    clean = target.strip()
    if not clean:
        raise ValueError("Target URL or domain cannot be empty.")

    parsed_initial = urlparse(clean)
    if parsed_initial.scheme and parsed_initial.scheme not in ("http", "https"):
        raise ValueError(f"Invalid or unsupported URL scheme: {parsed_initial.scheme}")

    if not clean.startswith(("http://", "https://")):
        clean = f"https://{clean}"

    parsed = urlparse(clean)
    if not (parsed.scheme in ("http", "https") and parsed.netloc):
        raise ValueError(f"Invalid target URL or domain: {target}")

    return clean


def resolve_portal_url(portal_url: str, api_key: str) -> str:
    portal = (portal_url or "https://opticparse-api.onrender.com").strip().rstrip("/")
    if api_key and portal.startswith("http://"):
        raise ValueError("Insecure HTTP portal URL is not allowed when an API key is configured. Use HTTPS.")
    return portal


class OpticParseToolComponent(LCToolComponent):
    display_name: str = "OpticParse Web Scraper"
    description: str = (
        "Extract structured text and markdown from any URL using multimodal vision. "
        "Bypasses Cloudflare Turnstile, anti-bot protections, and complex dynamic JS SPAs."
    )
    name: str = "OpticParseTool"
    icon: str = "globe"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="Target URL",
            info="The webpage URL to scrape (e.g., 'https://news.ycombinator.com').",
            required=True,
        ),
        MultilineInput(
            name="query",
            display_name="Extraction Query",
            info="Optional natural language prompt specifying fields or sections to extract.",
            value="Extract all primary text, articles, tables, and structured data.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpticParse API Key",
            info="Optional API key for higher rate limits. Free trial quota available by default.",
            required=False,
        ),
        MessageTextInput(
            name="portal_url",
            display_name="Portal URL",
            info="OpticParse API Portal URL.",
            value="https://opticparse-api.onrender.com",
            advanced=True,
        ),
    ]

    class OpticParseToolSchema(BaseModel):
        url: str = Field(..., description="The webpage URL to extract content from.")
        query: str = Field(
            default="Extract all primary text, articles, tables, and structured data.",
            description="Specific instruction on what data or elements to extract.",
        )

    def _scrape_webpage(self, url: str, query: str = "") -> str:
        target_url = normalize_target_url(url)
        api_key_str = self.api_key if hasattr(self, "api_key") and self.api_key else ""
        portal = resolve_portal_url(getattr(self, "portal_url", ""), api_key_str)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Langflow-OpticParse-Tool/1.0.0",
        }
        if api_key_str:
            headers["Authorization"] = f"Bearer {api_key_str}"
            headers["X-API-Key"] = api_key_str

        endpoint = f"{portal}/api/v1/parse"
        payload = {"url": target_url, "query": query or "Extract all primary text."}

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
                    "name": "opticparse_scrape",
                    "arguments": {"target_url": target_url, "extraction_query": query},
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
            return "Error: Gateway returned an unexpected redirect. Request aborted to prevent credential leakage."

        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            if "content" in data:
                return str(data["content"])
            if "result" in data:
                return json.dumps(data["result"], indent=2)
            return json.dumps(data, indent=2)
        return str(data)

    def run_model(self) -> list[Data]:
        content = self._scrape_webpage(self.url, getattr(self, "query", ""))
        return [Data(data={"result": content}, text=content)]

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="opticparse_scrape",
            description="Autonomous multimodal vision web scraper bypassing dynamic JS and bot challenges.",
            func=self._scrape_webpage,
            args_schema=self.OpticParseToolSchema,
        )

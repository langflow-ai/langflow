"""Read a web page or PDF with Clawifi and return its content as markdown."""

from __future__ import annotations

import json
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.clawifi.clawifi_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    ClawifiAPIError,
    clawifi_post,
    error_messages,
    redact,
    require_http_url,
)

QUERY_MAX_LENGTH = 500
TOP_K_MAX = 20
RENDER_MODES = ["never", "auto", "always"]
CONTENT_SCOPES = ["main", "full"]

# ``content_status`` values that mean the page had nothing to read.
_UNREADABLE_STATUS_HINTS = {
    "blocked": "The site blocked the read.",
    "needs_javascript": "The page needs JavaScript. Set Render to auto to read it in a browser.",
    "not_found": "The page was not found.",
}
_PAGE_FIELDS = (
    "url",
    "title",
    "excerpt",
    "language",
    "published_at",
    "modified_at",
    "content_type",
)


class ClawifiFetchComponent(Component):
    """Read one page or PDF through Clawifi.

    Clawifi reads the page on its own servers, so this component only sends the URL
    to ``api.clawifi.dev``. With a query, only the passages that answer it come back.
    """

    display_name = "Clawifi Fetch"
    description = (
        "Read a web page or PDF with Clawifi and return its main content as markdown, "
        "or only the passages that answer a query."
    )
    documentation = f"{DOCUMENTATION_URL}/api/post-fetch"
    icon = "Clawifi"
    name = "ClawifiFetch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Clawifi API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            info="The http(s) URL of the page or PDF to read.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info=(
                "Optional. A question about the page. When set, only the passages that answer it are returned. "
                f"At most {QUERY_MAX_LENGTH} characters."
            ),
            tool_mode=True,
        ),
        IntInput(
            name="top_k",
            display_name="Passages",
            info=f"How many passages to return when a query is set, from 1 to {TOP_K_MAX}.",
            value=5,
            advanced=True,
        ),
        DropdownInput(
            name="render",
            display_name="Render",
            info=(
                "Read the page in a browser: never, auto (only when the page needs JavaScript) or always. "
                "A browser read uses more credits than a plain read."
            ),
            options=RENDER_MODES,
            value="never",
            advanced=True,
        ),
        DropdownInput(
            name="content_scope",
            display_name="Content Scope",
            info="main returns the page's main content; full returns the whole page text.",
            options=CONTENT_SCOPES,
            value="main",
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Clawifi to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Page", name="page", method="fetch_page"),
    ]

    def _build_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"url": require_http_url(self.url)}
        query = str(self.query or "").strip()
        if query:
            if len(query) > QUERY_MAX_LENGTH:
                msg = f"The query is longer than {QUERY_MAX_LENGTH} characters."
                raise ClawifiAPIError(msg)
            payload["query"] = query
            payload["top_k"] = min(max(int(self.top_k or 1), 1), TOP_K_MAX)
        render = str(self.render or "never").strip().lower()
        if render in RENDER_MODES and render != "never":
            payload["render"] = render
        content_scope = str(self.content_scope or "main").strip().lower()
        if content_scope in CONTENT_SCOPES and content_scope != "main":
            payload["content_scope"] = content_scope
        return payload

    def fetch_page(self) -> Data:
        """Return the page as one ``Data`` with the markdown content as ``text``."""
        try:
            payload = self._build_payload()
            body = clawifi_post(
                "/fetch",
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                json=payload,
            )
            page_data = body.get("data")
            if not isinstance(page_data, dict):
                page_data = {}
            status = str(body.get("content_status") or "")
            if body.get("success") is False or status in _UNREADABLE_STATUS_HINTS:
                reason = _UNREADABLE_STATUS_HINTS.get(status) or redact(
                    error_messages(body.get("errors")), self.api_key
                )
                msg = f"Clawifi could not read {payload['url']}"
                if status:
                    msg += f" (content_status: {status})"
                msg = f"{msg}. {reason}" if reason else f"{msg}."
                raise ClawifiAPIError(redact(msg, self.api_key))
            page = self._page_from_record(payload, page_data, body, status)
        except ClawifiAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        self.status = page
        return page

    @staticmethod
    def _page_from_record(
        payload: dict[str, object], page_data: dict[str, Any], body: dict[str, Any], status: str
    ) -> Data:
        """Build the output ``Data`` from the ``data`` record of a fetch response.

        A page or PDF is a ``WebDocument`` with ``content_markdown``. Some URLs, such as
        papers or repositories, are read through an official API and come back as their own
        record type with their own fields; those fields are passed through as they are.
        """
        entity_type = str(body.get("entity_type") or page_data.get("entity_type") or "WebDocument")
        markdown = str(page_data.get("content_markdown") or "")
        if entity_type == "WebDocument":
            result: dict[str, object] = {
                field: page_data[field] for field in _PAGE_FIELDS if page_data.get(field) is not None
            }
            text = markdown
        else:
            result = {key: value for key, value in page_data.items() if value is not None}
            if not result:
                msg = f"Clawifi returned no content for {payload['url']}."
                raise ClawifiAPIError(msg)
            text = markdown or json.dumps(result, ensure_ascii=False, default=str)
        if not text:
            msg = f"Clawifi returned no content for {payload['url']}."
            raise ClawifiAPIError(msg)
        result.setdefault("url", payload["url"])
        if "query" in payload:
            result["query"] = payload["query"]
        result["entity_type"] = entity_type
        result["content_status"] = status or "ok"
        result["content_markdown"] = markdown
        return Data(text=text, data=result)

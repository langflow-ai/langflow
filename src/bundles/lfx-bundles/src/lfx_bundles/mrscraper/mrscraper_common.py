"""Shared client construction, inputs, and response handling for the MrScraper components.

The SDK is an optional dependency, and every one of its methods returns the same
HTTP envelope. Both concerns live here, together with the shared input
definitions, so the seven components stay consistent with each other and with
the standard parameter descriptions used by the MrScraper CLI and SDKs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, quote_plus

from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, DropdownInput, IntInput, MultilineInput, SecretStrInput, StrInput

if TYPE_CHECKING:
    from lfx.custom.custom_component.component import Component

SDK_REQUIREMENT = "mrscraper-sdk>=0.12.0,<0.13.0"
MISSING_SDK_MSG = f"Could not import mrscraper SDK. Please install it with `pip install '{SDK_REQUIREMENT}'`."
DEFAULT_JSON_PROMPT = "Extract all data as complete as possible."

# The dropdown maps to the SDK's tri-state browser_rendering argument.
BROWSER_RENDERING = {"Auto": None, "Enabled": True, "Disabled": False}
NO_SCREENSHOT = "None"
UPGRADE_REQUIRED = (
    "Update the {component} node in the flow editor and review its settings before running it with MrScraper SDK 0.12."
)


def require_updated_node(component: Component, legacy_input: str) -> None:
    """Handle servers that substitute current code while keeping the saved node template."""
    vertex = component.get_vertex()
    if vertex is not None and legacy_input in vertex.data["node"]["template"]:
        raise ValueError(UPGRADE_REQUIRED.format(component=component.display_name))


def build_client(token: str) -> Any:
    """Return an SDK client, or raise an error naming the package to install."""
    if not isinstance(token, str) or not token.strip():
        msg = "MrScraper API token is required"
        raise ValueError(msg)
    try:
        from mrscraper import MrScraper
    except ImportError as e:
        raise ImportError(MISSING_SDK_MSG) from e
    return MrScraper(token=token.strip())


def redact_token(message: str, token: str) -> str:
    """Remove raw, JSON-escaped, and URL-encoded forms of the API token."""
    variants = set()
    for value in {token, token.strip()}:
        if value:
            for escaped in {value, json.dumps(value)[1:-1], json.dumps(value, ensure_ascii=False)[1:-1]}:
                variants.update((escaped, quote(escaped, safe=""), quote_plus(escaped)))
    for value in sorted(variants, key=len, reverse=True):
        message = message.replace(value, "[REDACTED]")
    return message


async def call_sdk(token: str, method: str, **kwargs: Any) -> Any:
    """Call the optional SDK without exposing the configured token in errors."""
    legacy_component = {"account": "MrScraper Account", "scraper_api": "MrScraper Scraper API"}.get(method)
    if method == "web_search" and "url" in kwargs:
        legacy_component = "MrScraper Web Search"
    if legacy_component:
        raise ValueError(UPGRADE_REQUIRED.format(component=legacy_component))

    client = build_client(token)
    from mrscraper import APIError, MrScraperError

    try:
        return await getattr(client, method)(**kwargs)
    except MrScraperError as exc:
        message = redact_token(str(exc), token)
        if isinstance(exc, APIError):
            raise APIError(message, status_code=exc.status_code) from None
        raise type(exc)(message) from None


def payload(response: Any, *, scalar_key: str = "result") -> dict[str, Any]:
    """Return what the API sent, without the SDK's transport envelope.

    ``MrScraper._parse`` wraps every response as ``{"status_code", "data",
    "headers"}``.  A flow wants the payload, not the transport metadata, and the
    SDK raises on any non-2xx status, so the status code carries no information
    by the time a component sees it.

    A non-dict payload (Scrape HTML and Scrape Markdown return text) is boxed
    under ``scalar_key`` so the return value is always a mapping, which is what
    ``Data`` accepts.
    """
    unwrapped = response.get("data", response) if isinstance(response, dict) else response
    return unwrapped if isinstance(unwrapped, dict) else {scalar_key: unwrapped}


def browser_rendering(value: str) -> bool | None:
    """Map the Auto, Enabled, or Disabled choice to the SDK argument."""
    if value not in BROWSER_RENDERING:
        msg = f"browser_rendering must be one of: {', '.join(BROWSER_RENDERING)}"
        raise ValueError(msg)
    return BROWSER_RENDERING[value]


def optional_text(value: str | None) -> str | None:
    """Leave blank optional text fields unset so the SDK omits them."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def optional_integer(value: str | int | None, *, name: str) -> int | None:
    """Keep blank optional numeric fields unset, while preserving explicit zero."""
    if value is None:
        return None
    if isinstance(value, bool):
        msg = f"{name} must be an integer"
        raise TypeError(msg)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        msg = f"{name} must be an integer"
        raise ValueError(msg) from exc


def screenshot_capture(*, value: str | bool | None) -> str | bool:
    """Map the Scrape HTML screenshot choice to False or a capture string."""
    if isinstance(value, bool):
        return "full" if value else False
    text = optional_text(value)
    return False if text is None or text == NO_SCREENSHOT else text


# Shared inputs. Each factory returns a fresh input so components never share instances.


def api_token_input() -> SecretStrInput:
    return SecretStrInput(
        name="api_token",
        display_name="MrScraper API Token",
        required=True,
        password=True,
        info="Your MrScraper API token from https://app.mrscraper.com.",
    )


def url_input() -> MultilineInput:
    return MultilineInput(
        name="url",
        display_name="URL",
        required=True,
        tool_mode=True,
        info="Absolute HTTP or HTTPS URL of the page to process.",
    )


def browser_rendering_input() -> DropdownInput:
    return DropdownInput(
        name="browser_rendering",
        display_name="Browser Rendering",
        options=list(BROWSER_RENDERING),
        value="Auto",
        advanced=True,
        info=(
            "Whether to load the page in a browser: Enabled always does and Disabled never does. "
            "Auto loads the page without a browser first and switches to a browser automatically "
            "if the request is blocked."
        ),
    )


def timeout_input() -> IntInput:
    return IntInput(
        name="timeout",
        display_name="Timeout (seconds)",
        value=300,
        range_spec=RangeSpec(step_type="int", min=1, max=330, step=1),
        advanced=True,
        info="Maximum seconds to wait for the scrape, from 1 to 330. The HTTP request allows 30 additional seconds.",
    )


def warm_start_input() -> BoolInput:
    return BoolInput(
        name="warm_start",
        display_name="Warm Start",
        value=False,
        advanced=True,
        info="Whether to open the site's home page first to warm the session before loading the target URL.",
    )


def block_resources_input() -> BoolInput:
    return BoolInput(
        name="block_resources",
        display_name="Block Resources",
        value=False,
        advanced=True,
        info="Whether to block images, fonts, and stylesheets while loading the page.",
    )


def wait_for_selector_input() -> StrInput:
    return StrInput(
        name="wait_for_selector",
        display_name="Wait for Selector",
        value="",
        advanced=True,
        info=(
            "CSS selector or text to wait for on the page before returning the result, up to 500 characters. "
            "Leave blank to return the page without waiting."
        ),
    )


def action_input() -> StrInput:
    return StrInput(
        name="action",
        display_name="Action",
        value="",
        advanced=True,
        info=(
            "Scraper action that routes the request or simply flags it, useful for separating analytics "
            "per domain. Leave blank to send no action."
        ),
    )


def geo_code_input() -> StrInput:
    return StrInput(
        name="geo_code",
        display_name="Geo Code",
        value="",
        advanced=True,
        info=(
            "Two-letter country code to load the page from, sent in lowercase. "
            "Leave blank to use the API default (United States)."
        ),
    )


def max_age_input() -> IntInput:
    return IntInput(
        name="max_age",
        display_name="Max Age (milliseconds)",
        value=0,
        range_spec=RangeSpec(step_type="int", min=0, max=604800000, step=1),
        advanced=True,
        info=(
            "Return a cached result of the same request when it is newer than the selected age. "
            "A cached result costs the same tokens as the original scrape. Up to 604800000 (7 days); "
            "0 always scrapes fresh."
        ),
    )


def max_retries_input() -> StrInput:
    return StrInput(
        name="max_retries",
        display_name="Max Retries",
        value="",
        advanced=True,
        info="Maximum number of retries, as a nonnegative integer. Leave blank for no limit.",
    )


def page_inputs(*, loading: bool, action: bool) -> list[Any]:
    """Inputs shared by the page components, in the standard parameter order."""
    inputs: list[Any] = []
    if loading:
        inputs.append(browser_rendering_input())
    inputs.append(timeout_input())
    if loading:
        inputs += [warm_start_input(), block_resources_input()]
    inputs.append(wait_for_selector_input())
    if action:
        inputs.append(action_input())
    inputs += [geo_code_input(), max_age_input(), max_retries_input()]
    return inputs


def page_kwargs(component: Any, *, loading: bool) -> dict[str, Any]:
    """SDK keyword arguments for the shared page inputs; blank fields stay ``None``."""
    kwargs: dict[str, Any] = {}
    if loading:
        kwargs["browser_rendering"] = browser_rendering(component.browser_rendering)
    kwargs["timeout"] = component.timeout
    if loading:
        kwargs["warm_start"] = component.warm_start
        kwargs["block_resources"] = component.block_resources
    kwargs.update(
        wait_for_selector=optional_text(component.wait_for_selector),
        geo_code=optional_text(component.geo_code),
        max_age=component.max_age,
        max_retries=optional_integer(component.max_retries, name="max_retries"),
    )
    return kwargs

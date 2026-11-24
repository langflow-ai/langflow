"""MrScraper component contracts using the installed SDK and mocked HTTP."""

from __future__ import annotations

import builtins
import inspect
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from urllib.parse import quote, quote_plus

import httpx
import pytest
from lfx_bundles import mrscraper as components
from lfx_bundles.mrscraper import mrscraper_common
from lfx_bundles.mrscraper.mrscraper_account import MrscraperAccount
from lfx_bundles.mrscraper.mrscraper_common import build_client, call_sdk
from lfx_bundles.mrscraper.mrscraper_fetch_html import MrscraperFetchHtml
from lfx_bundles.mrscraper.mrscraper_get_screenshot import MrscraperGetScreenshot
from lfx_bundles.mrscraper.mrscraper_scrape_brand import MrscraperScrapeBrand
from lfx_bundles.mrscraper.mrscraper_scrape_json import MrscraperScrapeJson
from lfx_bundles.mrscraper.mrscraper_scrape_markdown import MrscraperScrapeMarkdown
from lfx_bundles.mrscraper.mrscraper_web_search import MrscraperWebSearch

if TYPE_CHECKING:
    from lfx.custom.custom_component.component import Component

MOCK_MR_API_TOKEN = "test-mrscraper-sdk-token-placeholder"  # noqa: S105
URL = "https://example.com/page"
DEFAULT_PROMPT = "Extract all data as complete as possible."
# (component class, output method, SDK method, required values)
COMPONENTS = [
    (MrscraperAccount, "get_account", "status", {}),
    (MrscraperFetchHtml, "fetch", "scrape_html", {"url": URL}),
    (MrscraperScrapeMarkdown, "scrape", "scrape_markdown", {"url": URL}),
    (MrscraperGetScreenshot, "capture", "get_screenshot", {"url": URL}),
    (MrscraperScrapeBrand, "extract_brand", "scrape_brand", {"url": URL}),
    (MrscraperScrapeJson, "extract", "scrape_json", {"url": URL}),
    (MrscraperWebSearch, "search", "web_search", {"query": "running shoes"}),
]
# Placeholders that keep the components retired in 1.13.0 discoverable for saved flows.
RETIRED = {
    "MrscraperAiScraper",
    "MrscraperBatchScrape",
    "MrscraperCrawlWebsite",
    "MrscraperGetResult",
    "MrscraperGetResults",
    "MrscraperRunAiScraper",
    "MrscraperRunManualScraper",
}
PAGE_DEFAULTS = {"timeout": "300", "saveResult": "true", "maxAge": "0"}
LOADING_DEFAULTS = {"warmStart": "false", "blockResources": "false"}


def real_sdk():
    """Skip transport/signature tests only when the optional SDK is absent."""
    import mrscraper

    if getattr(mrscraper, "__lfx_test_stub__", False):
        pytest.skip("mrscraper-sdk is not installed")
    return mrscraper


@pytest.fixture
def http_transport(monkeypatch):
    """Use the real SDK with a local transport; never send provider requests."""
    sdk = real_sdk()
    requests = []
    responses = []

    async def handler(request):
        requests.append(request)
        response = responses.pop(0) if responses else httpx.Response(200, json={"ok": True})
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(
        sdk.MrScraper, "_client", lambda _self: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    return requests, responses


class RecordingClient:
    """Stand-in SDK client that records which method was called with which keywords."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, method: str):
        async def call(**kwargs: Any) -> dict[str, Any]:
            self.calls.append((method, kwargs))
            return {"status_code": 200, "data": {"ok": True}, "headers": {}}

        return call


@pytest.fixture
def recording_client(monkeypatch):
    client = RecordingClient()
    monkeypatch.setattr(mrscraper_common, "build_client", lambda _token: client)
    return client


@pytest.fixture
def recording_client_factory(monkeypatch):
    """Switch to a recording SDK client part-way through a test."""

    def install() -> RecordingClient:
        client = RecordingClient()
        monkeypatch.setattr(mrscraper_common, "build_client", lambda _token: client)
        return client

    return install


def configure(component_class: type[Component], **values: Any) -> Component:
    """Instantiate real Langflow inputs and defaults before executing a component."""
    component = component_class()
    component.set(api_token=MOCK_MR_API_TOKEN, **values)
    return component


def query(request: httpx.Request) -> dict[str, str]:
    return dict(request.url.params)


@pytest.mark.unit
def test_services_and_retired_placeholders_are_exported_and_discoverable():
    """Lazy exports and folder discovery expose the seven services and the retired placeholders."""
    from lfx.base.mrscraper import retired
    from lfx.extension.loader._detection import collect_component_classes
    from lfx.extension.loader._discovery import import_bundle_module, iter_bundle_python_files

    expected = {component_class.__name__ for component_class, *_ in COMPONENTS}
    assert set(components.__all__) == expected | RETIRED
    bundle = Path(components.__file__).parent
    discovered = set()
    for path in iter_bundle_python_files(bundle):
        module_name = f"lfx_bundles.mrscraper.{path.stem}"
        module, error, _cause = import_bundle_module(module_name, path)
        assert error is None
        discovered.update(item.__name__ for item in collect_component_classes(module))
    assert discovered == expected | RETIRED
    for name in RETIRED:
        assert issubclass(getattr(components, name), getattr(retired, name))
        assert getattr(components, name).legacy is True
    # Saved flows keep resolving the retained identifiers.
    assert MrscraperAccount.name == "MrscraperAccount"
    assert MrscraperFetchHtml.name == "MrscraperFetchHtml"
    assert MrscraperWebSearch.name == "MrscraperWebSearch"
    assert {getattr(components, name).display_name for name in expected} == {
        "MrScraper Status",
        "MrScraper Scrape HTML",
        "MrScraper Scrape Markdown",
        "MrScraper Get Screenshot",
        "MrScraper Scrape Brand",
        "MrScraper Scrape JSON",
        "MrScraper Web Search",
    }
    assert all(output.name == "data" for name in expected for output in getattr(components, name).outputs)


@pytest.mark.unit
@pytest.mark.parametrize(("component_class", "method_name", "_sdk_method", "values"), COMPONENTS)
@pytest.mark.asyncio
async def test_missing_sdk_error(component_class, method_name, _sdk_method, values):
    """Lazy imports retain a useful installation error in minimal environments."""
    original_import = builtins.__import__

    def import_without_mrscraper(name, *args, **kwargs):
        if name == "mrscraper":
            msg = "No module named 'mrscraper'"
            raise ImportError(msg)
        return original_import(name, *args, **kwargs)

    with (
        patch("builtins.__import__", side_effect=import_without_mrscraper),
        pytest.raises(ImportError, match=r"mrscraper-sdk>=0\.12\.0,<0\.13\.0"),
    ):
        await getattr(configure(component_class, **values), method_name)()


@pytest.mark.unit
@pytest.mark.parametrize(("component_class", "method_name", "sdk_method", "values"), COMPONENTS)
@pytest.mark.asyncio
async def test_default_inputs_send_exact_sdk_keywords(
    recording_client, component_class, method_name, sdk_method, values
):
    """Default inputs pass every documented keyword; blank optional fields stay None."""
    await getattr(configure(component_class, **values), method_name)()
    page = {"timeout": 300, "wait_for_selector": None, "geo_code": None, "max_age": 0, "max_retries": None}
    loading = {"browser_rendering": None, "warm_start": False, "block_resources": False}
    expected = {
        "status": {},
        "scrape_html": {"url": URL, **loading, **page, "action": None, "screenshot": False},
        "scrape_markdown": {"url": URL, **loading, **page, "action": None},
        "get_screenshot": {"url": URL, "screenshot": "full", **page},
        "scrape_brand": {"url": URL},
        "scrape_json": {"url": URL, "prompt": DEFAULT_PROMPT, "html": True, **loading, **page, "screenshot": False},
        "web_search": {"query": "running shoes", "country": None, "num_results": 10},
    }[sdk_method]
    assert recording_client.calls == [(sdk_method, expected)]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_status_returns_the_raw_account_body(http_transport):
    """Status uses the platform account endpoint and returns the body unchanged."""
    requests, responses = http_transport
    body = {"message": "Account found", "data": {"tokenLimit": 100, "tokenUsage": 25, "user": {"email": "u@x.io"}}}
    responses.append(httpx.Response(200, json=body))
    output = await configure(MrscraperAccount).get_account()
    request = requests[0]
    assert request.method == "GET"
    assert str(request.url) == "https://api.app.mrscraper.com/api/v1/subscription-accounts"
    assert request.headers["x-api-token"] == MOCK_MR_API_TOKEN
    assert output.data == body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_html_defaults_and_text_output(http_transport):
    """Scrape HTML sends html=true and the documented defaults; text is boxed as html."""
    requests, responses = http_transport
    responses.append(httpx.Response(200, text="<html>plain</html>", headers={"content-type": "text/html"}))
    output = await configure(MrscraperFetchHtml, url=URL).fetch()
    request = requests[0]
    assert request.method == "GET"
    assert request.url.host == "api.mrscraper.com"
    assert query(request) == {
        "url": URL,
        "html": "true",
        "markdown": "false",
        "timeout": "300",
        **LOADING_DEFAULTS,
        "saveResult": "true",
        "maxAge": "0",
        "screenshot": "false",
    }
    assert list(query(request)) == [
        "url",
        "html",
        "markdown",
        "timeout",
        "warmStart",
        "blockResources",
        "saveResult",
        "maxAge",
        "screenshot",
    ]
    assert "token" not in query(request)
    assert request.extensions["timeout"]["read"] == 330
    assert output.data == {"html": "<html>plain</html>"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_html_maps_every_option(http_transport):
    """Every Scrape HTML input reaches the request, explicit zero is kept, and a screenshot renders."""
    requests, responses = http_transport
    expected = {"html": "<html>page</html>", "screenshot": "base64-image"}
    responses.append(httpx.Response(200, json=expected))
    output = await configure(
        MrscraperFetchHtml,
        url=f"  {URL}\n",
        screenshot="1920x1080-75",
        browser_rendering="Disabled",
        timeout=45,
        warm_start=True,
        block_resources=True,
        wait_for_selector=" .ready ",
        action=" analytics ",
        geo_code="ID",
        max_age=86400000,
        max_retries="0",
    ).fetch()
    request = requests[0]
    assert list(query(request).items()) == [
        ("url", URL),
        ("html", "true"),
        ("markdown", "false"),
        # A screenshot needs a rendered page, so it overrides Disabled.
        ("browserRendering", "true"),
        ("timeout", "45"),
        ("warmStart", "true"),
        ("blockResources", "true"),
        ("waitForSelector", ".ready"),
        ("action", "analytics"),
        ("geoCode", "id"),
        # Results are always saved; tokenCap is never sent.
        ("saveResult", "true"),
        ("maxAge", "86400000"),
        ("maxRetries", "0"),
        ("screenshot", "1920x1080-75"),
    ]
    assert request.extensions["timeout"]["read"] == 75
    assert output.data == expected


@pytest.mark.unit
@pytest.mark.parametrize("screenshot", ["full", "top", "1280x800"])
@pytest.mark.parametrize("rendering", ["Auto", "Enabled", "Disabled"])
@pytest.mark.asyncio
async def test_scrape_html_screenshot_always_sends_browser_rendering(http_transport, screenshot, rendering):
    """Any screenshot sends browserRendering=true, whatever the rendering choice."""
    requests, _responses = http_transport
    await configure(MrscraperFetchHtml, url=URL, screenshot=screenshot, browser_rendering=rendering).fetch()
    assert query(requests[0])["browserRendering"] == "true"
    assert query(requests[0])["screenshot"] == screenshot


@pytest.mark.unit
@pytest.mark.parametrize(
    ("component_class", "method_name"),
    [(MrscraperFetchHtml, "fetch"), (MrscraperScrapeMarkdown, "scrape"), (MrscraperScrapeJson, "extract")],
)
@pytest.mark.parametrize(("rendering", "sent"), [("Auto", None), ("Enabled", "true"), ("Disabled", "false")])
@pytest.mark.asyncio
async def test_browser_rendering_choices(http_transport, component_class, method_name, rendering, sent):
    """Auto omits browserRendering; Enabled and Disabled send true and false."""
    requests, _responses = http_transport
    await getattr(configure(component_class, url=URL, browser_rendering=rendering), method_name)()
    assert query(requests[0]).get("browserRendering") == sent


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_markdown_defaults_options_and_text_output(http_transport):
    """Scrape Markdown sends markdown=true; text is boxed as markdown."""
    requests, responses = http_transport
    responses.append(httpx.Response(200, text="# Page", headers={"content-type": "text/markdown"}))
    responses.append(httpx.Response(200, text="# Page", headers={"content-type": "text/markdown"}))
    output = await configure(MrscraperScrapeMarkdown, url=URL).scrape()
    await configure(
        MrscraperScrapeMarkdown,
        url=URL,
        browser_rendering="Disabled",
        block_resources=True,
        action="docs",
        geo_code="gb",
        max_retries="1",
    ).scrape()
    assert list(query(requests[0]).items()) == [
        ("url", URL),
        ("markdown", "true"),
        ("html", "false"),
        ("screenshot", "false"),
        ("timeout", "300"),
        ("warmStart", "false"),
        ("blockResources", "false"),
        ("saveResult", "true"),
        ("maxAge", "0"),
    ]
    assert query(requests[1]) == {
        "url": URL,
        "markdown": "true",
        "html": "false",
        "screenshot": "false",
        "browserRendering": "false",
        "timeout": "300",
        "warmStart": "false",
        "blockResources": "true",
        "action": "docs",
        "geoCode": "gb",
        "saveResult": "true",
        "maxAge": "0",
        "maxRetries": "1",
    }
    assert output.data == {"markdown": "# Page"}


@pytest.mark.unit
@pytest.mark.parametrize("area", [None, "full", "top", "1280x800", "1920x1080-75"])
@pytest.mark.asyncio
async def test_get_screenshot_sends_the_area_and_fixed_fields(http_transport, recording_client_factory, area):
    """Get Screenshot sends the chosen area (full by default) with html=false, markdown=false, and rendering."""
    requests, responses = http_transport
    expected = {"html": "<html>page</html>", "screenshot": "base64-image"}
    responses.append(httpx.Response(200, json=expected))
    values = {"url": URL} if area is None else {"url": URL, "screenshot": area}
    output = await configure(MrscraperGetScreenshot, **values).capture()
    assert list(query(requests[0]).items()) == [
        ("url", URL),
        ("screenshot", area or "full"),
        ("html", "false"),
        ("markdown", "false"),
        ("browserRendering", "true"),
        ("timeout", "300"),
        ("saveResult", "true"),
        ("maxAge", "0"),
    ]
    assert output.data == expected
    client = recording_client_factory()
    await configure(MrscraperGetScreenshot, **values).capture()
    assert client.calls == [
        (
            "get_screenshot",
            {
                "url": URL,
                "screenshot": area or "full",
                "timeout": 300,
                "wait_for_selector": None,
                "geo_code": None,
                "max_age": 0,
                "max_retries": None,
            },
        )
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_screenshot_maps_the_page_options(http_transport):
    """Get Screenshot passes its page options in the standard order after the fixed fields."""
    requests, _responses = http_transport
    await configure(
        MrscraperGetScreenshot,
        url=URL,
        screenshot="top",
        timeout=120,
        wait_for_selector="#results",
        geo_code="DE",
        max_retries="2",
    ).capture()
    assert list(query(requests[0]).items()) == [
        ("url", URL),
        ("screenshot", "top"),
        ("html", "false"),
        ("markdown", "false"),
        ("browserRendering", "true"),
        ("timeout", "120"),
        ("waitForSelector", "#results"),
        ("geoCode", "de"),
        ("saveResult", "true"),
        ("maxAge", "0"),
        ("maxRetries", "2"),
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_brand_sends_only_the_url_and_fixed_fields(http_transport):
    """Scrape Brand takes only the URL; the SDK adds action and bundle and waits 120 seconds."""
    requests, responses = http_transport
    brand = {"data": {"job_id": "job-1", "status": "succeeded", "brand": {"colors": {}}}, "message": "ok"}
    responses.append(httpx.Response(200, json=brand))
    output = await configure(MrscraperScrapeBrand, url=f" {URL}\n").extract_brand()
    assert {i.name for i in MrscraperScrapeBrand.inputs} == {"api_token", "url"}
    assert list(query(requests[0]).items()) == [("action", "brand-scraping"), ("url", URL), ("bundle", "none")]
    assert requests[0].extensions["timeout"]["read"] == 120
    assert output.data == brand


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_json_defaults_options_and_post_fallback(http_transport):
    """Scrape JSON uses GET with agent=general and switches to POST for long prompts."""
    requests, responses = http_transport
    result = {"success": True, "data": {"title": "Example"}, "html": "<html></html>"}
    responses.extend([httpx.Response(200, json=result) for _ in range(3)])
    output = await configure(MrscraperScrapeJson, url=URL).extract()
    await configure(
        MrscraperScrapeJson,
        url=URL,
        prompt="Extract the title",
        html=False,
        screenshot=True,
        browser_rendering="Enabled",
        warm_start=True,
        wait_for_selector="body",
    ).extract()
    long_prompt = "Extract every field. Json Schema: " + "x" * 8000
    await configure(MrscraperScrapeJson, url=URL, prompt=long_prompt).extract()
    assert requests[0].method == "GET"
    assert query(requests[0]) == {
        "url": URL,
        "prompt": DEFAULT_PROMPT,
        "agent": "general",
        "html": "true",
        "timeout": "300",
        **LOADING_DEFAULTS,
        "saveResult": "true",
        "maxAge": "0",
        "screenshot": "false",
    }
    assert query(requests[1]) == {
        "url": URL,
        "prompt": "Extract the title",
        "agent": "general",
        "html": "false",
        "browserRendering": "true",
        "timeout": "300",
        "warmStart": "true",
        "blockResources": "false",
        "waitForSelector": "body",
        "saveResult": "true",
        "maxAge": "0",
        "screenshot": "true",
    }
    assert requests[2].method == "POST"
    assert json.loads(requests[2].content) == {"url": URL, "prompt": long_prompt, "agent": "general"}
    assert not {"url", "prompt", "agent"} & set(query(requests[2]))
    assert output.data == result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_web_search_sends_country_only_when_set(http_transport):
    """Web Search sends action=websearch, trims the query, and omits a blank country."""
    requests, responses = http_transport
    results = {"success": True, "data": [{"rank": 1, "title": "Example"}]}
    responses.extend([httpx.Response(200, json=results), httpx.Response(200, json=results)])
    output = await configure(MrscraperWebSearch, query=" running shoes ").search()
    await configure(MrscraperWebSearch, query="running shoes", country="ID", num_results=20).search()
    assert list(query(requests[0]).items()) == [
        ("action", "websearch"),
        ("query", "running shoes"),
        ("numResults", "10"),
    ]
    assert query(requests[1]) == {"action": "websearch", "query": "running shoes", "country": "id", "numResults": "20"}
    assert requests[0].extensions["timeout"]["read"] == 120
    assert output.data == results


@pytest.mark.unit
@pytest.mark.parametrize(
    ("component_class", "method_name", "values", "message"),
    [
        (MrscraperFetchHtml, "fetch", {"url": "example.com"}, "url"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "timeout": 0}, "timeout"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "timeout": 331}, "timeout"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "max_age": -1}, "max_age"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "max_age": 604800001}, "max_age"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "max_retries": "-1"}, "max_retries"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "max_retries": "1.5"}, "max_retries"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "geo_code": "usa"}, "geo_code"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "wait_for_selector": "a" * 501}, "wait_for_selector"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "screenshot": "99x800"}, "screenshot"),
        (MrscraperFetchHtml, "fetch", {"url": URL, "browser_rendering": "Sometimes"}, "browser_rendering"),
        (MrscraperScrapeMarkdown, "scrape", {"url": URL, "geo_code": "1a"}, "geo_code"),
        (MrscraperGetScreenshot, "capture", {"url": URL, "timeout": 331}, "timeout"),
        (MrscraperGetScreenshot, "capture", {"url": URL, "screenshot": "99x800"}, "screenshot"),
        (MrscraperGetScreenshot, "capture", {"url": URL, "screenshot": "None"}, "screenshot"),
        (MrscraperScrapeBrand, "extract_brand", {"url": "example.com"}, "url"),
        (MrscraperScrapeJson, "extract", {"url": URL, "prompt": " "}, "prompt"),
        (MrscraperWebSearch, "search", {"query": " "}, "query"),
        (MrscraperWebSearch, "search", {"query": "test", "num_results": 9}, "num_results"),
        (MrscraperWebSearch, "search", {"query": "test", "num_results": 101}, "num_results"),
        (MrscraperWebSearch, "search", {"query": "test", "country": "usa"}, "country"),
    ],
)
@pytest.mark.asyncio
async def test_invalid_options_fail_before_http(http_transport, component_class, method_name, values, message):
    """Invalid input is rejected before any request rather than silently replaced by a default."""
    requests, _responses = http_transport
    with pytest.raises(ValueError, match=message):
        await getattr(configure(component_class, **values), method_name)()
    assert requests == []


@pytest.mark.unit
@pytest.mark.parametrize("status", [401, 422, 500])
@pytest.mark.asyncio
async def test_api_errors_propagate_without_token(http_transport, status):
    """Provider errors fail the node and keep the token out of the message."""
    sdk = real_sdk()
    _requests, responses = http_transport
    responses.append(httpx.Response(status, json={"message": f"request failed {MOCK_MR_API_TOKEN}"}))
    with pytest.raises(sdk.MrScraperError) as error:
        await configure(MrscraperFetchHtml, url=URL).fetch()
    assert MOCK_MR_API_TOKEN not in str(error.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_network_timeout_propagates(http_transport):
    """A failed HTTP request is surfaced through the SDK network exception."""
    sdk = real_sdk()
    _requests, responses = http_transport
    responses.append(httpx.ReadTimeout("Timed out"))
    with pytest.raises(sdk.NetworkError, match="Timed out"):
        await configure(MrscraperAccount).get_account()


@pytest.mark.unit
@pytest.mark.parametrize("token", [None, "", "   "])
def test_blank_token_never_uses_environment_credentials(monkeypatch, token):
    """A component must use its configured credential, even when the SDK env var exists."""
    monkeypatch.setenv("MRSCRAPER_API_TOKEN", MOCK_MR_API_TOKEN)
    with pytest.raises(ValueError, match="API token is required"):
        build_client(token)


@pytest.mark.unit
@pytest.mark.parametrize(
    "encoding", ["raw", "quoted", "plus", "json", "quoted_json", "plus_json", "quoted_unicode_json"]
)
@pytest.mark.asyncio
async def test_network_errors_redact_every_token_variant(http_transport, encoding):
    """Redact raw, URL-encoded, and JSON-escaped tokens while preserving the exception kind."""
    sdk = real_sdk()
    _requests, responses = http_transport
    # Header-safe ASCII that still changes under URL and JSON encoding.
    token = 'private token/"value"+x'  # noqa: S105
    transform = {
        "raw": lambda value: value,
        "quoted": lambda value: quote(value, safe=""),
        "plus": quote_plus,
        "json": lambda value: json.dumps(value)[1:-1],
        "quoted_json": lambda value: quote(json.dumps(value)[1:-1], safe=""),
        "plus_json": lambda value: quote_plus(json.dumps(value)[1:-1]),
        "quoted_unicode_json": lambda value: quote(json.dumps(value, ensure_ascii=False)[1:-1], safe=""),
    }[encoding]
    responses.append(httpx.ReadTimeout("Timed out with " + transform(token)))
    with pytest.raises(sdk.NetworkError) as error:
        await call_sdk(token, "scrape_html", url=URL)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__
    assert "Timed out" in str(error.value)
    assert "[REDACTED]" in str(error.value)
    assert transform(token) not in str(error.value)


@pytest.mark.unit
class TestSdkContract:
    """Check call-site keywords against the real package, independent of HTTP mocks."""

    def test_client_accepts_token_kwarg(self):
        assert "token" in inspect.signature(real_sdk().MrScraper).parameters

    @pytest.mark.parametrize(("component_class", "method_name", "sdk_method", "values"), COMPONENTS)
    @pytest.mark.asyncio
    async def test_components_expose_every_sdk_keyword(
        self, recording_client, component_class, method_name, sdk_method, values
    ):
        """Each component passes exactly the SDK method's documented parameters."""
        await getattr(configure(component_class, **values), method_name)()
        [(called, kwargs)] = recording_client.calls
        assert called == sdk_method
        parameters = set(inspect.signature(getattr(real_sdk().MrScraper, sdk_method)).parameters) - {"self"}
        assert set(kwargs) == parameters

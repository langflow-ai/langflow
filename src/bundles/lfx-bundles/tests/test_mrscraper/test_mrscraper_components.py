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
from lfx_bundles.mrscraper.mrscraper_account import MrscraperAccount
from lfx_bundles.mrscraper.mrscraper_common import build_client, call_sdk
from lfx_bundles.mrscraper.mrscraper_fetch_html import MrscraperFetchHtml
from lfx_bundles.mrscraper.mrscraper_web_search import MrscraperWebSearch

if TYPE_CHECKING:
    from lfx.custom.custom_component.component import Component

MOCK_MR_API_TOKEN = "test-mrscraper-sdk-token-placeholder"  # noqa: S105
COMPONENTS = [(MrscraperAccount, "get_account"), (MrscraperFetchHtml, "fetch"), (MrscraperWebSearch, "search")]


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


def configure(component_class: type[Component], **values: Any) -> Component:
    """Instantiate real Langflow inputs and defaults before executing a component."""
    component = component_class()
    component.set(api_token=MOCK_MR_API_TOKEN, **values)
    return component


@pytest.mark.unit
def test_exactly_three_components_are_exported_and_discoverable():
    """Both lazy exports and bundle folder discovery expose the same three tools."""
    from lfx.extension.loader._detection import collect_component_classes
    from lfx.extension.loader._discovery import import_bundle_module, iter_bundle_python_files

    expected = {"MrscraperAccount", "MrscraperFetchHtml", "MrscraperWebSearch"}
    assert set(components.__all__) == expected
    bundle = Path(components.__file__).parent
    discovered = set()
    for path in iter_bundle_python_files(bundle):
        module_name = f"lfx_bundles.mrscraper.{path.stem}"
        module, error, _cause = import_bundle_module(module_name, path)
        assert error is None
        discovered.update(item.__name__ for item in collect_component_classes(module))
    assert discovered == expected
    assert MrscraperFetchHtml.name == "MrscraperFetchHtml"
    assert {getattr(components, name).display_name for name in expected} == {
        "MrScraper Account",
        "MrScraper Scraper API",
        "MrScraper Web Search",
    }


@pytest.mark.unit
@pytest.mark.parametrize(("component_class", "method_name"), COMPONENTS)
@pytest.mark.asyncio
async def test_missing_sdk_error(component_class, method_name):
    """Lazy imports retain a useful installation error in minimal environments."""
    original_import = builtins.__import__

    def import_without_mrscraper(name, *args, **kwargs):
        if name == "mrscraper":
            msg = "No module named 'mrscraper'"
            raise ImportError(msg)
        return original_import(name, *args, **kwargs)

    with (
        patch("builtins.__import__", side_effect=import_without_mrscraper),
        pytest.raises(ImportError, match=r"0\.6\.0"),
    ):
        await getattr(configure(component_class), method_name)()


@pytest.mark.unit
@pytest.mark.parametrize("wrapped", [True, False])
@pytest.mark.asyncio
async def test_account_returns_safe_summary(http_transport, wrapped):
    """Account uses authenticated GET and excludes keys, billing, and the envelope."""
    requests, responses = http_transport
    details = {
        "stripeStatus": "active",
        "isEnterprise": True,
        "tokenLimit": "100",
        "tokenUsage": 25,
        "rateLimit": 10,
        "rateTtl": 60,
        "isAutoRenew": True,
        "endsAt": "2026-11-01T00:00:00Z",
        "stripeCustomerId": "private-billing",
        "user": {
            "name": "Test User",
            "email": "user@example.com",
            "isVerified": True,
            "latestApiToken": "private-token",
        },
    }
    responses.append(httpx.Response(200, json={"data": details} if wrapped else details))
    output = await configure(MrscraperAccount, timeout=12).get_account()
    request = requests[0]
    assert request.method == "GET"
    assert str(request.url) == "https://api.app.mrscraper.com/api/v1/subscription-accounts"
    assert request.headers["authorization"] == f"Bearer {MOCK_MR_API_TOKEN}"
    assert request.headers["x-api-token"] == MOCK_MR_API_TOKEN
    assert request.extensions["timeout"]["read"] == 12
    assert output.data == {
        "subscription_status": "active",
        "enterprise": True,
        "token_usage": 25,
        "token_limit": 100,
        "token_remaining": 75,
        "usage_percent": 25,
        "rate_limit": 10,
        "rate_ttl": 60,
        "auto_renew": True,
        "ends_at": "2026-11-01T00:00:00Z",
        "user": {"name": "Test User", "email": "user@example.com", "verified": True},
    }
    assert "private" not in json.dumps(output.data)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scraper_api_maps_all_options_without_losing_false_or_zero(http_transport):
    """UI controls map to SDK query/body/header options, including screenshot forcing."""
    requests, responses = http_transport
    expected = {"html": "<html>page</html>", "markdown": "# Page", "screenshot": "base64-image"}
    responses.append(httpx.Response(200, json=expected))
    component = configure(
        MrscraperFetchHtml,
        url="https://example.com/page",
        html=True,
        markdown=True,
        screenshot=True,
        browser_rendering="Disabled",
        super=True,
        timeout=45,
        geo_code="ID",
        proxy_country="SG",
        use_proxy=False,
        proxy="user:pass@proxy.example:8000",
        bypass_proxy=True,
        block_resources=True,
        wait_for_selector=".ready",
        home_page=True,
        cookie_jar="domain=example.com&country=sg",
        headers='{"accept-language": "en-US"}',
        max_retries=0,
        token_cap="0",  # noqa: S106
        stream="Disabled",
        discard_token_secret="discard-test-value",  # noqa: S106
    )
    output = await component.fetch()
    request = requests[0]
    assert request.method == "POST"
    assert request.url.host == "api.mrscraper.com"
    assert json.loads(request.content) == {"url": "https://example.com/page", "maxRetries": 0, "tokenCap": 0}
    assert dict(request.url.params) == {
        "token": MOCK_MR_API_TOKEN,
        "timeout": "45",
        "geoCode": "ID",
        "proxyCountry": "SG",
        "browserRendering": "true",
        "super": "true",
        "useProxy": "false",
        "proxy": "user:pass@proxy.example:8000",
        "html": "true",
        "markdown": "true",
        "waitForSelector": ".ready",
        "warmStart": "true",
        "screenshot": "true",
        "blockResources": "true",
        "bypassProxy": "true",
        "cookieJar": "domain=example.com&country=sg",
        "headers": '{"accept-language": "en-US"}',
        "stream": "false",
    }
    assert request.headers["x-discard-token-secret"] == "discard-test-value"
    assert request.headers["authorization"] == f"Bearer {MOCK_MR_API_TOKEN}"
    assert request.extensions["timeout"]["read"] == 75
    assert output.data == expected


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scraper_defaults_and_html_output_remain_compatible(http_transport):
    """Automatic browser fallback and unset token budget survive default Langflow inputs."""
    requests, responses = http_transport
    responses.append(httpx.Response(200, text="<html>plain</html>"))
    output = await configure(MrscraperFetchHtml, url="https://example.com").fetch()
    assert output.data == {"html": "<html>plain</html>"}
    assert json.loads(requests[0].content) == {"url": "https://example.com", "maxRetries": 3}
    assert "browserRendering" not in requests[0].url.params
    assert "super" not in requests[0].url.params
    assert "stream" not in requests[0].url.params
    assert requests[0].url.params["html"] == "true"
    assert requests[0].url.params["markdown"] == "false"


@pytest.mark.unit
@pytest.mark.parametrize("overrides", [{}, {"region": "id", "language": "id", "page": "2"}])
@pytest.mark.asyncio
async def test_web_search_normalizes_google_url(http_transport, overrides):
    """Google URL defaults and explicit overrides are delegated to the SDK v2 API."""
    requests, responses = http_transport
    responses.append(httpx.Response(200, json={"organic": [{"title": "Example"}]}))
    output = await configure(
        MrscraperWebSearch,
        url="https://www.google.com/search?q=running+shoes&gl=us&hl=en&start=20",
        raw=False,
        render_js=True,
        **overrides,
    ).search()
    request = requests[0]
    assert str(request.url) == "https://sync.scraper.mrscraper.com/api/google/serp/v2/sync"
    assert json.loads(request.content) == {
        "query": "running shoes",
        "region": overrides.get("region", "us"),
        "language": overrides.get("language", "en"),
        "page": int(overrides.get("page", 3)),
        "format": "json",
        "renderJs": True,
    }
    assert output.data == {"organic": [{"title": "Example"}]}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_web_search_defaults_to_raw_html(http_transport):
    """Raw is true by SDK default and takes precedence over the JSON format field."""
    requests, responses = http_transport
    responses.append(httpx.Response(200, text="<html>SERP</html>"))
    output = await configure(MrscraperWebSearch, url="example query").search()
    assert json.loads(requests[0].content) == {"query": "example query", "format": "html", "renderJs": False}
    assert output.data == {"result": "<html>SERP</html>"}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("component_class", "method_name", "values", "message"),
    [
        (MrscraperAccount, "get_account", {"timeout": 0}, "timeout"),
        (MrscraperFetchHtml, "fetch", {"url": "https://example.com", "timeout": 301}, "timeout"),
        (MrscraperFetchHtml, "fetch", {"url": "https://example.com", "max_retries": -1}, "max_retries"),
        (MrscraperFetchHtml, "fetch", {"url": "https://example.com", "token_cap": "-1"}, "token_cap"),
        (MrscraperWebSearch, "search", {"url": "test", "page": "0"}, "page"),
        (MrscraperWebSearch, "search", {"url": "test", "page": "1.5"}, "page"),
        (MrscraperWebSearch, "search", {"url": "test", "timeout": 0}, "timeout"),
        (MrscraperWebSearch, "search", {"url": " "}, "query"),
    ],
)
@pytest.mark.asyncio
async def test_invalid_options_fail_before_http(http_transport, component_class, method_name, values, message):
    """Invalid input is rejected rather than silently replaced by a default."""
    requests, _responses = http_transport
    with pytest.raises(ValueError, match=message):
        await getattr(configure(component_class, **values), method_name)()
    assert requests == []


@pytest.mark.unit
@pytest.mark.parametrize("status", [401, 422, 500])
@pytest.mark.asyncio
async def test_api_errors_propagate_without_query_token(http_transport, status):
    """Provider errors fail the node and keep the query token out of the message."""
    sdk = real_sdk()
    _requests, responses = http_transport
    responses.append(httpx.Response(status, json={"message": "request failed"}))
    with pytest.raises(sdk.MrScraperError) as error:
        await configure(MrscraperFetchHtml, url="https://example.com").fetch()
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
@pytest.mark.asyncio
async def test_http_error_redacts_proxy_cookie_and_target_headers(http_transport):
    """HTTP status errors include the request URL, whose optional query values may be secrets."""
    sdk = real_sdk()
    _requests, responses = http_transport
    responses.append(httpx.Response(422, json={"message": "request failed"}))
    proxy = "user:private-proxy@proxy.example:8000"
    cookie_jar = "domain=example.com&cookie=private-cookie-value"
    headers = json.dumps({"Authorization": 'Bearer private-header-value "quoted"'})
    with pytest.raises(sdk.APIError) as error:
        await configure(
            MrscraperFetchHtml,
            url="https://example.com",
            proxy=proxy,
            cookie_jar=cookie_jar,
            headers=headers,
        ).fetch()
    assert error.value.status_code == 422
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__
    for value in (
        MOCK_MR_API_TOKEN,
        proxy,
        cookie_jar,
        headers,
        "private-proxy",
        "private-cookie-value",
        "private-header-value",
    ):
        assert value not in str(error.value)
    assert "422" in str(error.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    "encoding", ["raw", "quoted", "plus", "json", "quoted_json", "plus_json", "quoted_unicode_json"]
)
@pytest.mark.asyncio
async def test_network_errors_redact_all_configured_secret_variants(http_transport, encoding):
    """Redact raw, URL-encoded, and JSON-escaped credentials while preserving the exception kind."""
    sdk = real_sdk()
    _requests, responses = http_transport
    values = {
        "proxy": "user:private-proxy value@proxy.example:8000",
        "cookie_jar": "domain=example.com&cookie=private-cookie value",
        "discard_token_secret": "private-discard/value",
        "headers": json.dumps({"Authorization": 'Bearer private-header "válue"', "X-Session": "private-session/value"}),
    }
    secrets = [MOCK_MR_API_TOKEN, *values.values(), *json.loads(values["headers"]).values()]
    transform = {
        "raw": lambda value: value,
        "quoted": lambda value: quote(value, safe=""),
        "plus": quote_plus,
        "json": lambda value: json.dumps(value)[1:-1],
        "quoted_json": lambda value: quote(json.dumps(value)[1:-1], safe=""),
        "plus_json": lambda value: quote_plus(json.dumps(value)[1:-1]),
        "quoted_unicode_json": lambda value: quote(json.dumps(value, ensure_ascii=False)[1:-1], safe=""),
    }[encoding]
    variants = [transform(value) for value in secrets]
    responses.append(httpx.ReadTimeout("Timed out with " + " | ".join(variants)))
    with pytest.raises(sdk.NetworkError) as error:
        await call_sdk(MOCK_MR_API_TOKEN, "scraper_api", url="https://example.com", **values)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__
    assert "Timed out" in str(error.value)
    assert "[REDACTED]" in str(error.value)
    for value in variants:
        assert value not in str(error.value)


@pytest.mark.unit
class TestSdkContract:
    """Check call-site keywords against the real package, independent of HTTP mocks."""

    def test_client_accepts_token_kwarg(self):
        assert "token" in inspect.signature(real_sdk().MrScraper).parameters

    @pytest.mark.parametrize(
        ("method_name", "call_site_kwargs"),
        [
            ("account", {"timeout"}),
            (
                "scraper_api",
                {
                    "url",
                    "html",
                    "markdown",
                    "screenshot",
                    "browser_rendering",
                    "super",
                    "timeout",
                    "geo_code",
                    "block_resources",
                    "proxy_country",
                    "use_proxy",
                    "proxy",
                    "bypass_proxy",
                    "wait_for_selector",
                    "home_page",
                    "cookie_jar",
                    "headers",
                    "max_retries",
                    "token_cap",
                    "stream",
                    "discard_token_secret",
                },
            ),
            ("web_search", {"url", "raw", "format", "region", "language", "page", "render_js", "timeout"}),
        ],
    )
    def test_call_site_kwargs_still_accepted(self, method_name, call_site_kwargs):
        method = getattr(real_sdk().MrScraper, method_name)
        assert call_site_kwargs <= set(inspect.signature(method).parameters) - {"self"}

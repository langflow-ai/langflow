"""Unit tests for the Geekflare extension bundle (``lfx-geekflare``).

The components call the Geekflare API with ``httpx``; the tests patch
``httpx.post`` at the shared helper module to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_geekflare import GeekflareScrapeComponent, GeekflareSearchComponent, GeekflareWebsiteCheckComponent
from lfx_geekflare.components.geekflare.geekflare_website_check import CHECKS

POST_PATCH_TARGET = "lfx_geekflare.components.geekflare._api.httpx.post"
API_KEY = "test-key"  # pragma: allowlist secret

SEARCH_PAYLOAD = {
    "apiStatus": "success",
    "apiCode": 200,
    "data": [
        {"title": "Result one", "url": "https://example.com/one", "snippet": "First snippet.", "position": 1},
        {"title": "Result two", "url": "https://example.com/two", "snippet": "Second snippet.", "position": 2},
    ],
}

SERP_PAYLOAD = {
    "apiStatus": "success",
    "apiCode": 200,
    "data": {
        "organic": [
            {"title": "Organic one", "link": "https://example.com/a", "description": "Desc A.", "position": 1},
        ],
        "people_also_ask": [{"question": "What is it?"}],
    },
}


def _response(status_code: int = 200, payload: object | None = None) -> httpx.Response:
    return httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://api.geekflare.com/x"),
        json=payload if payload is not None else {"apiStatus": "success", "data": {"ok": True}},
    )


@pytest.fixture
def search() -> GeekflareSearchComponent:
    c = GeekflareSearchComponent()
    c.input_value = "best crm"
    c.geekflare_api_key = API_KEY
    c.source = "web"
    c.serp = False
    c.location = ""
    c.city = ""
    c.max_results = 10
    return c


@pytest.fixture
def scrape() -> GeekflareScrapeComponent:
    c = GeekflareScrapeComponent()
    c.url = "example.com"
    c.geekflare_api_key = API_KEY
    c.output_format = "markdown"
    c.template = "none"
    return c


@pytest.fixture
def check() -> GeekflareWebsiteCheckComponent:
    c = GeekflareWebsiteCheckComponent()
    c.url = "example.com"
    c.geekflare_api_key = API_KEY
    c.check = "site_status"
    return c


def test_search_request_and_rows(search):
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response(payload=SEARCH_PAYLOAD))) as post:
        search.city = "London,England,United Kingdom"
        search.max_results = 500
        df = search.geekflare_search()

    args, kwargs = post.call_args
    assert args[0] == "https://api.geekflare.com/search"
    assert kwargs["headers"]["x-api-key"] == API_KEY
    assert kwargs["json"] == {
        "query": "best crm",
        "limit": 100,
        "source": "web",
        "serp": False,
        "city": "London,England,United Kingdom",
    }
    assert list(df["title"]) == ["Result one", "Result two"]
    assert list(df["link"]) == ["https://example.com/one", "https://example.com/two"]


def test_search_serp_maps_organic(search):
    search.serp = True
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response(payload=SERP_PAYLOAD))):
        rows = search.fetch_content()
    assert len(rows) == 1
    assert rows[0].data["link"] == "https://example.com/a"
    assert rows[0].data["snippet"] == "Desc A."


def test_search_api_error_returns_error_row(search):
    error = {"apiCode": 401, "message": "Invalid x-api-key"}
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response(401, error))):
        rows = search.fetch_content()
    assert "Invalid x-api-key" in rows[0].data["error"]


def test_search_requires_api_key(search):
    search.geekflare_api_key = ""
    with patch(POST_PATCH_TARGET) as post:
        rows = search.fetch_content()
    post.assert_not_called()
    assert "API key is required" in rows[0].data["error"]


def test_search_network_error_returns_error_row(search):
    with patch(POST_PATCH_TARGET, MagicMock(side_effect=httpx.ConnectError("boom"))):
        rows = search.fetch_content()
    assert "boom" in rows[0].data["error"]


def test_scrape_normalizes_url_and_returns_text(scrape):
    payload = {"apiStatus": "success", "data": {"markdown": "# Example"}}
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response(payload=payload))) as post:
        result = scrape.geekflare_scrape()
    args, kwargs = post.call_args
    assert args[0] == "https://api.geekflare.com/webscraping"
    assert kwargs["json"] == {"url": "https://example.com", "format": ["markdown"]}
    assert result.text == "# Example"


def test_scrape_template(scrape):
    scrape.template = "product"
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response())) as post:
        scrape.geekflare_scrape()
    assert post.call_args.kwargs["json"]["extractionMode"] == "template"
    assert post.call_args.kwargs["json"]["template"] == "product"


@pytest.mark.parametrize(("name", "path"), list(CHECKS.items()))
def test_website_check_routes(check, name, path):
    check.check = name
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response())) as post:
        result = check.geekflare_website_check()
    args, kwargs = post.call_args
    assert args[0] == f"https://api.geekflare.com/{path}"
    assert kwargs["json"] == {"url": "https://example.com"}
    assert result.data["check"] == name


def test_website_check_unknown_check(check):
    check.check = "nope"
    with patch(POST_PATCH_TARGET) as post:
        result = check.geekflare_website_check()
    post.assert_not_called()
    assert "Unknown check" in result.data["error"]


def test_redirect_status_is_an_error(search):
    with patch(POST_PATCH_TARGET, MagicMock(return_value=_response(302, {"message": "Moved"}))):
        rows = search.fetch_content()
    assert "302" in rows[0].data["error"]


def test_non_json_success_body_is_an_error(search):
    html = httpx.Response(
        200, request=httpx.Request("POST", "https://api.geekflare.com/search"), text="<html>gateway</html>"
    )
    with patch(POST_PATCH_TARGET, MagicMock(return_value=html)):
        rows = search.fetch_content()
    assert "malformed response" in rows[0].data["error"]

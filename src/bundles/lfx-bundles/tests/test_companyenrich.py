"""CompanyEnrich request mapping and errors, without live API calls."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx.extension.loader._orchestrator import _load_bundle_directory
from lfx.extension.loader._types import LoadResult
from lfx_bundles.companyenrich import (
    CompanyEnrichEnrichComponent,
    CompanyEnrichSearchComponent,
    CompanyEnrichSimilarComponent,
)
from lfx_bundles.companyenrich._client import API_URL, request, search_payload
from pydantic import SecretStr

API_KEY = "companyenrich-test-placeholder"  # pragma: allowlist secret
COMPONENTS = (CompanyEnrichEnrichComponent, CompanyEnrichSearchComponent, CompanyEnrichSimilarComponent)


def component(component_class, **kwargs):
    instance = component_class()
    instance.set(api_key=API_KEY, **kwargs)
    return instance


def response(status=200, **kwargs):
    return httpx.Response(status, request=httpx.Request("POST", API_URL), **kwargs)


@pytest.mark.parametrize("component_class", COMPONENTS)
def test_components_have_secret_credentials_and_no_shadowed_inputs(component_class):
    instance = component_class()
    assert not [item.name for item in instance.inputs if hasattr(Component, item.name)]
    key_input = next(item for item in instance.inputs if item.name == "api_key")
    assert key_input.password is True
    assert not getattr(key_input, "tool_mode", False)
    assert instance.to_frontend_node()["data"]["node"]["template"]["api_key"]["password"] is True


@pytest.mark.parametrize(
    ("component_class", "method_name", "inputs", "http_method", "path", "query", "body"),
    [
        (
            CompanyEnrichEnrichComponent,
            "enrich_company",
            {"domain": " stripe.com "},
            "GET",
            "/companies/enrich",
            {"domain": "stripe.com"},
            None,
        ),
        (
            CompanyEnrichSearchComponent,
            "search_companies",
            {"query": " AI for healthcare ", "search_filters": {"countries": ["US"]}, "page": 2, "page_size": 3},
            "POST",
            "/companies/search",
            None,
            {"semanticQuery": "AI for healthcare", "countries": ["US"], "page": 2, "pageSize": 3},
        ),
        (
            CompanyEnrichSimilarComponent,
            "find_similar_companies",
            {"domains": ["stripe.com", "squareup.com"], "search_filters": {"technologies": ["React"]}},
            "POST",
            "/companies/similar",
            None,
            {"domains": ["stripe.com", "squareup.com"], "technologies": ["React"], "page": 1, "pageSize": 10},
        ),
    ],
)
async def test_request_mapping_preserves_full_response(
    component_class, method_name, inputs, http_method, path, query, body
):
    instance = component(component_class, **inputs)
    result_body = {"items": [{"domain": "stripe.com"}], "totalItems": 42, "page": 2}
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(json=result_body)) as send:
        result = await getattr(instance, method_name)()
    assert result.data == result_body
    assert instance.status == result_body
    send.assert_awaited_once_with(
        http_method,
        f"{API_URL}{path}",
        headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"},
        params=query,
        json=body,
    )


async def test_filter_only_search_omits_semantic_query():
    instance = component(CompanyEnrichSearchComponent, search_filters={"countries": ["US"]})
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(json={})) as send:
        await instance.search_companies()
    assert send.call_args.kwargs["json"] == {"countries": ["US"], "page": 1, "pageSize": 10}


@pytest.mark.parametrize(
    ("component_class", "method_name", "inputs", "message"),
    [
        (CompanyEnrichEnrichComponent, "enrich_company", {"domain": "https://stripe.com/path"}, "bare company domain"),
        (CompanyEnrichSearchComponent, "search_companies", {}, "Search Query or at least one filter"),
        (CompanyEnrichSearchComponent, "search_companies", {"query": "AI", "page": 101, "page_size": 100}, "10,000"),
        (CompanyEnrichSearchComponent, "search_companies", {"query": "x" * 501}, "at most 500"),
        (CompanyEnrichSimilarComponent, "find_similar_companies", {"domains": []}, "one and ten"),
        (CompanyEnrichSimilarComponent, "find_similar_companies", {"domains": ["stripe.com"] * 11}, "one and ten"),
    ],
)
async def test_invalid_inputs_do_not_call_api(component_class, method_name, inputs, message):
    instance = component(component_class, **inputs)
    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock) as send,
        pytest.raises(ValueError, match=message),
    ):
        await getattr(instance, method_name)()
    send.assert_not_called()


@pytest.mark.parametrize(("page", "page_size"), [(0, 10), (1, 0), (1, 101), (True, 10)])
def test_pagination_is_bounded(page, page_size):
    with pytest.raises(ValueError, match="integer"):
        search_payload({}, page, page_size)


@pytest.mark.parametrize("field", ["page", "pageSize", "semanticQuery", "domain", "domains"])
def test_filters_cannot_override_dedicated_inputs(field):
    with pytest.raises(ValueError, match="dedicated"):
        search_payload({field: "ignored"}, 1, 10)


@pytest.mark.parametrize("status", [307, 401, 403, 404, 429, 500])
async def test_http_errors_do_not_include_response_body_or_credentials(status):
    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(status, text=API_KEY)),
        pytest.raises(ValueError, match=f"HTTP {status}") as error,
    ):
        await request(API_KEY, "GET", "/companies/enrich", timeout=30)
    assert API_KEY not in str(error.value)


async def test_secret_string_and_redirect_policy():
    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(json={})) as send,
        patch("httpx.AsyncClient", wraps=httpx.AsyncClient) as client,
    ):
        await request(SecretStr(API_KEY), "GET", "/companies/enrich", timeout=45)
    client.assert_called_once_with(timeout=45, follow_redirects=False)
    assert send.call_args.kwargs["headers"]["Authorization"] == f"Bearer {API_KEY}"


async def test_transport_error_is_sanitized_and_not_retried():
    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=httpx.ConnectError(API_KEY)) as send,
        pytest.raises(ValueError, match="Could not reach") as error,
    ):
        await request(API_KEY, "GET", "/companies/enrich", timeout=30)
    assert API_KEY not in str(error.value)
    assert send.await_count == 1


@pytest.mark.parametrize("body", ["not JSON", "[]"])
async def test_invalid_response_shape(body):
    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(text=body)),
        pytest.raises((ValueError, TypeError), match=r"invalid JSON|unexpected response"),
    ):
        await request(API_KEY, "GET", "/companies/enrich", timeout=30)


@pytest.mark.parametrize(("api_key", "timeout"), [("", 30), (API_KEY, 0), (API_KEY, 301)])
async def test_invalid_credentials_or_timeout_do_not_call_api(api_key, timeout):
    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock) as send,
        pytest.raises(ValueError, match=r"API key|Timeout"),
    ):
        await request(api_key, "GET", "/companies/enrich", timeout=timeout)
    send.assert_not_called()


def test_bundle_discovery_registers_three_components():
    bundle_root = Path(__file__).parents[1] / "src" / "lfx_bundles" / "companyenrich"
    result = LoadResult(slot="official", source_path=bundle_root, distribution=None)
    _load_bundle_directory(
        bundle_root=bundle_root,
        bundle_name="companyenrich",
        extension_id="lfx-bundles",
        extension_version="1.3.1",
        slot="official",
        distribution=None,
        result=result,
    )
    assert not result.errors
    assert {item.namespaced_id for item in result.components} == {
        f"ext:companyenrich:{component_class.__name__}@official" for component_class in COMPONENTS
    }

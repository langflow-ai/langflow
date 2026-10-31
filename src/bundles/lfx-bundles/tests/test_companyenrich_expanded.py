"""Exercise the actual components, operation selector and full JSON responses."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import lfx_bundles.companyenrich as bundle
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.companyenrich._catalog import OPERATIONS

CASES = json.loads(Path(__file__).with_name("companyenrich_operations.json").read_text())


def component(cls, **inputs):
    instance = cls()
    instance.set(api_key="test-key", **inputs)
    return instance


def response(value):
    return httpx.Response(200, json=value, request=httpx.Request("POST", "https://api.companyenrich.com"))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["operation"])
async def test_all_advanced_operations_dispatch_once_losslessly(case):
    instance = component(
        bundle.CompanyEnrichAdvancedComponent,
        operation=case["operation"],
        body=case["body"] or {},
        query_parameters=case["query"],
        path_parameters=case["path_parameters"],
        allow_beta=case["allow_beta"],
    )
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(case["result"])) as send:
        result = await instance.call_operation()
    assert result.data == (case["result"] if isinstance(case["result"], dict) else {"data": case["result"]})
    send.assert_awaited_once()
    assert send.call_args.args == (case["method"], "https://api.companyenrich.com" + case["path"])
    assert send.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"


CORE = [
    [
        "CompanyEnrichEnrichComponent",
        "enrich_company",
        {"domain": "example.com", "expand": ["workforce"], "wait_for_enrichment": "Return immediately"},
        "GET",
        "/companies/enrich",
    ],
    [
        "CompanyEnrichSearchComponent",
        "search_companies",
        {
            "search_filters": {"countries": ["US"], "query": "literal", "future": {"nested": [None]}},
            "query": "software",
            "expand": ["workforce"],
        },
        "POST",
        "/companies/search",
    ],
    [
        "CompanyEnrichSimilarComponent",
        "find_similar_companies",
        {
            "domains": ["example.com"],
            "search_filters": {"minScore": 0.7},
            "expand": ["workforce"],
            "wait_for_enrichment": "Return immediately",
        },
        "POST",
        "/companies/similar",
    ],
    [
        "CompanyEnrichPeopleSearchComponent",
        "search_people",
        {"search_filters": {"companyFilter": {"domains": ["example.com"]}}, "expand": ["education"]},
        "POST",
        "/people/search",
    ],
    [
        "CompanyEnrichPersonLookupComponent",
        "lookup_person",
        {"email": "person@example.com", "expand": ["education"]},
        "POST",
        "/people/lookup",
    ],
    ["CompanyEnrichWorkforceComponent", "get_workforce", {"domain": "example.com"}, "GET", "/companies/workforce"],
    [
        "CompanyEnrichPropertiesComponent",
        "match_company",
        {"properties": {"linkedinId": "123"}},
        "POST",
        "/companies/enrich",
    ],
    ["CompanyEnrichBatchComponent", "enrich_batch", {"domains": ["example.com"]}, "POST", "/companies/enrich/batch"],
    [
        "CompanyEnrichCompanyByIdComponent",
        "get_company",
        {"company_id": "123e4567-e89b-12d3-a456-426614174000"},
        "GET",
        "/companies",
    ],
    ["CompanyEnrichPersonByIdComponent", "get_person", {"person_id": "9007199254740993"}, "GET", "/people"],
    [
        "CompanyEnrichSearchCountComponent",
        "count_companies",
        {"search_filters": {"countries": ["US"]}},
        "POST",
        "/companies/search/count",
    ],
    [
        "CompanyEnrichSimilarCountComponent",
        "count_similar",
        {"domains": ["example.com"], "search_filters": {"minScore": 0.5}},
        "POST",
        "/companies/similar/count",
    ],
]


@pytest.mark.parametrize(("name", "method_name", "inputs", "method", "path"), CORE)
async def test_native_core_components_full_filters_and_optional_inputs(name, method_name, inputs, method, path):
    instance = component(getattr(bundle, name), **inputs)
    value = (
        0
        if path.endswith("/count")
        else [{"future": {"value": None}}]
        if path.endswith("/batch")
        else {"future": {"value": None}}
    )
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(value)) as send:
        result = await getattr(instance, method_name)()
    assert result.data == (value if isinstance(value, dict) else {"data": value})
    send.assert_awaited_once()
    assert send.call_args.args == (method, "https://api.companyenrich.com" + path)
    kwargs = send.call_args.kwargs
    for key, filter_value in inputs.get("search_filters", {}).items():
        assert kwargs["json"][key] == filter_value
    if "expand" in inputs:
        assert kwargs["params"]["expand"] == inputs["expand"]
    if "wait_for_enrichment" in inputs:
        assert kwargs["params"]["waitForEnrichment"] == "false"


@pytest.mark.parametrize("name", bundle.__all__)
def test_frontend_schema_all_registered_components(name):
    instance = getattr(bundle, name)()
    assert not [item.name for item in instance.inputs if hasattr(Component, item.name)]
    template = instance.to_frontend_node()["data"]["node"]["template"]
    assert template["api_key"]["password"] is True
    if name == "CompanyEnrichAdvancedComponent":
        assert set(template["operation"]["options"]) == set(OPERATIONS)
    for key in ("body", "query_parameters", "path_parameters", "search_filters", "properties"):
        if key in template:
            assert template[key]["list"] is False


@pytest.mark.parametrize(
    ("operation", "kwargs"),
    [
        ("get_me", {}),
        ("post_companies_search_async", {"body": {"count": 1, "similar": {}}}),
        ("post_companies_similar_count", {"body": {"domain": "example.com"}}),
        ("post_companies_similar_count", {"body": {"domains": ["example.com"], "domain": "example.com"}}),
        ("get_companies_enrich", {"query": {"domain": "", "Authorization": "x"}}),
        ("get_companies_workforce", {"query": {}}),
        ("get_companies_workforce", {"query": {"domain": "example.com", "id": "123e4567-e89b-12d3-a456-426614174000"}}),
        ("post_companies_enrich", {"body": {}}),
        ("post_companies_enrich_batch", {"body": {"domains": ["x"] * 51}}),
        ("post_companies_search", {"body": {"page": True}}),
        ("post_companies_search", {"body": {"page": 1001}}),
        ("post_companies_search", {"body": {"semanticQuery": "x" * 501}}),
        ("post_companies_similar", {"body": {"domains": []}}),
        ("post_people_lookup", {"body": {"email": " "}}),
        ("get_people", {"query": {"id": "9223372036854775808"}}),
        ("get_people_email", {"query": {"id": "1"}}),
        ("post_people_email_bulk", {"allow_beta": True, "body": {"items": []}}),
        ("post_companies_search_async", {"body": {}}),
        ("post_people_search_async", {"body": {"count": 50001}}),
        ("get_jobs_jobid", {"path_parameters": {"jobId": "../../me"}}),
    ],
)
async def test_invalid_input_never_sends(operation, kwargs):
    kwargs = {"query_parameters" if k == "query" else k: v for k, v in kwargs.items()}
    instance = component(bundle.CompanyEnrichAdvancedComponent, operation=operation, **kwargs)
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as send, pytest.raises((ValueError, TypeError)):
        await instance.call_operation()
    send.assert_not_called()


async def test_paid_failure_is_once_sanitized_and_no_result_url_download():
    instance = component(
        bundle.CompanyEnrichAdvancedComponent, operation="post_companies_search_async", body={"count": 1}
    )
    error = httpx.Response(
        429, text="test-key private upstream response", request=httpx.Request("POST", "https://api.companyenrich.com")
    )
    with (
        patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=error) as send,
        pytest.raises(ValueError, match="HTTP 429") as exc,
    ):
        await instance.call_operation()
    assert "test-key" not in str(exc.value)
    assert "private upstream response" not in str(exc.value)
    send.assert_awaited_once()


async def test_dedicated_values_take_precedence_and_default_page_size_is_explicit():
    instance = component(
        bundle.CompanyEnrichSearchComponent,
        query="semantic",
        literal_query="literal",
        page=2,
        page_size=3,
        search_filters={
            "query": "filterquery",
            "semanticQuery": "filtersemantic",
            "page": 99,
            "pageSize": 99,
            "countries": ["US"],
        },
    )
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response({})) as send:
        await instance.search_companies()
    assert send.call_args.kwargs["json"] == {
        "query": "literal",
        "semanticQuery": "semantic",
        "page": 2,
        "pageSize": 3,
        "countries": ["US"],
    }
    instance = component(bundle.CompanyEnrichAdvancedComponent, operation="post_people_search", body={})
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response({})) as send:
        await instance.call_operation()
    assert send.call_args.kwargs["json"] == {"page": 1, "pageSize": 10}

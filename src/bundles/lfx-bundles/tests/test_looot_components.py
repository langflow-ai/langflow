"""Contract tests for the looot REST API components. All HTTP is mocked."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

pytest.importorskip("lfx_bundles")

from lfx_bundles.looot import (
    LoootGetBalanceComponent,
    LoootGetRunComponent,
    LoootInspectEndpointComponent,
    LoootRunEndpointComponent,
    LoootSearchCatalogComponent,
)
from lfx_bundles.looot import (
    get_balance as get_balance_module,
)
from lfx_bundles.looot import (
    get_run as get_run_module,
)
from lfx_bundles.looot import (
    inspect_endpoint as inspect_module,
)
from lfx_bundles.looot import (
    run_endpoint as run_module,
)
from lfx_bundles.looot import (
    search_catalog as search_module,
)

BASE = "https://api.looot.ai"
API_KEY = "test-looot-key"  # pragma: allowlist secret


@respx.mock
async def test_search_catalog_sends_query_and_bearer_key() -> None:
    payload = {"items": [{"endpointId": "serper-search"}]}
    route = respx.get(f"{BASE}/v1/catalog/search").mock(return_value=httpx.Response(200, json=payload))
    component = LoootSearchCatalogComponent(
        api_key=f" {API_KEY} ", query=" find work email ", limit=5, prefer="cheapest"
    )

    result = await component.build_output()

    request = route.calls[0].request
    assert result.data["value"] == payload
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert dict(request.url.params) == {"q": "find work email", "limit": "5", "prefer": "cheapest"}


@respx.mock
async def test_inspect_endpoint_encodes_the_endpoint_id() -> None:
    payload = {"endpointId": "a/b", "price": {"micros": 1000}}
    route = respx.get(f"{BASE}/v1/operations/a%2Fb").mock(return_value=httpx.Response(200, json=payload))
    component = LoootInspectEndpointComponent(api_key=API_KEY, endpoint_id=" a/b ")

    result = await component.build_output()

    assert route.called
    assert result.data["value"] == payload


@respx.mock
async def test_run_endpoint_posts_body_with_idempotency_key_and_wait() -> None:
    payload = {"runId": "run_1", "status": "completed", "actualCost": 0.001}
    route = respx.post(f"{BASE}/v1/runs").mock(return_value=httpx.Response(200, json=payload))
    component = LoootRunEndpointComponent(
        api_key=API_KEY,
        endpoint_id="serper-search",
        input_json='{"q": "coffee"}',
        idempotency_key=" key-1 ",
        wait=20,
    )

    result = await component.build_output()

    request = route.calls[0].request
    assert result.data["value"] == payload
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert dict(request.url.params) == {"wait": "20"}
    assert json.loads(request.content) == {
        "endpointId": "serper-search",
        "input": {"q": "coffee"},
        "idempotencyKey": "key-1",
    }


@respx.mock
async def test_run_endpoint_generates_a_unique_key_when_none_given_and_clamps_wait() -> None:
    route = respx.post(f"{BASE}/v1/runs").mock(return_value=httpx.Response(200, json={"status": "queued"}))
    keys = []
    for _ in range(2):
        component = LoootRunEndpointComponent(
            api_key=API_KEY, endpoint_id="serper-search", input_json="{}", idempotency_key="", wait=500
        )
        await component.build_output()
        keys.append(json.loads(route.calls[-1].request.content)["idempotencyKey"])

    assert keys[0] != keys[1]
    assert all(key.startswith("langflow-") for key in keys)
    assert dict(route.calls[0].request.url.params) == {"wait": "60"}


@respx.mock
@pytest.mark.parametrize("bad_input", ["not json", "[1, 2]"])
async def test_run_endpoint_rejects_invalid_input_without_calling_the_api(bad_input: str) -> None:
    route = respx.post(f"{BASE}/v1/runs").mock(return_value=httpx.Response(200, json={}))
    component = LoootRunEndpointComponent(api_key=API_KEY, endpoint_id="serper-search", input_json=bad_input)

    with patch.object(run_module.logger, "aerror", new_callable=AsyncMock):
        result = await component.build_output()

    assert "Invalid input" in result.data["value"]["error"]
    assert not route.called


@respx.mock
async def test_pending_statuses_are_returned_as_data_not_errors() -> None:
    payload = {"runId": "run_2", "status": "pending_provider"}
    respx.get(f"{BASE}/v1/runs/run_2").mock(return_value=httpx.Response(200, json=payload))
    component = LoootGetRunComponent(api_key=API_KEY, run_id=" run_2 ")

    result = await component.build_output()

    assert result.data["value"] == payload
    assert "error" not in result.data["value"]


@respx.mock
async def test_get_balance_reads_the_balance_route() -> None:
    payload = {"balanceUsd": 12.5}
    route = respx.get(f"{BASE}/v1/balance").mock(return_value=httpx.Response(200, json=payload))
    component = LoootGetBalanceComponent(api_key=API_KEY)

    result = await component.build_output()

    assert route.calls[0].request.headers["authorization"] == f"Bearer {API_KEY}"
    assert result.data["value"] == payload


@pytest.mark.parametrize(
    ("factory", "module", "method", "url"),
    [
        pytest.param(
            lambda: LoootSearchCatalogComponent(api_key=API_KEY, query="x"),
            search_module,
            "get",
            f"{BASE}/v1/catalog/search",
            id="search",
        ),
        pytest.param(
            lambda: LoootInspectEndpointComponent(api_key=API_KEY, endpoint_id="x"),
            inspect_module,
            "get",
            f"{BASE}/v1/operations/x",
            id="inspect",
        ),
        pytest.param(
            lambda: LoootRunEndpointComponent(api_key=API_KEY, endpoint_id="x", input_json="{}"),
            run_module,
            "post",
            f"{BASE}/v1/runs",
            id="run",
        ),
        pytest.param(
            lambda: LoootGetRunComponent(api_key=API_KEY, run_id="x"),
            get_run_module,
            "get",
            f"{BASE}/v1/runs/x",
            id="get-run",
        ),
        pytest.param(
            lambda: LoootGetBalanceComponent(api_key=API_KEY),
            get_balance_module,
            "get",
            f"{BASE}/v1/balance",
            id="balance",
        ),
    ],
)
@pytest.mark.parametrize("failure", ["http-status", "request", "invalid-json"])
async def test_failures_are_returned_as_data(factory, module, method: str, url: str, failure: str) -> None:
    component = factory()

    with respx.mock:
        route = getattr(respx, method)(url)
        if failure == "http-status":
            route.mock(return_value=httpx.Response(402, json={"error": {"code": "insufficient_balance"}}))
            expected = "HTTP error occurred"
        elif failure == "request":
            route.mock(side_effect=httpx.ConnectError("connection failed"))
            expected = "Request failed"
        else:
            route.mock(return_value=httpx.Response(200, text="not-json"))
            expected = "Response parsing failed"

        with patch.object(module.logger, "aexception", new_callable=AsyncMock):
            result = await component.build_output()

    assert expected in result.data["value"]["error"]
    assert component.status == result.data["value"]

"""Unit tests for the Datacircle components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.get``, so the tests exercise the real
paths, query parameters, response shaping and error handling of the client.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.datacircle.datacircle_best import DatacircleBestComponent
from lfx_bundles.datacircle.datacircle_common import API_BASE_URL, PLAN_FIELDS
from lfx_bundles.datacircle.datacircle_list_apis import DatacircleListAPIsComponent
from lfx_bundles.datacircle.datacircle_provider import DatacircleProviderComponent, provider_slug
from lfx_bundles.datacircle.datacircle_search_plans import DatacircleSearchPlansComponent

COMPONENTS = [
    DatacircleListAPIsComponent,
    DatacircleBestComponent,
    DatacircleSearchPlansComponent,
    DatacircleProviderComponent,
]

APIS = [
    {
        "api": "Employee email",
        "slug": "email-finder",
        "plans": 5420,
        "providers": 300,
        "sheetPage": "https://datacircle.dev/email-finder-api-pricing",
        "bestPage": "https://datacircle.dev/best-email-finder-api",
        "best": {"provider": "GetProspect", "plan": "Growth 50k", "score": 79.7, "perThousand": 7.98},
    },
    {
        "api": "Employee profile",
        "slug": "linkedin-profile",
        "plans": 4940,
        "providers": 455,
        "sheetPage": "https://datacircle.dev/linkedin-profile-api-pricing",
        "bestPage": "https://datacircle.dev/best-linkedin-profile-api",
        "best": {"provider": "Bridgly", "plan": "Scale", "score": 78.3, "perThousand": 1},
    },
]

PLAN = {
    "rank": 1,
    "provider": "GetProspect",
    "plan": "Growth 50k",
    "api": "Employee email",
    "call": "Email Finder",
    "score": 79.7,
    "perThousand": 7.98,
    "pay": 399,
    "currency": "USD",
    "latencyMs": 820,
    "page": "https://datacircle.dev/find-email-apis/getprospect/growth-50k",
}

PROVIDER = {
    "provider": "Hunter",
    "slug": "hunter",
    "website": "https://hunter.io",
    "apis": [
        {
            "api": "Employee email",
            "slug": "email-finder",
            "rank": 32,
            "bestPage": "https://datacircle.dev/best-email-finder-api",
            "plans": [
                {"plan": "Free", "score": None, "perThousand": 0},
                {"plan": "Scale", "score": 64.6, "perThousand": 11.96},
                {"plan": "Growth", "score": 60.1, "perThousand": 16.33},
            ],
        },
        {"api": "Reverse email lookup", "slug": "reverse-email-lookup", "rank": None, "plans": []},
    ],
}


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _component(component_class: type[Component], **values) -> Any:
    component = component_class()
    component.set(**values)
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", COMPONENTS)
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", COMPONENTS)
def test_metadata(component_class: type[Component]) -> None:
    component = component_class()
    assert component.icon == "Datacircle"
    assert component.documentation == "https://datacircle.dev/api"
    assert not any(inp.name == "api_key" for inp in component_class.inputs)
    assert any(getattr(inp, "tool_mode", False) for inp in component_class.inputs)


@pytest.mark.unit
class TestDatacircleListAPIs:
    def test_lists_every_api_with_its_best_plan(self) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body=APIS)) as get:
            data = _component(DatacircleListAPIsComponent).list_apis()

        assert get.call_args.args[0] == f"{API_BASE_URL}/apis"
        assert [item.data["slug"] for item in data] == ["email-finder", "linkedin-profile"]
        assert data[0].data["best_provider"] == "GetProspect"
        assert data[0].data["best_per_thousand"] == 7.98
        assert data[0].text == "Employee email (email-finder)"

    def test_search_keeps_the_apis_with_every_word(self) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body=APIS)):
            data = _component(DatacircleListAPIsComponent, search="EMAIL employee").list_apis()

        assert [item.data["slug"] for item in data] == ["email-finder"]

    def test_unexpected_shape_is_an_error(self) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body={"apis": APIS})):
            data = _component(DatacircleListAPIsComponent).list_apis()

        assert "unexpected response shape" in data[0].data["error"]

    def test_dataframe_has_one_row_per_api(self) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body=APIS)):
            frame = _component(DatacircleListAPIsComponent).list_apis_dataframe()

        assert list(frame["slug"]) == ["email-finder", "linkedin-profile"]


@pytest.mark.unit
class TestDatacircleBest:
    def test_calls_the_best_path_with_its_limit(self) -> None:
        body = {"api": "Employee email", "slug": "email-finder", "total": 5420, "plans": [PLAN]}
        with patch("httpx.Client.get", return_value=_response(json_body=body)) as get:
            data = _component(DatacircleBestComponent, api=" email-finder ", limit=3).best()

        assert get.call_args.args[0] == f"{API_BASE_URL}/apis/email-finder/best"
        assert get.call_args.kwargs["params"] == {"limit": 3}
        assert data[0].data["provider"] == "GetProspect"
        assert set(data[0].data) - {"text"} <= set(PLAN_FIELDS)
        assert "latencyMs" not in data[0].data

    def test_all_fields_keeps_every_field(self) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body={"plans": [PLAN]})):
            data = _component(DatacircleBestComponent, api="email-finder", all_fields=True).best()

        assert data[0].data["latencyMs"] == 820

    @pytest.mark.parametrize(("limit", "sent"), [(0, 1), (500, 50), (None, 5)])
    def test_limit_is_clamped(self, limit: int | None, sent: int) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body={"plans": []})) as get:
            _component(DatacircleBestComponent, api="email-finder", limit=limit).best()

        assert get.call_args.kwargs["params"] == {"limit": sent}

    def test_slug_cannot_change_the_path(self) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body={"plans": []})) as get:
            _component(DatacircleBestComponent, api="../providers/hunter?x=1").best()

        assert get.call_args.args[0] == f"{API_BASE_URL}/apis/..%2Fproviders%2Fhunter%3Fx%3D1/best"

    def test_empty_api_makes_no_request(self) -> None:
        with patch("httpx.Client.get") as get:
            data = _component(DatacircleBestComponent, api="  ").best()

        get.assert_not_called()
        assert data[0].data["error"] == "Enter an API slug, such as email-finder."

    def test_unknown_slug_lists_the_known_ones(self) -> None:
        body = {"error": "no API has the slug emails", "slugs": ["email-finder", "linkedin-profile"]}
        with patch("httpx.Client.get", return_value=_response(404, json_body=body)):
            data = _component(DatacircleBestComponent, api="emails").best()

        error = data[0].data["error"]
        assert error.startswith("Datacircle found nothing for this (404): no API has the slug emails")
        assert "Known slugs: email-finder, linkedin-profile" in error


@pytest.mark.unit
class TestDatacircleSearchPlans:
    def test_sends_the_filters_it_is_given(self) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body={"total": 1, "plans": [PLAN]})) as get:
            data = _component(
                DatacircleSearchPlansComponent, query=" hunter ", api="email-finder", sort="price", limit=3, offset=6
            ).search_plans()

        assert get.call_args.args[0] == f"{API_BASE_URL}/plans"
        assert get.call_args.kwargs["params"] == {
            "sort": "price",
            "limit": 3,
            "offset": 6,
            "query": "hunter",
            "api": "email-finder",
        }
        assert data[0].data["call"] == "Email Finder"

    def test_empty_filters_are_left_out_and_an_unknown_sort_falls_back(self) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body={"plans": []})) as get:
            _component(DatacircleSearchPlansComponent, sort="cheapest").search_plans()

        assert get.call_args.kwargs["params"] == {"sort": "score", "limit": 10, "offset": 0}

    def test_rate_limit_is_an_error(self) -> None:
        with patch("httpx.Client.get", return_value=_response(429, json_body={"error": "slow down"})):
            data = _component(DatacircleSearchPlansComponent, query="hunter").search_plans()

        assert "rate limit exceeded (429)" in data[0].data["error"]

    def test_non_json_response_is_an_error(self) -> None:
        with patch("httpx.Client.get", return_value=_response(text="<html>bad gateway</html>")):
            data = _component(DatacircleSearchPlansComponent, query="hunter").search_plans()

        assert "not JSON" in data[0].data["error"]

    def test_timeout_is_an_error(self) -> None:
        with patch("httpx.Client.get", side_effect=httpx.ReadTimeout("slow")):
            data = _component(DatacircleSearchPlansComponent, query="hunter", timeout=2.5).search_plans()

        assert data[0].data["error"] == "Datacircle request timed out after 2.5 seconds."


@pytest.mark.unit
class TestDatacircleProvider:
    @pytest.mark.parametrize(
        ("name", "slug"), [("Hunter", "hunter"), ("Bright Data", "bright-data"), (" People Data Labs! ", "people-data-labs")]
    )
    def test_provider_slug(self, name: str, slug: str) -> None:
        assert provider_slug(name) == slug

    def test_one_row_per_api_with_its_best_scored_plan(self) -> None:
        with patch("httpx.Client.get", return_value=_response(json_body=PROVIDER)) as get:
            data = _component(DatacircleProviderComponent, provider="Hunter").provider_apis()

        assert get.call_args.args[0] == f"{API_BASE_URL}/providers/hunter"
        assert [item.data["slug"] for item in data] == ["email-finder", "reverse-email-lookup"]
        assert data[0].data["rank"] == 32
        assert data[0].data["plans"] == 3
        assert data[0].data["best_plan"] == "Scale"
        assert data[1].data["best_plan"] is None
        assert data[0].text == "Hunter on Employee email: rank 32"

    def test_unknown_provider_is_an_error(self) -> None:
        with patch("httpx.Client.get", return_value=_response(404, json_body={"error": "no provider has the slug x"})):
            data = _component(DatacircleProviderComponent, provider="x").provider_apis()

        assert data[0].data["error"] == "Datacircle found nothing for this (404): no provider has the slug x"

    def test_unreachable_api_is_an_error(self) -> None:
        with patch("httpx.Client.get", side_effect=httpx.ConnectError("connection refused")):
            data = _component(DatacircleProviderComponent, provider="hunter").provider_apis()

        assert data[0].data["error"].startswith("Could not reach the Datacircle API: ConnectError")

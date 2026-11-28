"""Unit tests for the Ktemia components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the
real endpoints, headers, payloads, result shaping, and error handling.
The response bodies are trimmed copies of real API responses.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.ktemia.ktemia_booking_options import KtemiaBookingOptionsComponent
from lfx_bundles.ktemia.ktemia_cars import KtemiaCarSearchComponent
from lfx_bundles.ktemia.ktemia_common import API_BASE_URL
from lfx_bundles.ktemia.ktemia_flights import KtemiaFlightSearchComponent
from lfx_bundles.ktemia.ktemia_hotels import KtemiaHotelSearchComponent
from lfx_bundles.ktemia.ktemia_lookup import KtemiaLookupComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-ktemia-api-key-placeholder"  # pragma: allowlist secret

ALL_COMPONENTS = [
    KtemiaLookupComponent,
    KtemiaFlightSearchComponent,
    KtemiaHotelSearchComponent,
    KtemiaCarSearchComponent,
    KtemiaBookingOptionsComponent,
]

FLIGHT_PAGE = {
    "flights": [
        {
            "id": "f1",
            "legs": [
                {
                    "departure": "2026-12-19T09:00:00",
                    "arrival": "2026-12-19T12:20:00",
                    "duration": 380,
                    "stops": 0,
                    "segments": [{"airline": "B6", "flightNumber": "623", "origin": "JFK", "destination": "LAX"}],
                }
            ],
            "bookingOptions": [
                {
                    "providerCode": "EXPEDIAAIR",
                    "price": 430,
                    "formattedPrice": "$430",
                    "totalPrice": 430,
                    "formattedTotalPrice": "$430",
                },
                {
                    "providerCode": "B6",
                    "price": 412,
                    "formattedPrice": "$412",
                    "totalPrice": 412,
                    "formattedTotalPrice": "$412",
                },
            ],
            "totalProviders": 12,
        }
    ],
    "providers": {"B6": {"name": "JetBlue"}, "EXPEDIAAIR": {"name": "Expedia"}},
    "hasMore": True,
}

HOTEL_PAGE = {
    "hotels": [
        {
            "id": "h1",
            "name": "Le Damantin Hotel & Spa",
            "stars": 5.0,
            "rating": {"score": 8.8, "reviewCount": 1289},
            "location": {"city": "Paris", "neighborhood": "8th arrondissement"},
            "bestOption": {
                "provider": "Agoda.com",
                "price": {"amount": 680, "currency": "USD", "formatted": "$680"},
                "totalPrice": {"amount": 743, "currency": "USD", "formatted": "$743"},
            },
            "optionCount": 6,
        }
    ]
}

CAR_PAGE = {
    "cars": [
        {
            "id": "c1",
            "car": {"name": "Volkswagen Tiguan", "class": "Standard SUV", "transmission": "automatic", "passengers": 5},
            "agency": {"code": "europcar", "name": "Europcar"},
            "pickup": {"address": "Kantonsstrasse 67", "city": "Visp"},
            "bestOption": {
                "provider": "IAUTOEUROPE",
                "price": {"formatted": "$712"},
                "perDay": {"formatted": "$238"},
                "freeCancellation": True,
            },
            "bookingOptions": [{"provider": "IAUTOEUROPE", "providerName": "Auto Europe"}],
        }
    ]
}


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None) -> httpx.Response:
    request = httpx.Request("GET", API_BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json_body, request=request)


def _make(component_class: type[Component], **values) -> Any:
    component = component_class()
    component.set(**{"api_key": API_KEY, **values})
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_components_use_the_ktemia_icon(component_class: type[Component]) -> None:
    assert component_class.icon == "Ktemia"


@pytest.mark.unit
def test_flight_search_starts_a_search_then_reads_the_first_page() -> None:
    calls: list[tuple[str, str, dict]] = []

    def fake_request(self, method, url, **kwargs):  # noqa: ARG001
        calls.append((method, url, kwargs))
        if url.endswith("/flights/search"):
            return _response(json_body={"searchToken": "tok-1", "expiresIn": 3600})
        return _response(json_body=FLIGHT_PAGE)

    component = _make(
        KtemiaFlightSearchComponent,
        origin="jfk",
        destination="lax",
        departure_date="2026-12-19",
        adults=1,
        airlines="b6, dl",
    )
    with patch.object(httpx.Client, "request", fake_request):
        rows = component.search()

    (search_method, search_url, search_kwargs), (results_method, results_url, results_kwargs) = calls
    assert (search_method, search_url) == ("POST", f"{API_BASE_URL}/flights/search")
    assert search_kwargs["headers"]["X-API-Key"] == API_KEY
    assert search_kwargs["json"]["origin"] == "JFK"
    assert search_kwargs["json"]["airlines"] == ["B6", "DL"]
    assert "returnDate" not in search_kwargs["json"]  # unset fields are dropped
    assert (results_method, results_url) == ("GET", f"{API_BASE_URL}/flights/results")
    assert results_kwargs["params"] == {"token": "tok-1"}

    row = rows[0].data
    assert row["price"] == "$412"  # the cheapest option, not the first
    assert row["seller"] == "JetBlue"  # codes become display names
    assert row["airlines"] == "JetBlue"
    assert row["token"] == "tok-1"  # noqa: S105 - placeholder search token
    assert row["result_id"] == "f1"
    assert row["sellers"] == 12


@pytest.mark.unit
def test_flight_search_asks_for_missing_fields_without_calling_the_api() -> None:
    component = _make(KtemiaFlightSearchComponent, origin="JFK", destination="", departure_date="")
    with patch.object(httpx.Client, "request") as request:
        rows = component.search()
    request.assert_not_called()
    assert "error" in rows[0].data


@pytest.mark.unit
def test_hotel_search_shapes_one_row_per_hotel() -> None:
    def fake_request(self, method, url, **kwargs):  # noqa: ARG001
        if url.endswith("/hotels/search"):
            assert kwargs["json"]["providers"] == ["Booking.com", "Expedia"]
            return _response(json_body={"searchToken": "tok-h"})
        return _response(json_body=HOTEL_PAGE)

    component = _make(
        KtemiaHotelSearchComponent,
        location="37687",
        checkin="2026-12-19",
        checkout="2026-12-21",
        adults=2,
        providers="Booking.com, Expedia",
    )
    with patch.object(httpx.Client, "request", fake_request):
        row = component.search()[0].data
    assert row["name"] == "Le Damantin Hotel & Spa"
    assert row["price"] == "$680"
    assert row["total_with_taxes"] == "$743"
    assert row["seller"] == "Agoda.com"
    assert row["token"] == "tok-h"  # noqa: S105 - placeholder search token


@pytest.mark.unit
def test_car_search_uses_the_seller_display_name() -> None:
    def fake_request(self, method, url, **kwargs):  # noqa: ARG001
        if url.endswith("/cars/search"):
            assert kwargs["json"]["pickupLocation"] == "300251"
            assert "dropoffLocation" not in kwargs["json"]
            return _response(json_body={"searchToken": "tok-c"})
        return _response(json_body=CAR_PAGE)

    component = _make(
        KtemiaCarSearchComponent, pickup_location="300251", pickup_date="2026-12-19", dropoff_date="2026-12-22"
    )
    with patch.object(httpx.Client, "request", fake_request):
        row = component.search()[0].data
    assert row["car"] == "Volkswagen Tiguan"
    assert row["agency"] == "Europcar"
    assert row["seller"] == "Auto Europe"
    assert row["per_day"] == "$238"


@pytest.mark.unit
def test_lookup_returns_every_match_for_the_agent_to_choose() -> None:
    body = {
        "locations": [
            {"locationId": "300251", "name": "Lax, Valais, Switzerland"},
            {"locationId": "12345", "name": "Los Angeles International Airport"},
        ]
    }

    def fake_request(self, method, url, **kwargs):  # noqa: ARG001
        assert url == f"{API_BASE_URL}/cars/locations"
        assert kwargs["params"] == {"query": "LAX"}
        return _response(json_body=body)

    component = _make(KtemiaLookupComponent, kind="Car rental location", query="LAX")
    with patch.object(httpx.Client, "request", fake_request):
        rows = component.lookup()
    assert [row.data["locationId"] for row in rows] == ["300251", "12345"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("vertical", "option", "seller"),
    [
        (
            "flights",
            {
                "providerCode": "B6",
                "formattedPrice": "$412",
                "providerUrl": "https://api.ktemia.com/flights/book?ref=x",
            },
            "JetBlue",
        ),
        (
            "hotels",
            {
                "provider": "Expedia",
                "price": {"formatted": "$693"},
                "providerUrl": "https://api.ktemia.com/hotels/book?ref=y",
            },
            "Expedia",
        ),
        (
            "cars",
            {
                "provider": {"code": "IHERTZ", "name": "Hertz"},
                "price": {"formatted": "$127"},
                "providerUrl": "https://api.ktemia.com/cars/book?ref=z",
            },
            "Hertz",
        ),
    ],
)
def test_booking_options_list_every_seller_with_its_link(vertical: str, option: dict, seller: str) -> None:
    def fake_request(self, method, url, **kwargs):  # noqa: ARG001
        assert url == f"{API_BASE_URL}/{vertical}/details"
        assert kwargs["params"] == {"token": "tok", "resultId": "r1"}
        return _response(
            json_body={"resultId": "r1", "bookingOptions": [option], "providers": {"B6": {"name": "JetBlue"}}}
        )

    component = _make(KtemiaBookingOptionsComponent, vertical=vertical, token="tok", result_id="r1")  # noqa: S106 - placeholder search token
    with patch.object(httpx.Client, "request", fake_request):
        row = component.booking_options()[0].data
    assert row["seller"] == seller
    assert row["booking_url"] == option["providerUrl"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "label"),
    [(401, "rejected the API key"), (429, "rate limit or monthly quota"), (500, "Ktemia API error (500)")],
)
def test_api_errors_are_returned_without_the_key(status: int, label: str) -> None:
    body = {"success": False, "error": {"code": "X", "message": f"bad key {API_KEY}"}}

    def fake_request(self, method, url, **kwargs):  # noqa: ARG001
        return _response(status, json_body=body)

    component = _make(KtemiaLookupComponent, kind="Airport", query="London")
    with patch.object(httpx.Client, "request", fake_request):
        message = component.lookup()[0].data["error"]
    assert label in message
    assert API_KEY not in message


@pytest.mark.unit
def test_missing_key_is_reported_before_any_request() -> None:
    component = KtemiaLookupComponent()
    component.set(api_key="", kind="Airport", query="London")
    with patch.object(httpx.Client, "request") as request:
        message = component.lookup()[0].data["error"]
    request.assert_not_called()
    assert "API key" in message


@pytest.mark.unit
def test_timeouts_become_a_readable_error() -> None:
    def fake_request(self, method, url, **kwargs):  # noqa: ARG001
        msg = "slow"
        raise httpx.ReadTimeout(msg)

    component = _make(KtemiaLookupComponent, kind="Airport", query="London", timeout=5)
    with patch.object(httpx.Client, "request", fake_request):
        message = component.lookup()[0].data["error"]
    assert "timed out after 5 seconds" in message

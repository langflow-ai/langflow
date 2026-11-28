"""Shared HTTP plumbing and result shaping for the Ktemia components.

Ktemia is a travel search API for flights, hotels, and rental cars. One search
returns results from airlines, booking sites, and rental companies, and each
result lists every seller's price with a booking link. Ktemia compares prices;
the traveller books on the seller's site.

Every search works the same way: ``POST /{vertical}/search`` returns a
``searchToken``, ``GET /{vertical}/results`` reads a page of results with it,
and ``GET /{vertical}/details`` expands one result into every seller. All calls
go to the fixed host ``https://api.ktemia.com`` with the key in ``X-API-Key``.
"""

from __future__ import annotations

from typing import Any

import httpx

API_BASE_URL = "https://api.ktemia.com"
DOCUMENTATION_URL = "https://www.ktemia.com/docs/api"
DEFAULT_TIMEOUT_SECONDS = 60.0

API_KEY_INFO = (
    "Your Ktemia API key. Create one at https://app.ktemia.com (the Free plan includes 100 requests a month)."
)
COUNTRY_INFO = (
    "Two-letter market country, such as US, GB, or NO. Prices come back in that country's currency. "
    "Leave empty for the US market."
)
EXPIRY_NOTE = "Search tokens expire after about an hour."

VERTICALS = ("flights", "hotels", "cars")

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "Ktemia rejected the API key (401)",
    403: "Ktemia refused the request (403)",
    429: "Ktemia rate limit or monthly quota reached (429)",
}


class KtemiaAPIError(Exception):
    """A Ktemia request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def text_value(value: Any) -> str:
    """Return a stripped string for a text input, or an empty string when unset."""
    return str(value or "").strip()


def split_list(value: Any) -> list[str]:
    """Split a comma- or newline-separated input into a list of non-empty strings."""
    if isinstance(value, (list, tuple)):
        items = [str(item) for item in value]
    else:
        items = str(value or "").replace("\n", ",").split(",")
    return [item.strip() for item in items if item.strip()]


def compact(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop unset fields so the API applies its own defaults."""
    return {key: value for key, value in payload.items() if value not in (None, "", [])}


def _redact(text: str, api_key: str) -> str:
    """Replace the API key in text with ***."""
    return text.replace(api_key, "***") if api_key else text


def _error_detail(body: Any) -> str:
    """Pull the human-readable message out of the API's error shape."""
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "")
    return str(body.get("detail") or body.get("message") or error or "")


def _error_message(response: httpx.Response, api_key: str) -> str:
    """Build a short, key-free error message from a failed API response."""
    try:
        detail = _error_detail(response.json())
    except ValueError:
        detail = response.text.strip()
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    label = _STATUS_LABELS.get(response.status_code, f"Ktemia API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def ktemia_request(
    method: str,
    path: str,
    *,
    api_key: Any,
    timeout: float,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the Ktemia API and return the JSON body.

    Raises:
        KtemiaAPIError: On a missing key, a transport error, a non-2xx status, or a body that is not a JSON object.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter a Ktemia API key. Create one at https://app.ktemia.com."
        raise KtemiaAPIError(msg)
    headers = {"X-API-Key": key, "Accept": "application/json"}
    try:
        # follow_redirects stays off so the key is never replayed to another origin.
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.request(method, f"{API_BASE_URL}{path}", params=params, json=json, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"Ktemia request timed out after {timeout:g} seconds."
        raise KtemiaAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Ktemia API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise KtemiaAPIError(msg) from exc
    if not response.is_success:
        raise KtemiaAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "Ktemia API returned a response that is not JSON."
        raise KtemiaAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "Ktemia API returned an unexpected response shape."
        raise KtemiaAPIError(msg)
    return body


def search_first_page(
    vertical: str,
    payload: dict[str, Any],
    *,
    api_key: Any,
    timeout: float,
) -> dict[str, Any]:
    """Start a search and read its first page. Costs two requests.

    The returned page carries ``token``: the token to pass to the details call for its results.
    """
    started = ktemia_request("POST", f"/{vertical}/search", api_key=api_key, timeout=timeout, json=compact(payload))
    token = started.get("searchToken")
    if not token:
        msg = "Ktemia API returned a search response without a searchToken."
        raise KtemiaAPIError(msg)
    page = ktemia_request("GET", f"/{vertical}/results", api_key=api_key, timeout=timeout, params={"token": token})
    return {**page, "token": token}


# ── Result shaping: one flat row per result, plus a one-line summary as text ──


def _formatted(value: Any) -> str | None:
    """Return ``formatted`` from a price object, or None."""
    return value.get("formatted") if isinstance(value, dict) else None


def _names(page: dict[str, Any]) -> dict[str, str]:
    """Map provider and airline codes to display names from the page's ``providers`` table."""
    table = page.get("providers") or {}
    return {code: info.get("name") or code for code, info in table.items() if isinstance(info, dict)}


def flight_rows(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a flights results page into one row per itinerary."""
    names = _names(page)
    rows = []
    for flight in page.get("flights") or []:
        if not isinstance(flight, dict):
            continue
        legs = [leg for leg in flight.get("legs") or [] if isinstance(leg, dict)]
        options = [option for option in flight.get("bookingOptions") or [] if isinstance(option, dict)]
        cheapest = min(options, key=lambda o: o.get("totalPrice") or o.get("price") or 0, default={})
        airlines = []
        for leg in legs:
            for segment in leg.get("segments") or []:
                code = segment.get("airline")
                if code and names.get(code, code) not in airlines:
                    airlines.append(names.get(code, code))
        first = legs[0] if legs else {}
        segments = first.get("segments") or [{}]
        rows.append(
            {
                "result_id": flight.get("id"),
                "token": page.get("token"),
                "origin": segments[0].get("origin"),
                "destination": segments[-1].get("destination"),
                "departure": first.get("departure"),
                "arrival": first.get("arrival"),
                "stops": first.get("stops"),
                "duration_minutes": first.get("duration"),
                "legs": len(legs),
                "airlines": ", ".join(airlines),
                "price": cheapest.get("formattedTotalPrice") or cheapest.get("formattedPrice"),
                "seller": names.get(cheapest.get("providerCode"), cheapest.get("providerCode")),
                "sellers": flight.get("totalProviders") or len(options),
            }
        )
    return rows


def hotel_rows(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a hotels results page into one row per hotel."""
    rows = []
    for hotel in page.get("hotels") or []:
        if not isinstance(hotel, dict):
            continue
        best = hotel.get("bestOption") or {}
        rating = hotel.get("rating") or {}
        location = hotel.get("location") or {}
        rows.append(
            {
                "result_id": hotel.get("id"),
                "token": page.get("token"),
                "name": hotel.get("name"),
                "stars": hotel.get("stars"),
                "rating": rating.get("score"),
                "reviews": rating.get("reviewCount"),
                "neighborhood": location.get("neighborhood") or location.get("city"),
                "price": _formatted(best.get("price")),
                "total_with_taxes": _formatted(best.get("totalPrice")),
                "seller": best.get("provider"),
                "sellers": hotel.get("optionCount"),
            }
        )
    return rows


def car_rows(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a cars results page into one row per car."""
    rows = []
    for car in page.get("cars") or []:
        if not isinstance(car, dict):
            continue
        vehicle = car.get("car") or {}
        best = car.get("bestOption") or {}
        pickup = car.get("pickup") or {}
        options = [option for option in car.get("bookingOptions") or [] if isinstance(option, dict)]
        seller_names = {o.get("provider"): o.get("providerName") for o in options if o.get("providerName")}
        rows.append(
            {
                "result_id": car.get("id"),
                "token": page.get("token"),
                "car": vehicle.get("name"),
                "class": vehicle.get("class"),
                "transmission": vehicle.get("transmission"),
                "passengers": vehicle.get("passengers"),
                "agency": (car.get("agency") or {}).get("name"),
                "pickup": pickup.get("address") or pickup.get("city"),
                "price": _formatted(best.get("price")) or _formatted(car.get("price")),
                "per_day": _formatted(best.get("perDay")),
                "free_cancellation": best.get("freeCancellation"),
                "seller": seller_names.get(best.get("provider"), best.get("provider")),
                "sellers": len(options) or None,
            }
        )
    return rows


def booking_option_rows(vertical: str, details: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a details response into one row per seller, with its booking link."""
    names = _names(details)
    rows = []
    for option in details.get("bookingOptions") or []:
        if not isinstance(option, dict):
            continue
        if vertical == "flights":
            seller = names.get(option.get("providerCode"), option.get("providerCode"))
            price = option.get("formattedPrice")
            total = option.get("formattedTotalPrice")
        elif vertical == "cars":
            provider = option.get("provider")
            seller = provider.get("name") if isinstance(provider, dict) else provider
            price = _formatted(option.get("price"))
            total = _formatted(option.get("totalPrice"))
        else:
            seller = option.get("provider")
            price = _formatted(option.get("price"))
            total = _formatted(option.get("totalPrice"))
        rows.append(
            {
                "seller": seller,
                "price": price,
                "total_price": total,
                "booking_url": option.get("providerUrl"),
                "result_id": details.get("resultId"),
            }
        )
    return rows


def summarize(row: dict[str, Any]) -> str:
    """One-line text for a row, so an agent can read results without the table."""
    return "; ".join(f"{key}: {value}" for key, value in row.items() if value not in (None, "") and key != "token")

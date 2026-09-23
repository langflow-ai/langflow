"""Unit tests for the UniRate currency-conversion extension bundle (``lfx-unirate``).

The component calls the UniRate convert endpoint with ``httpx``; the tests patch
``httpx.get`` at the component module to return real ``httpx.Response`` objects,
so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_unirate import UniRateConversionComponent

GET_PATCH_TARGET = "lfx_unirate.components.unirate.unirate_conversion.httpx.get"
CONVERT_URL = "https://api.unirateapi.com/api/convert"

# UniRate returns the converted amount as a string in the ``result`` field.
SAMPLE_PAYLOAD = {"result": "92.50"}


def _response(status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", CONVERT_URL), **kwargs)


def _mock_get(payload: object) -> MagicMock:
    return MagicMock(return_value=_response(json=payload))


@pytest.fixture
def component() -> UniRateConversionComponent:
    c = UniRateConversionComponent()
    c.to_currency = "EUR"
    c.from_currency = "USD"
    c.amount = 100.0
    c.unirate_api_key = "test-key"  # pragma: allowlist secret
    return c


def test_component_metadata():
    """Class name must stay stable for saved flows."""
    assert UniRateConversionComponent.__name__ == "UniRateConversionComponent"


def test_missing_api_key_raises(component):
    """No key set -> clear ValueError instead of an anonymous request."""
    component.unirate_api_key = ""
    with pytest.raises(ValueError, match="UniRate API key is required"):
        component._convert()


def test_missing_target_currency_raises(component):
    """No target currency -> clear ValueError instead of a malformed request."""
    component.to_currency = "  "
    with pytest.raises(ValueError, match="Target currency is required"):
        component._convert()


def test_fetch_content_reports_missing_api_key_without_request(component):
    """The public output turns a missing key into an error row and never calls the API."""
    component.unirate_api_key = ""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    mock_get.assert_not_called()
    assert len(results) == 1
    assert "UniRate API key is required" in results[0].data["error"]


def test_convert_sends_key_params_and_accept_header(component):
    """The request is a GET to the convert endpoint with the key and Accept header."""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        component._convert()
    assert mock_get.call_args.args[0] == CONVERT_URL
    params = mock_get.call_args.kwargs["params"]
    assert params["api_key"] == "test-key"  # pragma: allowlist secret
    assert params["from"] == "USD"
    assert params["to"] == "EUR"
    assert params["amount"] == 100.0
    # UniRate returns HTML 404 on some endpoints without this header.
    assert mock_get.call_args.kwargs["headers"]["Accept"] == "application/json"


def test_currency_codes_are_uppercased(component):
    """Lowercase currency codes are uppercased before the request is sent."""
    component.from_currency = "usd"
    component.to_currency = "gbp"
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        component._convert()
    params = mock_get.call_args.kwargs["params"]
    assert params["from"] == "USD"
    assert params["to"] == "GBP"


def test_from_currency_defaults_to_usd(component):
    """An empty From Currency falls back to USD."""
    component.from_currency = ""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        component._convert()
    assert mock_get.call_args.kwargs["params"]["from"] == "USD"


def test_fetch_content_maps_result_and_computes_rate(component):
    """The result maps to Data(text, data={from,to,amount,rate,result}); rate = result / amount."""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 1
    data = results[0].data
    assert data["from"] == "USD"
    assert data["to"] == "EUR"
    assert data["amount"] == 100.0
    assert data["result"] == 92.5
    assert data["rate"] == pytest.approx(0.925)


def test_rate_is_none_for_zero_amount(component):
    """A zero amount does not divide-by-zero; rate is None."""
    component.amount = 0.0
    mock_get = _mock_get({"result": "0"})
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert results[0].data["rate"] is None


def test_fetch_content_rejects_missing_result_field(component):
    """A payload without a result field becomes an error row, not a KeyError."""
    mock_get = _mock_get({"rates": {"EUR": "0.92"}})
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 1
    assert "unexpected response" in results[0].data["error"]


def test_fetch_content_rejects_non_numeric_result(component):
    """A non-numeric result becomes an error row, not a ValueError."""
    mock_get = _mock_get({"result": "not-a-number"})
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 1
    assert "non-numeric" in results[0].data["error"]


def test_fetch_content_wraps_http_error(component):
    """A transport error is surfaced as a single error Data, not raised."""
    mock_get = MagicMock(side_effect=httpx.HTTPError("boom"))
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 1
    assert "boom" in results[0].data["error"]


def test_fetch_content_surfaces_api_error_message(component):
    """A 401 keeps the API's own error message instead of the generic httpx message."""
    body = {"error": "Missing or invalid API key"}
    mock_get = MagicMock(return_value=_response(401, json=body))
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert len(results) == 1
    assert results[0].data["error"] == "UniRate API error 401: Missing or invalid API key"


def test_fetch_content_http_error_without_json_body(component):
    """A non-JSON error body falls back to the HTTP reason phrase."""
    mock_get = MagicMock(return_value=_response(503, text="service down"))
    with patch(GET_PATCH_TARGET, mock_get):
        results = component.fetch_content()
    assert results[0].data["error"] == "UniRate API error 503: Service Unavailable"


def test_convert_currency_dataframe_shape(component):
    """The default output builds a one-row DataFrame from the conversion."""
    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        frame = component.convert_currency()
    assert len(frame) == 1


def test_tool_mode_exposes_a_unirate_specific_tool():
    """The agent-facing tool name must not collide with other finance components."""
    # Tools read inputs the way a graph sets them (constructor kwargs), not
    # attributes assigned after construction, so build the component directly.
    component = UniRateConversionComponent(unirate_api_key="test-key")  # pragma: allowlist secret
    tools = asyncio.run(component.to_toolkit())
    assert [tool.name for tool in tools] == ["convert_currency"]

    mock_get = _mock_get(SAMPLE_PAYLOAD)
    with patch(GET_PATCH_TARGET, mock_get):
        output = asyncio.run(tools[0].ainvoke({"to_currency": "eur", "amount": 100, "from_currency": "usd"}))
    params = mock_get.call_args.kwargs["params"]
    assert params["to"] == "EUR"
    assert params["from"] == "USD"
    assert "92.5" in str(output)

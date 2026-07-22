from __future__ import annotations

from unittest.mock import Mock, patch

import httpx
import pytest
from lfx_adanos import AdanosMarketSentimentComponent
from lfx_adanos.components.adanos.adanos_market_sentiment import ADANOS_REQUEST_TIMEOUT

HTTPX_GET = "lfx_adanos.components.adanos.adanos_market_sentiment.httpx.get"


@pytest.fixture
def component() -> AdanosMarketSentimentComponent:
    instance = AdanosMarketSentimentComponent()
    instance.api_key = "placeholder"  # pragma: allowlist secret
    instance.operation = "Asset sentiment"
    instance.asset_type = "Stocks"
    instance.source = "Reddit"
    instance.symbol = "AAPL"
    instance.start_date = ""
    instance.end_date = ""
    instance.limit = 20
    return instance


def successful_response(payload: object) -> Mock:
    response = Mock(spec=httpx.Response)
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_component_metadata() -> None:
    assert AdanosMarketSentimentComponent.name == "AdanosMarketSentiment"
    assert AdanosMarketSentimentComponent.documentation == "https://api.adanos.org/docs"


def test_frontend_schema_marks_api_key_as_secret() -> None:
    node = AdanosMarketSentimentComponent().to_frontend_node()["data"]["node"]

    assert node["template"]["api_key"]["password"] is True
    assert node["template"]["symbol"]["tool_mode"] is True
    assert node["template"]["asset_type"]["real_time_refresh"] is True
    assert node["template"]["source"]["dynamic"] is True


def test_secret_value_unwraps_secret_str_like_object() -> None:
    secret = Mock()
    secret.get_secret_value.return_value = "  unwrapped-key  "

    assert AdanosMarketSentimentComponent._secret_value(secret) == "unwrapped-key"


@pytest.mark.parametrize(("asset_type", "visibility"), [("Stocks", "visible"), ("Crypto", "hidden")])
def test_asset_type_controls_stock_source_visibility(asset_type: str, visibility: str) -> None:
    component = AdanosMarketSentimentComponent()
    build_config = {"source": {"show": True}}

    result = component.update_build_config(build_config, asset_type, "asset_type")

    assert result["source"]["show"] is (visibility == "visible")


@patch(HTTPX_GET)
def test_fetches_stock_sentiment_with_dates(mock_get: Mock, component: AdanosMarketSentimentComponent) -> None:
    component.source = "X / FinTwit"
    component.symbol = "$tsla"
    component.start_date = "2026-07-01"
    component.end_date = "2026-07-20"
    mock_get.return_value = successful_response({"ticker": "TSLA", "sentiment": 0.42})

    result = component.fetch_sentiment()

    assert result.data == {"ticker": "TSLA", "sentiment": 0.42}
    mock_get.assert_called_once_with(
        "https://api.adanos.org/x/stocks/v1/stock/TSLA",
        headers={"X-API-Key": "placeholder", "Accept": "application/json"},  # pragma: allowlist secret
        params={"from": "2026-07-01", "to": "2026-07-20"},
        timeout=ADANOS_REQUEST_TIMEOUT,
    )


@patch(HTTPX_GET)
def test_crypto_uses_reddit_token_endpoint(mock_get: Mock, component: AdanosMarketSentimentComponent) -> None:
    component.asset_type = "Crypto"
    component.source = "Polymarket"
    component.symbol = "btc"
    mock_get.return_value = successful_response({"symbol": "BTC"})

    component.fetch_sentiment()

    assert mock_get.call_args.args[0] == "https://api.adanos.org/reddit/crypto/v1/token/BTC"


@patch(HTTPX_GET)
def test_trending_adds_limit_and_wraps_list(mock_get: Mock, component: AdanosMarketSentimentComponent) -> None:
    component.operation = "Trending assets"
    component.source = "News"
    component.limit = 7
    mock_get.return_value = successful_response([{"ticker": "NVDA"}])

    result = component.fetch_sentiment()

    assert result.data == {"results": [{"ticker": "NVDA"}]}
    assert mock_get.call_args.args[0] == "https://api.adanos.org/news/stocks/v1/trending"
    assert mock_get.call_args.kwargs["params"] == {"limit": 7}


@patch(HTTPX_GET)
def test_market_sentiment_omits_limit(mock_get: Mock, component: AdanosMarketSentimentComponent) -> None:
    component.operation = "Market sentiment"
    component.limit = 99
    mock_get.return_value = successful_response({"sentiment": "bullish"})

    component.fetch_sentiment()

    assert mock_get.call_args.args[0] == "https://api.adanos.org/reddit/stocks/v1/market-sentiment"
    assert mock_get.call_args.kwargs["params"] == {}


@pytest.mark.parametrize("value", [0, 101, None])
def test_rejects_invalid_trending_limit(component: AdanosMarketSentimentComponent, value: int | None) -> None:
    component.operation = "Trending assets"
    component.limit = value

    with pytest.raises(ValueError, match="between 1 and 100"):
        component._request_parts()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start_date", "07/20/2026"),
        ("start_date", "20260720"),
        ("start_date", "2026-W30-1"),
        ("end_date", "2026-02-30"),
    ],
)
def test_rejects_invalid_dates(component: AdanosMarketSentimentComponent, field: str, value: str) -> None:
    setattr(component, field, value)

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        component._request_parts()


def test_rejects_reversed_date_range(component: AdanosMarketSentimentComponent) -> None:
    component.start_date = "2026-07-20"
    component.end_date = "2026-07-01"

    with pytest.raises(ValueError, match="cannot be after"):
        component._request_parts()


@pytest.mark.parametrize(
    ("asset_type", "symbol"),
    [("Stocks", "AAPL/../../admin"), ("Stocks", "ABCDEFGHIJK"), ("Stocks", "1"), ("Crypto", "BTC ETH")],
)
def test_rejects_invalid_symbols(component: AdanosMarketSentimentComponent, asset_type: str, symbol: str) -> None:
    component.asset_type = asset_type
    component.symbol = symbol

    with pytest.raises(ValueError, match="valid ticker or crypto symbol"):
        component._request_parts()


def test_requires_api_key(component: AdanosMarketSentimentComponent) -> None:
    component.api_key = ""

    with pytest.raises(ValueError, match="API key is required"):
        component.fetch_sentiment()


@patch(HTTPX_GET)
def test_http_errors_do_not_expose_response_body(mock_get: Mock, component: AdanosMarketSentimentComponent) -> None:
    request = httpx.Request("GET", "https://api.adanos.org/reddit/stocks/v1/stock/AAPL")
    response = httpx.Response(401, request=request, text="sensitive upstream detail")
    mock_get.return_value = response

    with pytest.raises(ValueError, match=r"status 401\.$") as exc_info:
        component.fetch_sentiment()

    assert "sensitive upstream detail" not in str(exc_info.value)


@patch(HTTPX_GET)
def test_network_errors_are_sanitized(mock_get: Mock, component: AdanosMarketSentimentComponent) -> None:
    request = httpx.Request("GET", "https://api.adanos.org/reddit/stocks/v1/stock/AAPL")
    mock_get.side_effect = httpx.ConnectError("internal network detail", request=request)

    with pytest.raises(ValueError, match="Could not retrieve market sentiment from Adanos") as exc_info:
        component.fetch_sentiment()

    assert "internal network detail" not in str(exc_info.value)

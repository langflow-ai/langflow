from functools import partial

import httpx
from lfx.components.bocha.bocha_web_search import BochaSearchComponent


class CapturingClient:
    def __init__(self, captured, response, **_kwargs):
        self.captured = captured
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def post(self, url, json, headers):
        self.captured["url"] = url
        self.captured["json"] = json
        self.captured["headers"] = headers
        return self.response


def build_component(count):
    component = BochaSearchComponent()
    component.set_attributes(
        {
            "api_key": "test-key",
            "query": "test query",
            "summary": True,
            "freshness": "noLimit",
            "count": count,
        }
    )
    return component


def test_fetch_content_clamps_count_before_request(monkeypatch):
    captured = {}
    response = httpx.Response(
        200,
        json={"data": {"webPages": {"value": []}}},
        request=httpx.Request("POST", "https://api.bochaai.com/v1/web-search"),
    )

    monkeypatch.setattr(
        "lfx.components.bocha.bocha_web_search.httpx.Client",
        partial(CapturingClient, captured, response),
    )

    build_component(0).fetch_content()

    assert captured["json"]["count"] == 1


def test_fetch_content_caps_count_before_request(monkeypatch):
    captured = {}
    response = httpx.Response(
        200,
        json={"data": {"webPages": {"value": []}}},
        request=httpx.Request("POST", "https://api.bochaai.com/v1/web-search"),
    )

    monkeypatch.setattr(
        "lfx.components.bocha.bocha_web_search.httpx.Client",
        partial(CapturingClient, captured, response),
    )

    build_component(51).fetch_content()

    assert captured["json"]["count"] == 50


def test_fetch_content_returns_error_data_for_invalid_json(monkeypatch):
    response = httpx.Response(
        200,
        content=b"not json",
        request=httpx.Request("POST", "https://api.bochaai.com/v1/web-search"),
    )

    monkeypatch.setattr(
        "lfx.components.bocha.bocha_web_search.httpx.Client",
        partial(CapturingClient, {}, response),
    )

    result = build_component(10).fetch_content()

    assert len(result) == 1
    assert "Bocha response parse error" in result[0].text
    assert result[0].data["error"] == result[0].text

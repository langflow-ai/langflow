"""Tests for DoclingRemoteComponent compatibility and polling behavior."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

pytest.importorskip("docling_core")

# NOTE: Import the bundle component module before lfx.inputs/lfx.schema. Importing
# lfx.inputs/lfx.schema first leaves lfx.custom partially initialized and triggers a
# circular import when the component (a Component subclass) is imported afterwards.
# isort: off
from lfx_docling.components.docling import docling_remote
from lfx_docling.components.docling.docling_remote import DoclingRemoteComponent

from lfx.inputs import TableInput
from lfx.schema import Data

# isort: on


class _Message:
    def __init__(self, text: str) -> None:
        self.text = text


_UNSET = object()


class _Response:
    def __init__(self, status_code: int, payload: Any = _UNSET) -> None:
        self.status_code = status_code
        self.payload = payload
        self.json_called = False
        self.request = httpx.Request("GET", "http://docling.test/v1/status/poll/task-1")
        self.response = httpx.Response(status_code, request=self.request)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            msg = f"HTTP error {self.status_code}"
            raise httpx.HTTPStatusError(msg, request=self.request, response=self.response)

    def json(self) -> Any:
        self.json_called = True
        if self.payload is _UNSET:
            msg = "json() should not be called for this response"
            raise AssertionError(msg)
        return self.payload


class _Client:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str) -> _Response:
        self.urls.append(url)
        return self.responses.pop(0)


def _input(name: str):
    return next(input_ for input_ in DoclingRemoteComponent.inputs if input_.name == name)


def test_api_headers_uses_table_input_contract() -> None:
    api_headers = _input("api_headers")

    assert isinstance(api_headers, TableInput)
    assert api_headers.input_types == ["Data", "JSON"]
    columns = {column["name"]: column for column in api_headers.table_schema}
    assert columns["key"].get("load_from_db") is not True
    assert columns["value"].get("load_from_db") is True


def test_process_headers_skips_blank_and_none_keys_across_input_shapes() -> None:
    component = DoclingRemoteComponent()
    component._attributes.update(
        {
            "api_headers": [
                Data(data={"key": " X-Data ", "value": "data"}),
                Data(data={"key": " ", "value": "skip"}),
                Data(data={"X-Data-Fallback": "fallback", "": "skip", None: "skip"}),
                {"key": "X-Table", "value": 123},
                {"key": None, "value": "skip"},
                {"X-Merged": "merged", "  ": "skip", "None": "skip"},
                _Message('{" X-Message ": "message", "": "skip", "None": "skip"}'),
            ],
        }
    )

    assert component._process_headers() == {
        "X-Data": "data",
        "X-Data-Fallback": "fallback",
        "X-Table": "123",
        "X-Merged": "merged",
        "X-Message": "message",
    }


def test_update_build_config_migrates_dict_values_to_api_headers_table_rows() -> None:
    component = DoclingRemoteComponent()
    headers = {"Authorization": "Bearer token"}
    build_config = {
        "api_headers": {"value": []},
    }

    updated = component.update_build_config(build_config, headers, "api_headers")

    assert updated["api_headers"]["value"] == [{"key": "Authorization", "value": "Bearer token"}]


def test_poll_retries_initial_5xx_before_returning_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(docling_remote.time, "sleep", lambda _seconds: None)
    component = DoclingRemoteComponent()
    component._attributes["max_poll_timeout"] = 60
    responses = [_Response(500) for _ in range(component.MAX_500_RETRIES + 1)]
    client = _Client(responses)

    result = component._poll_and_fetch_result(client, "http://docling.test/v1", "task-1")

    assert result is None
    assert len(client.urls) == component.MAX_500_RETRIES + 1


def test_poll_raises_later_4xx_before_json_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(docling_remote.time, "sleep", lambda _seconds: None)
    component = DoclingRemoteComponent()
    component._attributes["max_poll_timeout"] = 60
    pending_response = _Response(200, {"task_status": "pending"})
    not_found_response = _Response(404)
    client = _Client([pending_response, not_found_response])

    with pytest.raises(httpx.HTTPStatusError):
        component._poll_and_fetch_result(client, "http://docling.test/v1", "task-1")

    assert pending_response.json_called is True
    assert not_found_response.json_called is False

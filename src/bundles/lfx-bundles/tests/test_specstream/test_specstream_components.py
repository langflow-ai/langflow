"""Unit tests for the SpecStream Find List component with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.request``, so the tests exercise the real
request flow: read, quote, approve within the ceiling, poll, read the rows.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx_bundles.specstream.base import SpecStreamClient, SpecStreamError, flatten_row
from lfx_bundles.specstream.find_list import SpecStreamFindListComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-specstream-api-key-placeholder"  # pragma: allowlist secret
REQUEST = "Roofing companies in Columbus, Ohio with their website"
FIND_ID = "fnd_test123"


def _ok(data: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"data": data}, request=httpx.Request("GET", "https://api.specstream.ai"))


def _status(code: int, body: Any = None) -> httpx.Response:
    return httpx.Response(code, json=body, request=httpx.Request("GET", "https://api.specstream.ai"))


ROWS_PAGE = {
    "status": "completed",
    "rows": [
        {
            "ordinal": 1,
            "details": [
                {
                    "label": "Company",
                    "display": "Acme Roofing",
                    "provenance": {"source_url": "https://acme.example/about", "observed_at": "2026-10-15T10:00:00Z"},
                },
                {"label": "Website", "value": "https://acme.example"},
                {"label": "source_url", "display": "clash"},
                {"label": "Phone", "absence": True},
            ],
        },
        {"ordinal": 2, "cells": [{"column_id": "Company", "display": "Buckeye Roofs"}]},
    ],
    "next_cursor": None,
}


class FakeSpecStream:
    """Routes the SpecStream endpoints and records every call."""

    def __init__(self, *, maximum_cents: int = 300, existing: dict | None = None, runnable: bool = True) -> None:
        self.maximum_cents = maximum_cents
        self.existing = existing
        self.runnable = runnable
        self.calls: list[tuple[str, str, Any]] = []

    def __call__(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        path = url.removeprefix("https://api.specstream.ai")
        self.calls.append((method, path, kwargs.get("json")))
        if method == "GET" and path.startswith("/v1/capacity/requests/"):
            return _ok(self.existing) if self.existing else _status(404, {"error": {"message": "not found"}})
        if method == "POST" and path == "/v1/parse":
            if not self.runnable:
                return _ok({"status": "needs_edit", "canonical_sentence": "Roofing companies"})
            return _ok({"status": "runnable", "ast_hash": "ast_1"})
        if method == "POST" and path == "/v1/capacity/quotes":
            return _ok({"quote_id": "q_1", "quote_hash": "h_1", "maximum_cents": self.maximum_cents})
        if method == "POST" and path == "/v1/capacity/executions":
            return _ok({"find_id": FIND_ID})
        if method == "GET" and path.startswith(f"/v1/finds/{FIND_ID}/rows"):
            return _ok(ROWS_PAGE)
        msg = f"unexpected call {method} {path}"
        raise AssertionError(msg)

    def paths(self) -> list[str]:
        return [f"{method} {path.split('?')[0]}" for method, path, _ in self.calls]


def _component(**overrides: Any) -> SpecStreamFindListComponent:
    values = {"api_key": API_KEY, "request": REQUEST, "max_results": 10, "max_price_usd": 5.0, "wait_seconds": 0}
    values.update(overrides)
    component = SpecStreamFindListComponent()
    component.set(**values)
    return component


@pytest.mark.unit
def test_input_names_do_not_shadow_component_attributes() -> None:
    shadowed = [inp.name for inp in SpecStreamFindListComponent.inputs if hasattr(Component, inp.name)]
    assert shadowed == []


@pytest.mark.unit
class TestFlattenRow:
    def test_keeps_labels_source_and_renames_reserved_columns(self) -> None:
        row = flatten_row(FIND_ID, ROWS_PAGE["rows"][0])

        assert row["Company"] == "Acme Roofing"
        assert row["Website"] == "https://acme.example"
        assert row["Phone"] == ""
        assert row["source_url (column)"] == "clash"
        assert row["source_url"] == "https://acme.example/about"
        assert row["checked_at"] == "2026-10-15T10:00:00Z"
        assert row["position"] == 1
        assert row["list_link"].endswith(f"/workspace/collections/{FIND_ID}")

    def test_row_without_provenance_has_empty_source(self) -> None:
        row = flatten_row(FIND_ID, ROWS_PAGE["rows"][1])

        assert row["Company"] == "Buckeye Roofs"
        assert row["source_url"] == ""


@pytest.mark.unit
class TestFindList:
    def test_runs_quote_approval_and_returns_rows(self) -> None:
        fake = FakeSpecStream()
        with patch.object(httpx.Client, "request", side_effect=fake):
            table = _component().find_list_dataframe()

        assert isinstance(table, DataFrame)
        assert list(table["Company"]) == ["Acme Roofing", "Buckeye Roofs"]
        assert list(table["source_url"]) == ["https://acme.example/about", ""]
        assert fake.paths()[-4:-1] == ["POST /v1/parse", "POST /v1/capacity/quotes", "POST /v1/capacity/executions"]
        execution = next(body for method, path, body in fake.calls if path == "/v1/capacity/executions")
        assert execution["confirm_max_cents"] == 300
        assert execution["quote_id"] == "q_1"
        assert execution["idempotency_key"].startswith("langflow-")
        quote = next(body for method, path, body in fake.calls if path == "/v1/capacity/quotes")
        assert quote["requested_units"] == 10

    def test_sends_bearer_key_and_never_puts_it_in_the_url(self) -> None:
        seen: list[dict] = []

        def spy(method: str, url: str, **kwargs: Any) -> httpx.Response:
            seen.append({"url": url, "headers": kwargs.get("headers")})
            return FakeSpecStream()(method, url, **kwargs)

        with patch.object(httpx.Client, "request", side_effect=spy):
            _component().find_list_data()

        assert all(call["headers"]["Authorization"] == f"Bearer {API_KEY}" for call in seen)
        assert all(API_KEY not in call["url"] for call in seen)

    def test_data_output_has_one_data_per_row(self) -> None:
        with patch.object(httpx.Client, "request", side_effect=FakeSpecStream()):
            rows = _component().find_list_data()

        assert len(rows) == 2
        assert all(isinstance(item, Data) for item in rows)
        assert rows[0].data["source_url"] == "https://acme.example/about"

    def test_quote_above_the_maximum_runs_nothing(self) -> None:
        fake = FakeSpecStream(maximum_cents=900)
        with (
            patch.object(httpx.Client, "request", side_effect=fake),
            pytest.raises(SpecStreamError, match=r"above the maximum of \$5\.00"),
        ):
            _component().find_list_dataframe()

        assert "POST /v1/capacity/executions" not in fake.paths()

    def test_unclear_request_runs_nothing(self) -> None:
        fake = FakeSpecStream(runnable=False)
        with patch.object(httpx.Client, "request", side_effect=fake), pytest.raises(SpecStreamError, match="clearer"):
            _component().find_list_dataframe()

        assert "POST /v1/capacity/quotes" not in fake.paths()

    def test_existing_run_is_reused_without_a_new_quote(self) -> None:
        fake = FakeSpecStream(existing={"find_id": FIND_ID, "maximum_cents": 300})
        with patch.object(httpx.Client, "request", side_effect=fake):
            table = _component().find_list_dataframe()

        assert len(table) == 2
        assert "POST /v1/capacity/quotes" not in fake.paths()
        assert "POST /v1/capacity/executions" not in fake.paths()

    def test_run_key_becomes_the_idempotency_key(self) -> None:
        fake = FakeSpecStream()
        with patch.object(httpx.Client, "request", side_effect=fake):
            _component(run_key="weekly-roofers").find_list_dataframe()

        execution = next(body for method, path, body in fake.calls if path == "/v1/capacity/executions")
        assert execution["idempotency_key"] == "langflow-weekly-roofers"
        assert fake.calls[0][1] == "/v1/capacity/requests/langflow-weekly-roofers"

    def test_same_request_in_the_same_hour_gets_the_same_key(self) -> None:
        keys = []
        for _ in range(2):
            fake = FakeSpecStream()
            with patch.object(httpx.Client, "request", side_effect=fake):
                _component().find_list_dataframe()
            keys.append(next(body for method, path, body in fake.calls if path == "/v1/capacity/executions"))

        assert keys[0]["idempotency_key"] == keys[1]["idempotency_key"]

    def test_both_outputs_share_one_run(self) -> None:
        fake = FakeSpecStream()
        component = _component()
        with patch.object(httpx.Client, "request", side_effect=fake):
            component.find_list_dataframe()
            component.find_list_data()

        assert fake.paths().count("POST /v1/capacity/executions") == 1

    def test_follows_row_pages(self) -> None:
        pages = [
            {
                "status": "completed",
                "rows": [{"ordinal": 1, "cells": [{"label": "A", "display": "1"}]}],
                "next_cursor": "c2",
            },
            {
                "status": "completed",
                "rows": [{"ordinal": 2, "cells": [{"label": "A", "display": "2"}]}],
                "next_cursor": None,
            },
        ]
        calls: list[str] = []

        def handler(_method: str, url: str, **_: Any) -> httpx.Response:
            calls.append(url)
            return _ok(pages.pop(0))

        with patch.object(httpx.Client, "request", side_effect=handler):
            result = SpecStreamClient(API_KEY).results(FIND_ID)

        assert [row["A"] for row in result["rows"]] == ["1", "2"]
        assert "cursor=c2" in calls[1]

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"request": "  "}, "Describe the list"),
            ({"max_results": 0}, "1 or more"),
            ({"max_price_usd": 0}, "greater than 0"),
        ],
    )
    def test_rejects_bad_inputs_before_any_call(self, overrides: dict, message: str) -> None:
        with (
            patch.object(httpx.Client, "request", side_effect=AssertionError("no call expected")),
            pytest.raises(SpecStreamError, match=message),
        ):
            _component(**overrides).find_list_dataframe()

    def test_missing_api_key(self) -> None:
        with pytest.raises(SpecStreamError, match="API key is required"):
            _component(api_key="").find_list_dataframe()


@pytest.mark.unit
class TestErrors:
    def test_http_error_carries_status_and_message(self) -> None:
        response = _status(401, {"error": {"message": "Invalid API key"}})
        with (
            patch.object(httpx.Client, "request", return_value=response),
            pytest.raises(SpecStreamError, match="answered 401: Invalid API key"),
        ):
            _component().find_list_dataframe()

    def test_unreadable_body(self) -> None:
        response = httpx.Response(200, text="<html>", request=httpx.Request("GET", "https://api.specstream.ai"))
        with (
            patch.object(httpx.Client, "request", return_value=response),
            pytest.raises(SpecStreamError, match="couldn't read"),
        ):
            _component().find_list_dataframe()

    def test_timeout_and_connection_errors(self) -> None:
        with (
            patch.object(httpx.Client, "request", side_effect=httpx.ReadTimeout("slow")),
            pytest.raises(SpecStreamError, match="did not answer"),
        ):
            _component().find_list_dataframe()
        with (
            patch.object(httpx.Client, "request", side_effect=httpx.ConnectError("down")),
            pytest.raises(SpecStreamError, match="Couldn't reach SpecStream"),
        ):
            _component().find_list_dataframe()

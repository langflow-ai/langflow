import json
from unittest.mock import patch

import httpx
import pytest

pytest.importorskip("lfx_bundles")

from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_bundles.jsonify.jsonify_dataset import JsonifyDatasetComponent, JsonifyFetchError

SERVE_URL = "https://factory.jsonify.com/api/serve/abc123"
BLOCKED_URL = "http://169.254.169.254/latest/meta-data"
FETCH = "lfx_bundles.jsonify.jsonify_dataset.ssrf_safe_httpx_get_bounded"

PAGE_ONE = {
    "dataset": "abc123",
    "dataset_name": "Competitor watch",
    "table": "competitor_changes",
    "version": 12,
    "updated_at": 1760400000,
    "row_count": 2,
    "has_more": True,
    "next_offset": 2,
    "rows": [
        {"_row_id": "r1", "competitor": "Klue", "page": "homepage"},
        {"_row_id": "r2", "competitor": "Crayon", "page": "pricing"},
    ],
}
PAGE_TWO = {
    **PAGE_ONE,
    "row_count": 1,
    "has_more": False,
    "next_offset": None,
    "rows": [{"_row_id": "r3", "competitor": "Kompyte", "page": "pricing"}],
}


def _body(payload):
    return json.dumps(payload).encode()


def _status_error(status):
    request = httpx.Request("GET", SERVE_URL)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"Client error '{status}' for url '{SERVE_URL}'", request=request, response=response)


def test_fetch_rows_pages_pins_version_and_adds_row_id():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL, columns="competitor", filters='{"page": "pricing"}')
    with patch(FETCH, side_effect=[_body(PAGE_ONE), _body(PAGE_TWO)]) as mock_get:
        rows = component.fetch_rows()

    assert [r.data["_row_id"] for r in rows] == ["r1", "r2", "r3"]
    first_params = mock_get.call_args_list[0].kwargs["params"]
    second_params = mock_get.call_args_list[1].kwargs["params"]
    assert first_params["columns"] == "_row_id,competitor"
    assert first_params["filter[page]"] == "pricing"
    assert "version" not in first_params
    assert second_params["offset"] == 2
    assert second_params["version"] == 12
    assert mock_get.call_args.kwargs["max_bytes"] > 0


def test_configured_version_is_forwarded():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL, version=7)
    with patch(FETCH, return_value=_body(PAGE_TWO)) as mock_get:
        component.fetch_rows()
    assert mock_get.call_args.kwargs["params"]["version"] == 7


def test_fetch_dataframe_respects_max_rows():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL, max_rows=1)
    with patch(FETCH, return_value=_body(PAGE_ONE)) as mock_get:
        frame = component.fetch_dataframe()

    assert mock_get.call_args.kwargs["params"]["limit"] == 1
    assert len(frame) == 1


def test_stops_when_cursor_does_not_advance():
    stuck = {**PAGE_ONE, "next_offset": 0}
    component = JsonifyDatasetComponent(serve_url=SERVE_URL)
    with patch(FETCH, return_value=_body(stuck)) as mock_get:
        rows = component.fetch_rows()
    assert mock_get.call_count == 1
    assert len(rows) == 2


def test_tool_hides_serve_url_and_reports_truncation():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL)
    tool = component.build_tool()
    properties = tool.args_schema.model_json_schema()["properties"]
    assert "serve_url" not in properties
    assert properties["max_rows"]["minimum"] == 1

    with patch(FETCH, return_value=_body(PAGE_ONE)):
        result = json.loads(tool.func(filters={}, columns=[], max_rows=1))

    assert result["dataset_name"] == "Competitor watch"
    assert result["row_count"] == 1
    assert result["truncated"] is True


def test_tool_rejects_zero_max_rows():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL)
    tool = component.build_tool()
    with pytest.raises(Exception, match="max_rows"):
        tool.invoke({"max_rows": 0})


def test_tool_merges_configured_filters_and_columns():
    component = JsonifyDatasetComponent(
        serve_url=SERVE_URL, columns="competitor, page", filters='{"page": "pricing"}', max_rows=5
    )
    with patch(FETCH, return_value=_body(PAGE_TWO)) as mock_get:
        component._run_for_tool(filters={"competitor": "Kompyte", "page": "homepage"}, columns=["url"], max_rows=50)

    params = mock_get.call_args.kwargs["params"]
    assert params["filter[page]"] == "pricing"
    assert params["filter[competitor]"] == "Kompyte"
    assert params["columns"] == "_row_id,competitor,page"
    assert params["limit"] == 5


def test_tool_narrows_configured_columns():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL, columns="competitor, page")
    with patch(FETCH, return_value=_body(PAGE_TWO)) as mock_get:
        component._run_for_tool(columns=["page"])
    assert mock_get.call_args.kwargs["params"]["columns"] == "_row_id,page"


def test_tool_http_error_omits_url():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL)
    with patch(FETCH, side_effect=_status_error(404)):
        result = component._run_for_tool()
    assert result == "Error reading Jsonify dataset: Jsonify returned HTTP 404"
    assert SERVE_URL not in result


def test_oversized_response_error_omits_url():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL)
    with patch(FETCH, side_effect=ValueError(f"Response from {SERVE_URL} exceeds the maximum size")):
        result = component._run_for_tool()
    assert "exceeded" in result
    assert SERVE_URL not in result


def test_unexpected_shape_is_an_error():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL)
    with patch(FETCH, return_value=_body({"rows": "nope"})), pytest.raises(JsonifyFetchError, match="shape"):
        component.fetch_rows()


@pytest.mark.parametrize("filters", ["{not json", '["page"]'])
def test_malformed_filters_are_rejected(filters):
    component = JsonifyDatasetComponent(serve_url=SERVE_URL, filters=filters)
    with pytest.raises((ValueError, TypeError), match="Filters"):
        component.fetch_rows()
    assert component._run_for_tool().startswith("Error reading Jsonify dataset: Filters")


def test_blocks_metadata_url_before_request(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
    component = JsonifyDatasetComponent(serve_url=BLOCKED_URL)

    with patch.object(httpx.Client, "send") as mock_send, pytest.raises(ValueError, match="SSRF Protection"):
        component.fetch_rows()

    mock_send.assert_not_called()


def test_tool_reports_ssrf_as_redacted_error_string():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL)
    with patch(FETCH, side_effect=SSRFProtectionError(f"blocked {SERVE_URL}")):
        result = component._run_for_tool()
    assert result.startswith("Error reading Jsonify dataset: SSRF Protection")
    assert SERVE_URL not in result


def test_requires_serve_url():
    component = JsonifyDatasetComponent(serve_url="")
    with pytest.raises(ValueError, match="Serve URL"):
        component.fetch_rows()


def test_build_tool_returns_named_tool():
    tool = JsonifyDatasetComponent(serve_url=SERVE_URL).build_tool()
    assert tool.name == "read_jsonify_dataset"

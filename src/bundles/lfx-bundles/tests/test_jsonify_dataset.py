import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")

from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_bundles.jsonify.jsonify_dataset import JsonifyDatasetComponent

SERVE_URL = "https://factory.jsonify.com/api/serve/abc123"
BLOCKED_URL = "http://169.254.169.254/latest/meta-data"

PAGE_ONE = {
    "dataset": "abc123",
    "dataset_name": "Competitor watch",
    "table": "competitor_changes",
    "integration": "rest_api",
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


def _response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_fetch_rows_pages_and_pins_version():
    component = JsonifyDatasetComponent(
        serve_url=SERVE_URL, columns="_row_id, competitor", filters='{"page": "pricing"}'
    )
    with patch(
        "lfx_bundles.jsonify.jsonify_dataset.ssrf_safe_httpx_get",
        side_effect=[_response(PAGE_ONE), _response(PAGE_TWO)],
    ) as mock_get:
        rows = component.fetch_rows()

    assert [r.data["_row_id"] for r in rows] == ["r1", "r2", "r3"]
    first_params = mock_get.call_args_list[0].kwargs["params"]
    second_params = mock_get.call_args_list[1].kwargs["params"]
    assert first_params["columns"] == "_row_id,competitor"
    assert first_params["filter[page]"] == "pricing"
    assert "version" not in first_params
    assert second_params["offset"] == 2
    assert second_params["version"] == 12


def test_fetch_dataframe_respects_max_rows():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL, max_rows=1)
    with patch("lfx_bundles.jsonify.jsonify_dataset.ssrf_safe_httpx_get", return_value=_response(PAGE_ONE)) as mock_get:
        frame = component.fetch_dataframe()

    assert mock_get.call_args.kwargs["params"]["limit"] == 1
    assert len(frame) == 1


def test_tool_hides_serve_url_and_returns_json():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL)
    tool = component.build_tool()
    assert "serve_url" not in tool.args_schema.model_json_schema()["properties"]

    with patch("lfx_bundles.jsonify.jsonify_dataset.ssrf_safe_httpx_get", return_value=_response(PAGE_TWO)):
        result = json.loads(tool.func(filters={"competitor": "Kompyte"}, columns=[], max_rows=10))

    assert result["dataset_name"] == "Competitor watch"
    assert result["row_count"] == 1


def test_blocks_metadata_url_before_request(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
    component = JsonifyDatasetComponent(serve_url=BLOCKED_URL)

    with patch("httpx.get") as mock_get, pytest.raises(ValueError, match="SSRF Protection"):
        component.fetch_rows()

    mock_get.assert_not_called()


def test_tool_reports_ssrf_as_error_string():
    component = JsonifyDatasetComponent(serve_url=SERVE_URL)
    with patch(
        "lfx_bundles.jsonify.jsonify_dataset.ssrf_safe_httpx_get",
        side_effect=SSRFProtectionError("blocked"),
    ):
        result = component._run_for_tool()
    assert result.startswith("Error reading Jsonify dataset")

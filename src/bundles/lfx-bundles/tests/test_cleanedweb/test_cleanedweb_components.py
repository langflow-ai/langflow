"""Unit tests for the CleanedWeb extension bundle (``lfx-bundles[cleanedweb]``).

The components build a ``cleanedweb.CleanedWeb`` client through ``make_client``;
the tests patch it with a fake client, so no network access is required.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from cleanedweb.exceptions import AuthenticationError
from lfx_bundles.cleanedweb import CleanedWebFindAPIComponent, CleanedWebRunAPIComponent

FIND_CLIENT = "lfx_bundles.cleanedweb.cleanedweb_find_api.make_client"
RUN_CLIENT = "lfx_bundles.cleanedweb.cleanedweb_run_api.make_client"

API = SimpleNamespace(
    api_id="api_1",
    slug="rubygems-gem-search",
    name="RubyGems Gem Search",
    site_domain="rubygems.org",
    site_name="RubyGems",
    category="public_data",
    description="Ruby gems matching a search.",
    key_fields=["title", "url"],
    endpoints=[SimpleNamespace(endpoint_id="ep_search", name="Search", description="Search gems.")],
)
CONTRACT = SimpleNamespace(
    api_id="api_1",
    endpoints=[
        SimpleNamespace(
            endpoint_id="ep_search",
            input_schema={
                "properties": {"search": {"type": "string", "description": "Search text."}, "sort": {"type": "string"}},
                "required": ["search"],
            },
        )
    ],
)


def _result(records, *, complete=True, usable=True):
    return SimpleNamespace(
        records=records,
        complete=complete,
        is_usable=usable,
        idempotency_key="key-1",
        stop_reason=None if usable else "time_budget",
        summary={"status": "completed" if usable else "partial"},
    )


def _client(**catalog_methods) -> MagicMock:
    client = MagicMock()
    client.__enter__.return_value = client
    for name, value in catalog_methods.items():
        setattr(client.catalog, name, value)
    return client


# --- Find API ---------------------------------------------------------------------------------


def test_find_requires_query_or_site():
    with patch(FIND_CLIENT) as make_client:
        rows = CleanedWebFindAPIComponent(query="", site="").fetch_content()
    make_client.assert_not_called()
    assert "Set a Query or a Site" in rows[0].data["error"]


def test_find_maps_apis_with_endpoint_inputs():
    client = _client(find=MagicMock(return_value=[API]), get=MagicMock(return_value=CONTRACT))
    with patch(FIND_CLIENT, return_value=client) as make_client:
        rows = CleanedWebFindAPIComponent(query="gems", site="rubygems.org", limit=3).fetch_content()
    make_client.assert_called_once_with()  # catalog reads send no key
    client.catalog.find.assert_called_once_with(q="gems", site="rubygems.org", limit=3)
    client.catalog.get.assert_called_once_with("rubygems-gem-search")
    data = rows[0].data
    assert (data["api_id"], data["slug"], data["site"]) == ("api_1", "rubygems-gem-search", "rubygems.org")
    assert data["key_fields"] == "title, url"
    endpoint = json.loads(data["endpoints"])[0]
    assert endpoint["endpoint_id"] == "ep_search"
    assert endpoint["inputs"] == {"search": "string, required - Search text.", "sort": "string"}


def test_find_without_inputs_skips_contracts():
    client = _client(find=MagicMock(return_value=[API]), get=MagicMock())
    with patch(FIND_CLIENT, return_value=client):
        rows = CleanedWebFindAPIComponent(query="gems", include_inputs=False).fetch_content()
    client.catalog.get.assert_not_called()
    assert "inputs" not in json.loads(rows[0].data["endpoints"])[0]


def test_find_limit_is_clamped():
    client = _client(find=MagicMock(return_value=[]))
    with patch(FIND_CLIENT, return_value=client):
        CleanedWebFindAPIComponent(query="gems", limit=500).fetch_content()
    assert client.catalog.find.call_args.kwargs["limit"] == 20


def test_find_error_becomes_error_row():
    client = _client(find=MagicMock(side_effect=OSError("network down")))
    with patch(FIND_CLIENT, return_value=client):
        rows = CleanedWebFindAPIComponent(query="gems").fetch_content()
    assert rows[0].data["error"] == "network down"


# --- Run API ----------------------------------------------------------------------------------


@pytest.fixture
def run_component() -> CleanedWebRunAPIComponent:
    return CleanedWebRunAPIComponent(
        api="rubygems-gem-search",
        endpoint_id="",
        run_input='{"search": "http"}',
        max_items=5,
        api_key="test-key",  # pragma: allowlist secret
    )


def test_run_requires_api_key(run_component):
    run_component.api_key = ""
    with patch(RUN_CLIENT) as make_client:
        rows = run_component.fetch_content()
    make_client.assert_not_called()
    assert "API key is required" in rows[0].data["error"]


def test_run_resolves_slug_and_first_endpoint(run_component):
    records = [{"title": "httparty", "url": "https://rubygems.org/gems/httparty"}]
    client = _client(get=MagicMock(return_value=CONTRACT), run=MagicMock(return_value=_result(records)))
    with patch(RUN_CLIENT, return_value=client) as make_client:
        frame = run_component.cleanedweb_run_api()
    make_client.assert_called_once_with("test-key")
    client.catalog.run.assert_called_once_with("api_1", "ep_search", {"search": "http"}, max_items=5)
    assert len(frame) == 1
    assert frame.iloc[0]["title"] == "httparty"


def test_run_uses_given_endpoint_and_clamps_max_items(run_component):
    run_component.endpoint_id = "ep_other"
    run_component.max_items = 0
    client = _client(get=MagicMock(return_value=CONTRACT), run=MagicMock(return_value=_result([])))
    with patch(RUN_CLIENT, return_value=client):
        run_component.fetch_content()
    assert client.catalog.run.call_args.args[1] == "ep_other"
    assert client.catalog.run.call_args.kwargs["max_items"] == 1


def test_run_rejects_non_object_input(run_component):
    run_component.run_input = "[1, 2]"
    with patch(RUN_CLIENT, return_value=_client(get=MagicMock(return_value=CONTRACT))):
        rows = run_component.fetch_content()
    assert "must be a JSON object" in rows[0].data["error"]


def test_run_surfaces_api_error(run_component):
    error = AuthenticationError("Unauthorized", status_code=401)
    client = _client(get=MagicMock(return_value=CONTRACT), run=MagicMock(side_effect=error))
    with patch(RUN_CLIENT, return_value=client):
        rows = run_component.fetch_content()
    assert rows[0].data["error"] == "CleanedWeb error: HTTP 401: Unauthorized"


def test_run_incomplete_reports_idempotency_key(run_component):
    client = _client(get=MagicMock(return_value=CONTRACT), run=MagicMock(return_value=_result([], complete=False)))
    with patch(RUN_CLIENT, return_value=client):
        rows = run_component.fetch_content()
    assert "key-1" in rows[0].data["error"]


def test_tool_names_are_provider_specific():
    find_tools = asyncio.run(CleanedWebFindAPIComponent().to_toolkit())
    run_tools = asyncio.run(CleanedWebRunAPIComponent(api_key="test-key").to_toolkit())  # pragma: allowlist secret
    assert [t.name for t in find_tools] == ["cleanedweb_find_api"]
    assert [t.name for t in run_tools] == ["cleanedweb_run_api"]

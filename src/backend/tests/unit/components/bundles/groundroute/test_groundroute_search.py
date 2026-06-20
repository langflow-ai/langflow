"""Unit tests for the GroundRoute Search bundle component (Langflow core bundle).

Uses the mandatory base class + 3 fixtures per Langflow's contributing-component-tests docs
(verified against src/backend/tests/base.py on main, 2026-06-20):
  component_class, default_kwargs (incl. _session_id), file_names_mapping ([] for a new component).
The base runs the latest-version + version-mapping checks; the two methods below add Arrange/Act/Assert
coverage of the result mapping and the graceful-error path (httpx mocked, no network).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from lfx.components.groundroute.groundroute_search import GroundRouteSearchComponent

from tests.base import ComponentTestBaseWithoutClient


class TestGroundRouteSearchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        return GroundRouteSearchComponent

    @pytest.fixture
    def default_kwargs(self) -> dict[str, Any]:
        return {
            "api_key": "gr_live_test_key",
            "query": "vector databases",
            "mode": "auto",
            "max_results": 10,
            "_session_id": "test-session",
        }

    @pytest.fixture
    def file_names_mapping(self) -> list:
        # New component: no previously released versions to map.
        return []

    def test_search_data_maps_results_with_source_engine(
        self, component_class: type[Any], default_kwargs: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange: a captured /v1/search 200 body (matches the gateway SearchResponse contract).
        component = component_class(**default_kwargs)
        sample = {
            "request_id": "r1",
            "results": [
                {"url": "https://ex.com/a", "title": "A", "snippet": "s", "source_engine": "serper"},
                {"url": "https://ex.com/b", "title": "B", "snippet": "s2", "source_engine": "exa"},
            ],
            "answer": None,
            "citations": [],
            "degraded": False,
            "routing_meta": {"chosen_engine": "serper", "cost_usd": 0.001},
            "cache_meta": {"cache_tier": "miss"},
            "usage_meta": {"cost_usd": 0.001},
        }

        class _Resp:
            status_code = 200
            text = "ok"

            def json(self) -> dict[str, Any]:
                return sample

        monkeypatch.setattr(httpx, "post", lambda *_a, **_k: _Resp())

        # Act
        data = component.search_data()

        # Assert: one Data per result, each carrying its source_engine.
        assert len(data) == 2
        assert {d.data["source_engine"] for d in data} == {"serper", "exa"}

    def test_missing_key_returns_error_not_crash(self, component_class: type[Any]) -> None:
        # Arrange / Act: no API key supplied.
        component = component_class(api_key="", query="x", _session_id="s")
        out = component.search_data()
        # Assert: graceful error Data, never an exception.
        assert "error" in out[0].data

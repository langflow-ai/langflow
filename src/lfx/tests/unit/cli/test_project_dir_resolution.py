"""A served or run flow can resolve its sibling flows from the folder it came from.

``lfx serve <dir>`` and ``lfx run <dir>/flow.json`` load flows off disk with no database
behind them, so Run Flow had no way to find the other flows in the same folder. The folder
it was loaded from is recorded on ``graph.context['project_dir']`` and Run Flow resolves
siblings out of it before falling back to the database lookup langflow provides.
"""

import json
from types import SimpleNamespace

import pytest
from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.cli.serve_app import FlowRegistry
from lfx.graph.graph.base import Graph

FLOW = {"id": "11111111-1111-1111-1111-111111111111", "name": "search-docs", "data": {"nodes": [], "edges": []}}


def _write(directory, stem, payload):
    path = directory / f"{stem}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestRegistryStampsProjectDir:
    def test_stamp_records_the_directory(self, tmp_path):
        registry = FlowRegistry(project_dir=tmp_path)
        graph = Graph()

        registry.stamp(graph)

        assert graph.context["project_dir"] == str(tmp_path)

    def test_stamp_leaves_context_alone_without_a_directory(self):
        """A registry built from individual files has no folder to resolve against."""
        registry = FlowRegistry()
        graph = Graph()

        registry.stamp(graph)

        assert "project_dir" not in graph.context

    def test_stamp_is_idempotent_across_deepcopy_reapplication(self, tmp_path):
        """``stamp`` is called again after deepcopy, so it must be safe to repeat."""
        registry = FlowRegistry(project_dir=tmp_path)
        graph = Graph()

        registry.stamp(graph)
        registry.stamp(graph)

        assert graph.context["project_dir"] == str(tmp_path)


class TestSiblingFlowResolution:
    @pytest.fixture
    def component_in(self):
        def _make(directory):
            component = RunFlowBaseComponent()
            graph = Graph()
            if directory is not None:
                graph.context["project_dir"] = str(directory)
            # Component.graph reads through self._vertex.graph.
            component._vertex = SimpleNamespace(graph=graph)
            return component

        return _make

    def test_resolves_a_sibling_by_file_stem(self, tmp_path, component_in):
        _write(tmp_path, "search-docs", FLOW)

        found = component_in(tmp_path)._sibling_flow("search-docs", None)

        assert found is not None
        assert found.data["name"] == "search-docs"

    def test_resolves_a_sibling_by_flow_name_when_the_filename_differs(self, tmp_path, component_in):
        """Exports sanitise the filename, so the stem and the flow's own name can diverge."""
        _write(tmp_path, "search_docs_sanitised", FLOW)

        found = component_in(tmp_path)._sibling_flow("search-docs", None)

        assert found is not None
        assert found.data["id"] == FLOW["id"]

    def test_resolves_a_sibling_by_flow_id(self, tmp_path, component_in):
        _write(tmp_path, "whatever", FLOW)

        found = component_in(tmp_path)._sibling_flow(None, FLOW["id"])

        assert found is not None
        assert found.data["name"] == "search-docs"

    def test_returns_none_when_the_flow_is_not_in_the_folder(self, tmp_path, component_in):
        _write(tmp_path, "search-docs", FLOW)

        assert component_in(tmp_path)._sibling_flow("absent", None) is None

    def test_returns_none_without_a_project_dir(self, tmp_path, component_in):
        """No folder context means the database lookup is the only path, as it is in langflow."""
        _write(tmp_path, "search-docs", FLOW)

        assert component_in(None)._sibling_flow("search-docs", None) is None

    def test_a_flow_name_cannot_reach_outside_the_folder(self, tmp_path, component_in):
        """A flow name is data, so it must not be able to read a file elsewhere on disk."""
        outside = tmp_path / "outside"
        outside.mkdir()
        _write(outside, "secrets", FLOW)
        served = tmp_path / "served"
        served.mkdir()

        assert component_in(served)._sibling_flow("../outside/secrets", None) is None

    def test_ignores_a_corrupt_sibling_rather_than_failing_the_run(self, tmp_path, component_in):
        (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
        _write(tmp_path, "search-docs", FLOW)

        found = component_in(tmp_path)._sibling_flow("search-docs", None)

        assert found is not None


class TestServePathRecordsTheFolder:
    """The wiring, exercised through the real registry builder rather than the class alone."""

    def test_build_registry_from_directory_stamps_every_graph(self, tmp_path):
        import asyncio
        from pathlib import Path

        from lfx.cli.commands import build_registry_from_directory

        # A real shipped flow, so this exercises the actual loader rather than a hand-made payload.
        # A real shipped flow, so this exercises the actual loader rather than a hand-made payload.
        fixture = Path(__file__).parents[2] / "data" / "LoopTest.json"
        (tmp_path / "solo.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

        registry = asyncio.run(build_registry_from_directory(tmp_path, lambda _: None, check_variables=False))

        assert len(registry) >= 1
        graph, _meta = next(iter(registry._flows.values()))
        assert graph.context["project_dir"] == str(tmp_path)

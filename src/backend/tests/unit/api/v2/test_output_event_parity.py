"""Sync/stream parity for per-component outputs.

The ``langflow`` stream emits one ``output`` event per terminal output carrying
the same ``ComponentOutput`` shape sync returns in ``outputs[id]``. These tests
pin (a) the authoritative metadata the v1 build path ships on ``end_vertex``,
(b) the adapter emitting ``output`` only for terminals, and (c) builder parity —
the two result-data forms pass through one builder to the same output. (Real-run
``content`` is each mode's own serialization; see the e2e shape test in
``test_workflow_agui.py``.)
"""

from __future__ import annotations

import json
from unittest.mock import Mock

from langflow.api.build import _output_meta_for_vertex
from lfx.workflow.adapters import StreamAdapterContext
from lfx.workflow.adapters.langflow import LangflowAdapter
from lfx.workflow.converters import build_component_output, resolve_output_type


def _adapter() -> LangflowAdapter:
    return LangflowAdapter(StreamAdapterContext(run_id="run-1", thread_id="thread-1"))


def _end_vertex_data(component_id: str, text: str, *, is_terminal: bool = True, is_output: bool = True) -> dict:
    return {
        "build_data": {"id": component_id, "valid": True, "data": {"outputs": {"message": {"message": text}}}},
        "output_meta": {
            "component_id": component_id,
            "display_name": "Chat Output",
            "vertex_type": "ChatOutput",
            "is_output": is_output,
            "is_terminal": is_terminal,
            "output_types": ["Message"],
        },
    }


def _result_object(text: str) -> Mock:
    """Sync-side result data: an object whose ``.outputs`` mirrors the stream dict's ``outputs``."""
    rd = Mock()
    rd.outputs = {"message": {"message": text}}
    rd.metadata = {}
    return rd


def _vertex(vertex_id: str, *, is_output: bool = True, display_name: str = "Chat Output") -> Mock:
    vertex = Mock()
    vertex.id = vertex_id
    vertex.display_name = display_name
    vertex.vertex_type = "ChatOutput"
    vertex.is_output = is_output
    vertex.outputs = [{"types": ["Message"]}]
    return vertex


def _graph(vertices: list[Mock], terminal_ids: list[str]) -> Mock:
    graph = Mock()
    graph.vertices = vertices
    by_id = {v.id: v for v in vertices}
    graph.get_vertex = Mock(side_effect=lambda vid: by_id[vid])
    graph.get_terminal_nodes = Mock(return_value=terminal_ids)
    return graph


class TestOutputMetaForVertex:
    """The v1 build path ships authoritative vertex metadata as an additive key."""

    def test_carries_authoritative_vertex_facts(self):
        v = _vertex("ChatOutput-abc")
        graph = _graph([v], terminal_ids=["ChatOutput-abc"])

        meta = _output_meta_for_vertex(graph, "ChatOutput-abc")

        assert meta["component_id"] == "ChatOutput-abc"
        assert meta["display_name"] == "Chat Output"
        assert meta["vertex_type"] == "ChatOutput"
        assert meta["is_output"] is True
        assert meta["is_terminal"] is True
        assert meta["output_types"] == ["Message"]

    def test_non_terminal_vertex_marked_not_terminal(self):
        a = _vertex("ChatOutput-a")
        b = _vertex("LLM-b", is_output=False, display_name="LLM")
        graph = _graph([a, b], terminal_ids=["ChatOutput-a"])

        meta = _output_meta_for_vertex(graph, "LLM-b")
        assert meta["is_terminal"] is False


class TestLangflowAdapterOutputEvent:
    """On a terminal end_vertex, the adapter ALSO emits a normalized ``output`` event."""

    def test_terminal_end_vertex_adds_output_event(self):
        events = list(_adapter().translate("end_vertex", _end_vertex_data("ChatOutput-abc", "Hi there!")))
        types = [e.type for e in events]
        # The raw end_vertex passthrough is preserved AND an output event is added.
        assert "end_vertex" in types
        assert "output" in types

        output = next(e for e in events if e.type == "output")
        payload = json.loads(output.data_json)
        assert payload["event"] == "output"
        data = payload["data"]
        assert data["component_id"] == "ChatOutput-abc"
        assert data["type"] == "message"
        assert data["display_name"] == "Chat Output"
        assert data["content"] == "Hi there!"
        assert data["status"] == "completed"

    def test_non_terminal_end_vertex_is_passthrough_only(self):
        events = list(
            _adapter().translate("end_vertex", _end_vertex_data("LLM-b", "x", is_terminal=False, is_output=False))
        )
        assert [e.type for e in events] == ["end_vertex"]

    def test_other_events_unchanged(self):
        events = list(_adapter().translate("token", {"id": "m1", "chunk": "Hi"}))
        assert [e.type for e in events] == ["token"]
        assert json.loads(events[0].data_json) == {"event": "token", "data": {"id": "m1", "chunk": "Hi"}}


class TestSyncStreamParity:
    """Builder parity: equivalent result data (object form vs dict form) builds the same output.

    Proves there is NO per-mode logic divergence — the sync ``ResultData`` object and the
    stream ``VertexBuildResponse.data`` dict pass through the SAME ``build_component_output``
    to the same ``ComponentOutput``. (When real runs differ, it's because the framework puts
    different data in the two sources, not because this code diverges — see the e2e shape test.)
    """

    def test_object_and_dict_result_data_build_identical_output(self):
        component_id = "ChatOutput-abc"

        # Sync side builds from an OBJECT result_data (RunResponse ResultData form).
        sync_output = build_component_output(
            component_id=component_id,
            is_output=True,
            vertex_type="ChatOutput",
            output_type=resolve_output_type(["Message"], "ChatOutput"),
            display_name="Chat Output",
            result_data=_result_object("Hi there!"),
        )

        # Stream side builds from the DICT event (VertexBuildResponse.data form).
        output = next(
            e
            for e in _adapter().translate("end_vertex", _end_vertex_data(component_id, "Hi there!"))
            if e.type == "output"
        )
        stream_data = json.loads(output.data_json)["data"]

        # Identical, except component_id (which sync carries as the dict key).
        assert {k: v for k, v in stream_data.items() if k != "component_id"} == sync_output.model_dump(mode="json")
        assert stream_data["component_id"] == component_id

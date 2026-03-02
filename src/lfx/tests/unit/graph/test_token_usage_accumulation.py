"""Tests for Vertex._accumulate_upstream_token_usage() and _extract_token_usage()."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from lfx.graph.schema import ResultData
from lfx.graph.vertex.base import Vertex


def _make_edge(source_id: str, target_id: str):
    """Create a lightweight edge stub with source_id and target_id."""
    return SimpleNamespace(source_id=source_id, target_id=target_id)


def _make_vertex_stub(
    vertex_id: str,
    *,
    is_output: bool = False,
    token_usage: dict | None = None,
    own_token_usage: dict | None = None,
):
    """Create a lightweight stub that behaves like a Vertex for accumulation tests."""
    stub = MagicMock(spec=Vertex)
    stub.id = vertex_id
    stub.is_output = is_output

    if token_usage is not None:
        stub.result = ResultData(token_usage=token_usage)
    else:
        stub.result = None

    if own_token_usage is not None:
        stub.custom_component = SimpleNamespace(_token_usage=own_token_usage)
    else:
        stub.custom_component = None

    return stub


def _wire_graph(output: MagicMock, vertices: dict[str, MagicMock], edges: list):
    """Wire a mock graph with edges and vertex_map, and bind real traversal methods."""
    graph = MagicMock()
    graph.edges = edges
    graph.get_vertex = lambda vid: vertices[vid]
    output.graph = graph
    # Bind real methods so they work on the mock
    output._get_all_upstream_vertices = lambda: Vertex._get_all_upstream_vertices(output)
    output._accumulate_upstream_token_usage = lambda: Vertex._accumulate_upstream_token_usage(output)


class TestAccumulateUpstreamTokenUsage:
    """Tests for Vertex._accumulate_upstream_token_usage()."""

    def test_single_llm_upstream(self):
        """Single LLM predecessor: returns that LLM's token usage."""
        llm = _make_vertex_stub(
            "LLM-1",
            token_usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        output = _make_vertex_stub("ChatOutput-1", is_output=True)
        _wire_graph(output, {"LLM-1": llm}, [_make_edge("LLM-1", "ChatOutput-1")])

        result = output._accumulate_upstream_token_usage()

        assert result is not None
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150

    def test_two_serial_llms(self):
        """LLM1 → LLM2 → ChatOutput: returns accumulated total from both."""
        llm1 = _make_vertex_stub(
            "LLM-1",
            token_usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        llm2 = _make_vertex_stub(
            "LLM-2",
            token_usage={"input_tokens": 200, "output_tokens": 80, "total_tokens": 280},
        )
        output = _make_vertex_stub("ChatOutput-1", is_output=True)
        edges = [_make_edge("LLM-1", "LLM-2"), _make_edge("LLM-2", "ChatOutput-1")]
        _wire_graph(output, {"LLM-1": llm1, "LLM-2": llm2}, edges)

        result = output._accumulate_upstream_token_usage()

        assert result is not None
        assert result["input_tokens"] == 300
        assert result["output_tokens"] == 130
        assert result["total_tokens"] == 430

    def test_no_llms_upstream(self):
        """No predecessors with token usage: returns None."""
        prompt = _make_vertex_stub("Prompt-1")
        output = _make_vertex_stub("ChatOutput-1", is_output=True)
        _wire_graph(output, {"Prompt-1": prompt}, [_make_edge("Prompt-1", "ChatOutput-1")])

        result = output._accumulate_upstream_token_usage()

        assert result is None

    def test_no_predecessors(self):
        """No predecessors at all: returns None."""
        output = _make_vertex_stub("ChatOutput-1", is_output=True)
        _wire_graph(output, {}, [])

        result = output._accumulate_upstream_token_usage()

        assert result is None

    def test_diamond_pattern_deduplication(self):
        """Diamond: LLM feeds into two branches that merge at ChatOutput, counted once."""
        llm = _make_vertex_stub(
            "LLM-1",
            token_usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        branch_a = _make_vertex_stub("BranchA-1")
        branch_b = _make_vertex_stub("BranchB-1")
        output = _make_vertex_stub("ChatOutput-1", is_output=True)
        edges = [
            _make_edge("LLM-1", "BranchA-1"),
            _make_edge("LLM-1", "BranchB-1"),
            _make_edge("BranchA-1", "ChatOutput-1"),
            _make_edge("BranchB-1", "ChatOutput-1"),
        ]
        _wire_graph(output, {"LLM-1": llm, "BranchA-1": branch_a, "BranchB-1": branch_b}, edges)

        result = output._accumulate_upstream_token_usage()

        assert result is not None
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150

    def test_includes_own_token_usage(self):
        """Output vertex with its own _token_usage includes it in the total."""
        llm = _make_vertex_stub(
            "LLM-1",
            token_usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        output = _make_vertex_stub(
            "ChatOutput-1",
            is_output=True,
            own_token_usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )
        _wire_graph(output, {"LLM-1": llm}, [_make_edge("LLM-1", "ChatOutput-1")])

        result = output._accumulate_upstream_token_usage()

        assert result is not None
        assert result["input_tokens"] == 110
        assert result["output_tokens"] == 55
        assert result["total_tokens"] == 165

    def test_mixed_predecessors_with_and_without_tokens(self):
        """Only predecessors with token_usage contribute; others are skipped."""
        llm = _make_vertex_stub(
            "LLM-1",
            token_usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        prompt = _make_vertex_stub("Prompt-1")
        output = _make_vertex_stub("ChatOutput-1", is_output=True)
        edges = [_make_edge("Prompt-1", "LLM-1"), _make_edge("LLM-1", "ChatOutput-1")]
        _wire_graph(output, {"Prompt-1": prompt, "LLM-1": llm}, edges)

        result = output._accumulate_upstream_token_usage()

        assert result is not None
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150

    def test_predecessor_with_result_but_no_token_usage(self):
        """Predecessor has a result but token_usage is None: skipped."""
        predecessor = _make_vertex_stub("SomeComponent-1")
        predecessor.result = ResultData(token_usage=None)
        output = _make_vertex_stub("ChatOutput-1", is_output=True)
        _wire_graph(output, {"SomeComponent-1": predecessor}, [_make_edge("SomeComponent-1", "ChatOutput-1")])

        result = output._accumulate_upstream_token_usage()

        assert result is None

    def test_handles_none_values_in_token_dict(self):
        """Token usage dict with None values treated as 0."""
        llm = _make_vertex_stub(
            "LLM-1",
            token_usage={"input_tokens": None, "output_tokens": 50, "total_tokens": None},
        )
        output = _make_vertex_stub("ChatOutput-1", is_output=True)
        _wire_graph(output, {"LLM-1": llm}, [_make_edge("LLM-1", "ChatOutput-1")])

        result = output._accumulate_upstream_token_usage()

        assert result is not None
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 50


class TestExtractTokenUsage:
    """Tests for Vertex._extract_token_usage() dispatch logic."""

    def test_output_vertex_returns_none(self):
        """Output vertex returns None (tokens shown on chat message instead)."""
        llm = _make_vertex_stub(
            "LLM-1",
            token_usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )
        output = _make_vertex_stub("ChatOutput-1", is_output=True)
        _wire_graph(output, {"LLM-1": llm}, [_make_edge("LLM-1", "ChatOutput-1")])

        result = Vertex._extract_token_usage(output)

        assert result is None

    def test_non_output_vertex_returns_own_usage(self):
        """Non-output vertex returns its own component's _token_usage."""
        llm = _make_vertex_stub(
            "LLM-1",
            is_output=False,
            own_token_usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )

        result = Vertex._extract_token_usage(llm)

        assert result is not None
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150

    def test_non_output_vertex_without_usage_returns_none(self):
        """Non-output vertex with no _token_usage returns None."""
        vertex = _make_vertex_stub("Prompt-1", is_output=False)

        result = Vertex._extract_token_usage(vertex)

        assert result is None

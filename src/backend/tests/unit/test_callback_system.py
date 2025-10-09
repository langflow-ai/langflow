"""Test the callback-based logging system for Graph execution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from langflow.graph.log_collector import (
    TransactionCollector,
    VertexBuildCollector,
    create_log_callbacks,
)
from lfx.graph.vertex.base import Vertex


class TestTransactionCollector:
    """Test the TransactionCollector class."""

    def test_collect_transaction(self):
        """Test collecting transactions."""
        collector = TransactionCollector()

        # Create mock vertices
        source = MagicMock(spec=Vertex)
        source.id = "source-vertex"
        target = MagicMock(spec=Vertex)
        target.id = "target-vertex"

        # Collect a transaction
        collector.collect_transaction(
            flow_id="test-flow-id",
            source=source,
            status="success",
            target=target,
            error=None,
        )

        # Verify transaction was collected
        assert len(collector.transactions) == 1
        transaction = collector.transactions[0]
        assert transaction[0] == "test-flow-id"
        assert transaction[1] == source
        assert transaction[2] == "success"
        assert transaction[3] == target
        assert transaction[4] is None

    def test_collect_multiple_transactions(self):
        """Test collecting multiple transactions."""
        collector = TransactionCollector()

        source1 = MagicMock(spec=Vertex)
        source2 = MagicMock(spec=Vertex)

        # Collect multiple transactions
        collector.collect_transaction("flow1", source1, "success", None, None)
        collector.collect_transaction("flow2", source2, "error", None, "Test error")

        assert len(collector.transactions) == 2

    def test_get_and_clear(self):
        """Test getting and clearing collected transactions."""
        collector = TransactionCollector()

        source = MagicMock(spec=Vertex)

        # Collect transactions
        collector.collect_transaction("flow1", source, "success", None, None)
        collector.collect_transaction("flow2", source, "error", None, "Error")

        # Get and clear
        transactions = collector.get_and_clear()

        # Verify we got the transactions
        assert len(transactions) == 2

        # Verify collector is now empty
        assert len(collector.transactions) == 0

        # Get again should return empty list
        transactions2 = collector.get_and_clear()
        assert len(transactions2) == 0

    def test_transaction_with_uuid(self):
        """Test collecting transaction with UUID flow_id."""
        collector = TransactionCollector()

        source = MagicMock(spec=Vertex)
        flow_uuid = UUID("12345678-1234-5678-1234-567812345678")

        collector.collect_transaction(flow_uuid, source, "success", None, None)

        assert len(collector.transactions) == 1
        assert collector.transactions[0][0] == flow_uuid


class TestVertexBuildCollector:
    """Test the VertexBuildCollector class."""

    def test_collect_vertex_build(self):
        """Test collecting vertex builds."""
        collector = VertexBuildCollector()

        # Collect a vertex build
        collector.collect_vertex_build(
            flow_id="test-flow",
            vertex_id="vertex-1",
            valid=True,
            params={"param1": "value1"},
            result_dict={"result": "data"},
            artifacts={"artifact": "value"},
        )

        # Verify build was collected
        assert len(collector.builds) == 1
        build = collector.builds[0]
        assert build[0] == "test-flow"
        assert build[1] == "vertex-1"
        assert build[2] is True
        assert build[3] == {"param1": "value1"}
        assert build[4] == {"result": "data"}
        assert build[5] == {"artifact": "value"}

    def test_collect_build_without_artifacts(self):
        """Test collecting vertex build without artifacts."""
        collector = VertexBuildCollector()

        collector.collect_vertex_build(
            flow_id="test-flow",
            vertex_id="vertex-1",
            valid=False,
            params={},
            result_dict={},
        )

        assert len(collector.builds) == 1
        assert collector.builds[0][5] is None  # artifacts should be None

    def test_get_and_clear(self):
        """Test getting and clearing collected builds."""
        collector = VertexBuildCollector()

        # Collect builds
        collector.collect_vertex_build(
            flow_id="flow1",
            vertex_id="v1",
            valid=True,
            params={},
            result_dict={},
        )
        collector.collect_vertex_build(
            flow_id="flow2",
            vertex_id="v2",
            valid=False,
            params={},
            result_dict={},
        )

        # Get and clear
        builds = collector.get_and_clear()

        # Verify we got the builds
        assert len(builds) == 2

        # Verify collector is now empty
        assert len(collector.builds) == 0

        # Get again should return empty list
        builds2 = collector.get_and_clear()
        assert len(builds2) == 0


class TestCreateLogCallbacks:
    """Test the create_log_callbacks factory function."""

    def test_create_log_callbacks(self):
        """Test creating log callbacks with collectors."""
        callbacks, transaction_collector, vertex_build_collector = create_log_callbacks()

        # Verify we got all three objects
        assert callbacks is not None
        assert transaction_collector is not None
        assert vertex_build_collector is not None

        # Verify callbacks are wired correctly
        assert callbacks.transaction == transaction_collector.collect_transaction
        assert callbacks.vertex_build == vertex_build_collector.collect_vertex_build

        # Test that callbacks work
        source = MagicMock(spec=Vertex)
        callbacks.transaction("flow", source, "success", None, None)
        assert len(transaction_collector.transactions) == 1

        callbacks.vertex_build("flow", "vertex", valid=True, params={}, result_dict={})
        assert len(vertex_build_collector.builds) == 1


class TestGraphIntegration:
    """Test Graph integration with callbacks."""

    @pytest.mark.asyncio
    async def test_graph_with_callbacks(self):
        """Test that Graph properly uses callbacks when provided."""
        from lfx.graph.graph.base import Graph

        # Create callbacks and collectors
        callbacks, _transaction_collector, _vertex_build_collector = create_log_callbacks()

        # Create an empty graph with callbacks
        graph = Graph(log_callbacks=callbacks)

        # Set flow_id for testing
        graph.flow_id = "test-flow-123"

        # Verify callbacks are set
        assert graph.log_callbacks is not None
        assert graph.log_callbacks.transaction is not None
        assert graph.log_callbacks.vertex_build is not None

    @pytest.mark.asyncio
    async def test_graph_without_callbacks(self):
        """Test that Graph works without callbacks."""
        from lfx.graph.graph.base import Graph

        # Create an empty graph without callbacks
        graph = Graph()

        # Set flow_id for testing
        graph.flow_id = "test-flow"

        # Verify no callbacks are set
        assert graph.log_callbacks is None


class TestEndpointIntegration:
    """Test endpoint integration with callbacks."""

    @pytest.mark.asyncio
    async def test_run_graph_internal_with_collectors(self):
        """Test run_graph_internal with log callbacks."""
        from langflow.graph.log_collector import create_log_callbacks
        from langflow.processing.process import run_graph_internal

        # Create mock graph
        mock_graph = MagicMock()
        mock_graph.arun = AsyncMock(return_value=[])
        mock_graph.session_id = "test-session"

        # Create callbacks and collectors
        callbacks, transaction_collector, vertex_build_collector = create_log_callbacks()

        # Add some test data to collectors
        source = MagicMock(spec=Vertex)
        transaction_collector.collect_transaction("flow", source, "success", None, None)
        vertex_build_collector.collect_vertex_build("flow", "vertex", valid=True, params={}, result_dict={})

        # Set log_callbacks on the graph (this is how run_graph_internal passes them)
        mock_graph.log_callbacks = callbacks

        # Run graph
        _outputs, _session_id = await run_graph_internal(
            graph=mock_graph,
            flow_id="test-flow",
            stream=False,
            session_id="test-session",
        )

        # Collectors keep their data - they're not automatically cleared by run_graph_internal
        # The collectors' data would be processed by queue services in the real system
        assert len(transaction_collector.transactions) == 1
        assert len(vertex_build_collector.builds) == 1

        # Manual clear to verify data was there
        transactions = transaction_collector.get_and_clear()
        builds = vertex_build_collector.get_and_clear()
        assert len(transactions) == 1
        assert len(builds) == 1

    @pytest.mark.asyncio
    async def test_run_graph_internal_without_collectors(self):
        """Test run_graph_internal without collectors."""
        from langflow.processing.process import run_graph_internal

        # Create mock graph
        mock_graph = MagicMock()
        mock_graph.arun = AsyncMock(return_value=[])
        mock_graph.session_id = "test-session"

        # Run graph without collectors
        _outputs, _session_id = await run_graph_internal(
            graph=mock_graph,
            flow_id="test-flow",
            stream=False,
        )

        # Without collectors, run_graph_internal just returns outputs and session_id
        # No transaction or build data is collected


class TestBatchProcessing:
    """Test batch processing of collected data."""

    def test_batch_collection(self):
        """Test that collectors can handle batch collection."""
        transaction_collector = TransactionCollector()
        vertex_build_collector = VertexBuildCollector()

        # Simulate batch collection (like during graph execution)
        for i in range(100):
            source = MagicMock(spec=Vertex)
            source.id = f"vertex-{i}"

            transaction_collector.collect_transaction(
                flow_id=f"flow-{i % 10}",
                source=source,
                status="success" if i % 2 == 0 else "error",
                target=None,
                error=None if i % 2 == 0 else f"Error {i}",
            )

            vertex_build_collector.collect_vertex_build(
                flow_id=f"flow-{i % 10}",
                vertex_id=f"vertex-{i}",
                valid=i % 3 != 0,
                params={"index": i},
                result_dict={"result": f"data-{i}"},
            )

        # Verify all data was collected
        assert len(transaction_collector.transactions) == 100
        assert len(vertex_build_collector.builds) == 100

        # Get all data in one batch
        transactions = transaction_collector.get_and_clear()
        builds = vertex_build_collector.get_and_clear()

        assert len(transactions) == 100
        assert len(builds) == 100

        # Verify collectors are empty
        assert len(transaction_collector.transactions) == 0
        assert len(vertex_build_collector.builds) == 0


class TestCallbackProtocols:
    """Test that callback protocols work correctly."""

    def test_callback_protocol_compatibility(self):
        """Test that our callbacks match the expected protocol."""
        from lfx.graph.callbacks import LogCallbacks

        # Create mock callbacks that match the protocol
        mock_transaction_callback = MagicMock()
        mock_vertex_build_callback = MagicMock()

        # Create LogCallbacks instance
        callbacks = LogCallbacks(
            transaction_callback=mock_transaction_callback,
            vertex_build_callback=mock_vertex_build_callback,
        )

        # Test transaction callback
        source = MagicMock(spec=Vertex)
        callbacks.transaction("flow", source, "status", None, None)
        mock_transaction_callback.assert_called_once_with("flow", source, "status", None, None)

        # Test vertex build callback
        callbacks.vertex_build("flow", "vertex", valid=True, params={}, result_dict={})
        mock_vertex_build_callback.assert_called_once_with("flow", "vertex", valid=True, params={}, result_dict={})

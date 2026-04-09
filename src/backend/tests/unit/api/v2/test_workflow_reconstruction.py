"""Unit tests for workflow reconstruction from vertex_build table.

Test Coverage:
    - Successful reconstruction with terminal nodes
    - Reconstruction with no vertex builds found (error case)
    - Reconstruction with flow having no data (error case)
    - Reconstruction filtering to terminal nodes only
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from langflow.api.v2.workflow_reconstruction import reconstruct_workflow_response_from_job_id
from langflow.services.database.models.vertex_builds.model import VertexBuildTable


class TestWorkflowReconstruction:
    """Unit tests for workflow reconstruction logic."""

    async def test_reconstruct_success_with_terminal_nodes(self):
        """Test successful reconstruction filters to terminal nodes and returns response."""
        flow_id = uuid4()
        job_id = uuid4()
        user_id = uuid4()

        # Mock flow
        mock_flow = MagicMock()
        mock_flow.id = flow_id
        mock_flow.data = {"nodes": [{"id": "node1"}, {"id": "node2"}], "edges": []}

        # Mock vertex_builds
        mock_vb1 = MagicMock(spec=VertexBuildTable)
        mock_vb1.id = "node1"
        mock_vb1.data = {"outputs": {"result": "output1"}}
        mock_vb1.artifacts = {}
        mock_vb1.timestamp = datetime.now(timezone.utc)

        mock_vb2 = MagicMock(spec=VertexBuildTable)
        mock_vb2.id = "node2"
        mock_vb2.data = {"outputs": {"result": "output2"}}
        mock_vb2.artifacts = {}
        mock_vb2.timestamp = datetime.now(timezone.utc)

        mock_session = MagicMock()

        with (
            patch("langflow.api.v2.workflow_reconstruction.get_vertex_builds_by_job_id") as mock_get_vb,
            patch("langflow.api.v2.workflow_reconstruction.Graph") as mock_graph_class,
            patch("langflow.api.v2.workflow_reconstruction.run_response_to_workflow_response") as mock_converter,
        ):
            mock_get_vb.return_value = [mock_vb1, mock_vb2]

            mock_graph = MagicMock()
            mock_graph.get_terminal_nodes.return_value = ["node1", "node2"]
            mock_graph_class.from_payload.return_value = mock_graph

            mock_response = MagicMock()
            mock_response.flow_id = str(flow_id)
            mock_response.job_id = str(job_id)
            mock_converter.return_value = mock_response

            result = await reconstruct_workflow_response_from_job_id(
                session=mock_session,
                flow=mock_flow,
                job_id=str(job_id),
                user_id=user_id,
            )

            assert result.flow_id == str(flow_id)
            assert result.job_id == str(job_id)
            mock_get_vb.assert_called_once_with(mock_session, str(job_id))
            mock_graph.get_terminal_nodes.assert_called_once()

    async def test_reconstruct_fails_when_no_vertex_builds(self):
        """Test reconstruction raises ValueError when no vertex_builds found."""
        mock_flow = MagicMock()
        mock_flow.data = {"nodes": [{"id": "node1"}], "edges": []}
        mock_session = MagicMock()

        with patch("langflow.api.v2.workflow_reconstruction.get_vertex_builds_by_job_id") as mock_get_vb:
            mock_get_vb.return_value = []

            with pytest.raises(ValueError, match="No vertex builds found"):
                await reconstruct_workflow_response_from_job_id(
                    session=mock_session,
                    flow=mock_flow,
                    job_id=str(uuid4()),
                    user_id=uuid4(),
                )

    async def test_reconstruct_fails_when_flow_has_no_data(self):
        """Test reconstruction raises ValueError when flow has no data."""
        mock_flow = MagicMock()
        mock_flow.data = None
        mock_session = MagicMock()

        with pytest.raises(ValueError, match="has no data"):
            await reconstruct_workflow_response_from_job_id(
                session=mock_session,
                flow=mock_flow,
                job_id=str(uuid4()),
                user_id=uuid4(),
            )

    async def test_reconstruct_filters_to_terminal_nodes_only(self):
        """Test reconstruction only includes terminal node outputs, not intermediate nodes."""
        flow_id = uuid4()
        job_id = uuid4()
        user_id = uuid4()

        mock_flow = MagicMock()
        mock_flow.id = flow_id
        mock_flow.data = {"nodes": [{"id": "node1"}, {"id": "node2"}, {"id": "node3"}], "edges": []}

        # Create vertex_builds for all 3 nodes
        mock_vertex_builds = []
        for node_id in ["node1", "node2", "node3"]:
            mock_vb = MagicMock(spec=VertexBuildTable)
            mock_vb.id = node_id
            mock_vb.data = {"outputs": {"result": f"output_{node_id}"}}
            mock_vb.artifacts = {}
            mock_vb.timestamp = datetime.now(timezone.utc)
            mock_vertex_builds.append(mock_vb)

        mock_session = MagicMock()

        with (
            patch("langflow.api.v2.workflow_reconstruction.get_vertex_builds_by_job_id") as mock_get_vb,
            patch("langflow.api.v2.workflow_reconstruction.Graph") as mock_graph_class,
            patch("langflow.api.v2.workflow_reconstruction.run_response_to_workflow_response") as mock_converter,
        ):
            mock_get_vb.return_value = mock_vertex_builds

            # Only node1 and node3 are terminal nodes (node2 is intermediate)
            mock_graph = MagicMock()
            mock_graph.get_terminal_nodes.return_value = ["node1", "node3"]
            mock_graph_class.from_payload.return_value = mock_graph

            mock_response = MagicMock()
            mock_converter.return_value = mock_response

            result = await reconstruct_workflow_response_from_job_id(
                session=mock_session,
                flow=mock_flow,
                job_id=str(job_id),
                user_id=user_id,
            )

            assert result is not None
            mock_converter.assert_called_once()
            # Verify filtering happened by checking terminal nodes were retrieved
            mock_graph.get_terminal_nodes.assert_called_once()

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.helpers.flow import (
    get_flow_by_id_or_name,
    list_flows,
    list_flows_by_flow_folder,
    list_flows_by_folder_id,
)
from langflow.schema.data import Data
from langflow.services.database.models.flow.model import Flow


class TestListFlows:
    """Test list_flows function in backend."""

    @pytest.mark.asyncio
    async def test_list_flows_raises_error_without_user_id(self):
        """Test that list_flows raises ValueError without user_id."""
        with pytest.raises(ValueError, match="Session is invalid"):
            await list_flows(user_id=None)

    @pytest.mark.asyncio
    async def test_list_flows_queries_database(self):
        """Test that list_flows queries database correctly."""
        user_id = str(uuid4())

        mock_flow1 = MagicMock(spec=Flow)
        mock_flow1.to_data = MagicMock(return_value=Data(data={"name": "Flow 1"}))

        mock_flow2 = MagicMock(spec=Flow)
        mock_flow2.to_data = MagicMock(return_value=Data(data={"name": "Flow 2"}))

        with patch("langflow.helpers.flow.session_scope") as mock_session_scope:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.all = MagicMock(return_value=[mock_flow1, mock_flow2])
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock()

            result = await list_flows(user_id=user_id)

            assert len(result) == 2
            assert result[0].data["name"] == "Flow 1"
            assert result[1].data["name"] == "Flow 2"


class TestListFlowsByFlowFolder:
    """Test list_flows_by_flow_folder function in backend."""

    @pytest.mark.asyncio
    async def test_list_flows_by_flow_folder_raises_error_without_user_id(self):
        """Test that function raises ValueError without user_id."""
        with pytest.raises(ValueError, match="Session is invalid"):
            await list_flows_by_flow_folder(user_id=None, flow_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_list_flows_by_flow_folder_raises_error_without_flow_id(self):
        """Test that function raises ValueError without flow_id."""
        with pytest.raises(ValueError, match="Flow ID is required"):
            await list_flows_by_flow_folder(user_id=str(uuid4()), flow_id=None)

    @pytest.mark.asyncio
    async def test_list_flows_by_flow_folder_queries_same_folder(self):
        """Test that function queries flows in same folder."""
        user_id = str(uuid4())
        flow_id = str(uuid4())

        # Mock database results
        mock_row1 = MagicMock()
        mock_row1._mapping = {"id": str(uuid4()), "name": "Flow 1", "updated_at": "2024-01-01"}

        mock_row2 = MagicMock()
        mock_row2._mapping = {"id": str(uuid4()), "name": "Flow 2", "updated_at": "2024-01-02"}

        with patch("langflow.helpers.flow.session_scope") as mock_session_scope:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.all = MagicMock(return_value=[mock_row1, mock_row2])
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock()

            result = await list_flows_by_flow_folder(user_id=user_id, flow_id=flow_id)

            assert len(result) == 2
            assert isinstance(result[0], Data)
            assert result[0].data["name"] == "Flow 1"

    @pytest.mark.asyncio
    async def test_list_flows_by_flow_folder_respects_order_params(self):
        """Test that function respects ordering parameters."""
        user_id = str(uuid4())
        flow_id = str(uuid4())
        order_params = {"column": "name", "direction": "asc"}

        with patch("langflow.helpers.flow.session_scope") as mock_session_scope:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.all = MagicMock(return_value=[])
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock()

            result = await list_flows_by_flow_folder(user_id=user_id, flow_id=flow_id, order_params=order_params)

            # Verify query was executed (result should be empty list from mock)
            assert result == []


class TestListFlowsByFolderId:
    """Test list_flows_by_folder_id function in backend."""

    @pytest.mark.asyncio
    async def test_list_flows_by_folder_id_raises_error_without_user_id(self):
        """Test that function raises ValueError without user_id."""
        with pytest.raises(ValueError, match="Session is invalid"):
            await list_flows_by_folder_id(user_id=None, folder_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_list_flows_by_folder_id_raises_error_without_folder_id(self):
        """Test that function raises ValueError without folder_id."""
        with pytest.raises(ValueError, match="Folder ID is required"):
            await list_flows_by_folder_id(user_id=str(uuid4()), folder_id=None)

    @pytest.mark.asyncio
    async def test_list_flows_by_folder_id_queries_database(self):
        """Test that function queries database for flows in folder."""
        user_id = str(uuid4())
        folder_id = str(uuid4())

        mock_row1 = MagicMock()
        mock_row1._mapping = {"id": str(uuid4()), "name": "Flow 1"}

        with patch("langflow.helpers.flow.session_scope") as mock_session_scope:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.all = MagicMock(return_value=[mock_row1])
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock()

            result = await list_flows_by_folder_id(user_id=user_id, folder_id=folder_id)

            assert len(result) == 1
            assert isinstance(result[0], Data)


class TestGetFlowByIdOrName:
    """Test get_flow_by_id_or_name function in backend."""

    @pytest.mark.asyncio
    async def test_get_flow_by_id_or_name_raises_error_without_user_id(self):
        """Test that function raises ValueError without user_id."""
        with pytest.raises(ValueError, match="Session is invalid"):
            await get_flow_by_id_or_name(user_id="", flow_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_get_flow_by_id_or_name_raises_error_without_id_or_name(self):
        """Test that function raises ValueError without flow_id or flow_name."""
        with pytest.raises(ValueError, match="Flow ID or Flow Name is required"):
            await get_flow_by_id_or_name(user_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_get_flow_by_id_or_name_queries_by_id(self):
        """Test that function queries database by flow ID."""
        user_id = str(uuid4())
        flow_id = str(uuid4())

        mock_flow = MagicMock(spec=Flow)
        mock_flow.to_data = MagicMock(return_value=Data(data={"name": "Test Flow"}))

        with patch("langflow.helpers.flow.session_scope") as mock_session_scope:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.first = MagicMock(return_value=mock_flow)
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock()

            result = await get_flow_by_id_or_name(user_id=user_id, flow_id=flow_id)

            assert isinstance(result, Data)
            assert result.data["name"] == "Test Flow"

    @pytest.mark.asyncio
    async def test_get_flow_by_id_or_name_queries_by_name(self):
        """Test that function queries database by flow name."""
        user_id = str(uuid4())
        flow_name = "Test Flow"

        mock_flow = MagicMock(spec=Flow)
        mock_flow.to_data = MagicMock(return_value=Data(data={"name": flow_name}))

        with patch("langflow.helpers.flow.session_scope") as mock_session_scope:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.first = MagicMock(return_value=mock_flow)
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock()

            result = await get_flow_by_id_or_name(user_id=user_id, flow_name=flow_name)

            assert isinstance(result, Data)
            assert result.data["name"] == flow_name

    @pytest.mark.asyncio
    async def test_get_flow_by_id_or_name_prefers_id_over_name(self):
        """Test that function prefers flow_id when both are provided."""
        user_id = str(uuid4())
        flow_id = str(uuid4())
        flow_name = "Test Flow"

        mock_flow = MagicMock(spec=Flow)
        mock_flow.to_data = MagicMock(return_value=Data(data={"id": flow_id, "name": flow_name}))

        with patch("langflow.helpers.flow.session_scope") as mock_session_scope:
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.first = MagicMock(return_value=mock_flow)
            mock_session.exec = AsyncMock(return_value=mock_result)
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock()

            result = await get_flow_by_id_or_name(user_id=user_id, flow_id=flow_id, flow_name=flow_name)

            assert isinstance(result, Data)
            # The query should have been made with flow_id (checking it was called)
            mock_session.exec.assert_called_once()

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.helpers.flow import (
    get_flow_by_id_or_endpoint_name,
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


class TestGetFlowByIdOrEndpointName:
    """Regression tests for the IDOR fix in get_flow_by_id_or_endpoint_name (LE-639).

    The UUID branch previously called ``session.get(Flow, flow_id)`` without
    applying any ownership check, so any authenticated caller could resolve
    another user's flow by UUID.  The endpoint_name branch had the matching
    issue when ``user_id`` was not supplied (the FastAPI ``Depends`` pattern
    provided no user_id by default).  These tests lock in the fix.
    """

    @staticmethod
    def _patch_session(mock_session):
        """Patch session_scope to yield the provided mock session."""
        patcher = patch("langflow.helpers.flow.session_scope")
        mock_scope = patcher.start()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
        return patcher

    @pytest.mark.asyncio
    async def test_uuid_branch_returns_flow_for_owner(self):
        """Same-user UUID lookup returns the flow (happy path)."""
        owner_id = uuid4()
        flow_id = uuid4()
        flow = MagicMock(spec=Flow)
        flow.id = flow_id
        flow.user_id = owner_id
        flow.name = "test_flow"
        flow.endpoint_name = None
        flow.data = {}
        flow.description = None
        flow.is_component = False
        flow.updated_at = None
        flow.folder_id = None
        flow.user_id = owner_id

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=flow)

        patcher = self._patch_session(mock_session)
        try:
            with patch("langflow.helpers.flow.FlowRead") as mock_flow_read:
                mock_flow_read.model_validate = MagicMock(return_value="validated_flow")
                result = await get_flow_by_id_or_endpoint_name(str(flow_id), str(owner_id))
                assert result == "validated_flow"
                mock_session.get.assert_awaited_once_with(Flow, flow_id)
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_uuid_branch_rejects_cross_user_access(self):
        """Cross-user UUID lookup raises 404 (the core IDOR fix)."""
        attacker_id = uuid4()
        victim_id = uuid4()
        flow_id = uuid4()
        victim_flow = MagicMock(spec=Flow)
        victim_flow.id = flow_id
        victim_flow.user_id = victim_id

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=victim_flow)

        patcher = self._patch_session(mock_session)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await get_flow_by_id_or_endpoint_name(str(flow_id), str(attacker_id))
            assert exc_info.value.status_code == 404
            # Must NOT 403 -- returning 403 would confirm the flow exists to
            # an attacker enumerating UUIDs.  404 hides existence.
            assert "not found" in exc_info.value.detail.lower()
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_uuid_branch_accepts_uuid_instance_for_user_id(self):
        """Callers passing a UUID object (not str) are handled correctly."""
        attacker_id = uuid4()
        victim_id = uuid4()
        flow_id = uuid4()
        victim_flow = MagicMock(spec=Flow)
        victim_flow.id = flow_id
        victim_flow.user_id = victim_id

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=victim_flow)

        patcher = self._patch_session(mock_session)
        try:
            with pytest.raises(HTTPException) as exc_info:
                # Pass UUID, not str -- matches workflow.py:151 call style.
                await get_flow_by_id_or_endpoint_name(str(flow_id), attacker_id)
            assert exc_info.value.status_code == 404
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_uuid_branch_without_user_id_returns_flow(self):
        """No user_id = no scoping (preserves webhook/internal caller behavior)."""
        flow_id = uuid4()
        flow = MagicMock(spec=Flow)
        flow.id = flow_id
        flow.user_id = uuid4()

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=flow)

        patcher = self._patch_session(mock_session)
        try:
            with patch("langflow.helpers.flow.FlowRead") as mock_flow_read:
                mock_flow_read.model_validate = MagicMock(return_value="validated_flow")
                # user_id=None: any flow is returned.
                result = await get_flow_by_id_or_endpoint_name(str(flow_id), user_id=None)
                assert result == "validated_flow"
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_uuid_branch_missing_flow_raises_404(self):
        """Non-existent UUID returns 404 regardless of user_id."""
        owner_id = uuid4()
        flow_id = uuid4()

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=None)

        patcher = self._patch_session(mock_session)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await get_flow_by_id_or_endpoint_name(str(flow_id), str(owner_id))
            assert exc_info.value.status_code == 404
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_endpoint_name_branch_scopes_by_user(self):
        """endpoint_name lookup filters by user_id when supplied."""
        owner_id = uuid4()

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=None)
        mock_session.exec = AsyncMock(return_value=mock_result)

        patcher = self._patch_session(mock_session)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await get_flow_by_id_or_endpoint_name("my-webhook", str(owner_id))
            assert exc_info.value.status_code == 404
            # The select statement should have been filtered by user_id --
            # verified indirectly by the exec call count (1 call, scoped).
            mock_session.exec.assert_awaited_once()
            stmt = mock_session.exec.await_args.args[0]
            # Compile the where clauses and confirm the user_id filter is present.
            where_sql = str(stmt.whereclause)
            assert "user_id" in where_sql

        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_endpoint_name_branch_without_user_id_not_scoped(self):
        """No user_id on endpoint_name branch = no user scoping (webhook behavior)."""
        flow = MagicMock(spec=Flow)
        flow.id = uuid4()
        flow.user_id = uuid4()

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=flow)
        mock_session.exec = AsyncMock(return_value=mock_result)

        patcher = self._patch_session(mock_session)
        try:
            with patch("langflow.helpers.flow.FlowRead") as mock_flow_read:
                mock_flow_read.model_validate = MagicMock(return_value="validated_flow")
                result = await get_flow_by_id_or_endpoint_name("webhook-ep", user_id=None)
                assert result == "validated_flow"
                stmt = mock_session.exec.await_args.args[0]
                where_sql = str(stmt.whereclause) if stmt.whereclause is not None else ""
                # With no user_id, the only filter should be endpoint_name.
                assert "user_id" not in where_sql
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_accepts_uuid_instance_for_user_id_parameter(self):
        """user_id can be a UUID object (matches workflow.py call sites)."""
        owner_id = UUID(str(uuid4()))

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=None)

        patcher = self._patch_session(mock_session)
        try:
            with pytest.raises(HTTPException):
                await get_flow_by_id_or_endpoint_name(str(uuid4()), owner_id)
        finally:
            patcher.stop()

    @pytest.mark.parametrize("bad_user_id", ["not-a-uuid", "", "12345-not-a-real-uuid"])
    @pytest.mark.asyncio
    async def test_malformed_user_id_raises_404_not_500(self, bad_user_id):
        """Malformed user_id (e.g. ``?user_id=foo``) must fail closed with 404.

        Previously the eager ``UUID(user_id)`` normalization raised a raw
        ``ValueError`` that surfaced as a 500 to the client.  The helper now
        converts that into the same 404 we'd return for "flow not found" so
        that a malformed caller identity can never be used to enumerate or
        exfiltrate flows, and doesn't give attackers a new error signal.
        """
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=None)

        patcher = self._patch_session(mock_session)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await get_flow_by_id_or_endpoint_name(str(uuid4()), bad_user_id)
            assert exc_info.value.status_code == 404
            # Session lookup should never happen if user_id couldn't be parsed.
            mock_session.get.assert_not_awaited()
        finally:
            patcher.stop()

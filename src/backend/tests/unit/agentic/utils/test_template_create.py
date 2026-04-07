"""Tests for flow creation from starter templates.

Tests the create_flow_from_template_and_get_link function
which creates a new Flow from a template and returns a UI link.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.agentic.utils.template_create import create_flow_from_template_and_get_link

MODULE = "langflow.agentic.utils.template_create"

USER_ID = uuid4()
FOLDER_ID = uuid4()
FLOW_ID = uuid4()

TEMPLATE_DATA = {
    "name": "Test Template",
    "description": "A test template",
    "icon": "test-icon",
    "icon_bg_color": "#000000",
    "gradient": "linear-gradient()",
    "data": {"nodes": [], "edges": []},
    "is_component": False,
    "endpoint_name": "test-endpoint",
    "tags": ["test"],
    "mcp_enabled": False,
}


def _make_db_flow():
    """Create a mock database flow object."""
    flow = MagicMock()
    flow.id = FLOW_ID
    return flow


def _make_folder(user_id=None):
    """Create a mock folder object."""
    folder = MagicMock()
    folder.id = FOLDER_ID
    folder.user_id = user_id or USER_ID
    return folder


class TestCreateFlowFromTemplate:
    """Tests for create_flow_from_template_and_get_link."""

    @pytest.mark.asyncio
    async def test_should_create_flow_from_template(self):
        """Should create flow using default folder and return id + link."""
        mock_session = AsyncMock()
        db_flow = _make_db_flow()
        default_folder = _make_folder()

        with (
            patch(f"{MODULE}.get_template_by_id", return_value=TEMPLATE_DATA),
            patch(f"{MODULE}.get_or_create_default_folder", new_callable=AsyncMock, return_value=default_folder),
            patch(f"{MODULE}._new_flow", new_callable=AsyncMock, return_value=db_flow),
            patch(f"{MODULE}._save_flow_to_fs", new_callable=AsyncMock),
            patch(f"{MODULE}.get_storage_service", return_value=MagicMock()),
        ):
            result = await create_flow_from_template_and_get_link(
                session=mock_session,
                user_id=USER_ID,
                template_id="test-template",
            )

        assert result["id"] == str(FLOW_ID)
        assert f"/flow/{FLOW_ID}" in result["link"]
        assert f"/folder/{FOLDER_ID}" in result["link"]

    @pytest.mark.asyncio
    async def test_should_raise_404_when_template_not_found(self):
        """Should raise HTTPException 404 when template doesn't exist."""
        mock_session = AsyncMock()

        with patch(f"{MODULE}.get_template_by_id", return_value=None), pytest.raises(HTTPException) as exc_info:
            await create_flow_from_template_and_get_link(
                session=mock_session,
                user_id=USER_ID,
                template_id="nonexistent",
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_should_use_target_folder_when_provided(self):
        """Should use target_folder_id instead of default folder."""
        mock_session = AsyncMock()
        target_folder = _make_folder()
        mock_session.get = AsyncMock(return_value=target_folder)
        db_flow = _make_db_flow()

        with (
            patch(f"{MODULE}.get_template_by_id", return_value=TEMPLATE_DATA),
            patch(f"{MODULE}._new_flow", new_callable=AsyncMock, return_value=db_flow),
            patch(f"{MODULE}._save_flow_to_fs", new_callable=AsyncMock),
            patch(f"{MODULE}.get_storage_service", return_value=MagicMock()),
        ):
            result = await create_flow_from_template_and_get_link(
                session=mock_session,
                user_id=USER_ID,
                template_id="test-template",
                target_folder_id=FOLDER_ID,
            )

        assert f"/folder/{FOLDER_ID}" in result["link"]

    @pytest.mark.asyncio
    async def test_should_raise_400_for_invalid_target_folder(self):
        """Should raise HTTPException 400 when folder doesn't exist."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        with (
            patch(f"{MODULE}.get_template_by_id", return_value=TEMPLATE_DATA),
            pytest.raises(HTTPException) as exc_info,
        ):
            await create_flow_from_template_and_get_link(
                session=mock_session,
                user_id=USER_ID,
                template_id="test-template",
                target_folder_id=uuid4(),
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_should_raise_400_for_wrong_user_folder(self):
        """Should raise HTTPException 400 when folder belongs to different user."""
        mock_session = AsyncMock()
        other_user_folder = _make_folder(user_id=uuid4())
        mock_session.get = AsyncMock(return_value=other_user_folder)

        with (
            patch(f"{MODULE}.get_template_by_id", return_value=TEMPLATE_DATA),
            pytest.raises(HTTPException) as exc_info,
        ):
            await create_flow_from_template_and_get_link(
                session=mock_session,
                user_id=USER_ID,
                template_id="test-template",
                target_folder_id=FOLDER_ID,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_should_build_correct_link_format(self):
        """Link should follow format /flow/{id}/folder/{folder_id}."""
        mock_session = AsyncMock()
        db_flow = _make_db_flow()
        default_folder = _make_folder()

        with (
            patch(f"{MODULE}.get_template_by_id", return_value=TEMPLATE_DATA),
            patch(f"{MODULE}.get_or_create_default_folder", new_callable=AsyncMock, return_value=default_folder),
            patch(f"{MODULE}._new_flow", new_callable=AsyncMock, return_value=db_flow),
            patch(f"{MODULE}._save_flow_to_fs", new_callable=AsyncMock),
            patch(f"{MODULE}.get_storage_service", return_value=MagicMock()),
        ):
            result = await create_flow_from_template_and_get_link(
                session=mock_session,
                user_id=USER_ID,
                template_id="test-template",
            )

        assert result["link"] == f"/flow/{FLOW_ID}/folder/{FOLDER_ID}"

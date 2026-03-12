"""Tests for deployment provider-sync helpers.

Covers:
- _fetch_provider_resource_keys: ID-only matching, error handling
- _list_deployments_synced: cursor-based sync with inline stale-row deletion
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


MODULE = "langflow.api.v1.deployments"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_item(*, id: str, name: str = "irrelevant") -> MagicMock:
    """Simulate an ItemResult from the provider."""
    item = MagicMock()
    item.id = id
    item.name = name
    return item


def _mock_provider_view(items: list[MagicMock]) -> MagicMock:
    view = MagicMock()
    view.deployments = items
    return view


def _mock_deployment_row(resource_key: str, deployment_type: str | None = None) -> MagicMock:
    row = MagicMock()
    row.id = uuid4()
    row.resource_key = resource_key
    row.deployment_type = deployment_type
    return row


# ---------------------------------------------------------------------------
# _fetch_provider_resource_keys
# ---------------------------------------------------------------------------


class TestFetchProviderResourceKeys:
    @pytest.mark.asyncio
    async def test_returns_ids_only(self):
        """Provider items matched by str(item.id), not item.name."""
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view([
            _mock_item(id="rk-1", name="deploy-one"),
            _mock_item(id="rk-2", name="deploy-two"),
        ])

        from langflow.api.v1.deployments import _fetch_provider_resource_keys

        result = await _fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=["rk-1", "rk-2"],
        )

        assert result == {"rk-1", "rk-2"}

    @pytest.mark.asyncio
    async def test_does_not_match_by_name(self):
        """If a name matches a resource_key but the id doesn't, it should NOT be included."""
        adapter = AsyncMock()
        # Provider returns item with id="different" but name="rk-1"
        adapter.list.return_value = _mock_provider_view([
            _mock_item(id="different", name="rk-1"),
        ])

        from langflow.api.v1.deployments import _fetch_provider_resource_keys

        result = await _fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=["rk-1"],
        )

        # "rk-1" is NOT in the result because only id is checked, and id="different"
        assert "rk-1" not in result
        assert result == {"different"}

    @pytest.mark.asyncio
    async def test_skips_items_with_no_id(self):
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view([
            _mock_item(id="rk-1"),
            _mock_item(id=""),  # falsy id
        ])

        from langflow.api.v1.deployments import _fetch_provider_resource_keys

        result = await _fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=["rk-1"],
        )

        assert result == {"rk-1"}

    @pytest.mark.asyncio
    async def test_empty_provider_response(self):
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view([])

        from langflow.api.v1.deployments import _fetch_provider_resource_keys

        result = await _fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=["rk-1"],
        )

        assert result == set()

    @pytest.mark.asyncio
    async def test_provider_error_raises_502(self):
        adapter = AsyncMock()
        adapter.list.side_effect = RuntimeError("provider down")

        from langflow.api.v1.deployments import _fetch_provider_resource_keys

        with pytest.raises(HTTPException) as exc_info:
            await _fetch_provider_resource_keys(
                deployment_adapter=adapter,
                user_id=uuid4(),
                provider_id=uuid4(),
                db=AsyncMock(),
                resource_keys=["rk-1"],
            )

        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_passes_resource_keys_as_ids_param(self):
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view([])

        from langflow.api.v1.deployments import _fetch_provider_resource_keys

        keys = ["rk-1", "rk-2", "rk-3"]
        await _fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=keys,
        )

        call_args = adapter.list.call_args
        params = call_args.kwargs["params"]
        assert params.provider_params == {"ids": keys}
        assert params.deployment_types is None

    @pytest.mark.asyncio
    async def test_passes_deployment_type_filter(self):
        """When deployment_type is provided, it's forwarded to the provider."""
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view([])

        from langflow.api.v1.deployments import DeploymentType, _fetch_provider_resource_keys

        await _fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=["rk-1"],
            deployment_type=DeploymentType("agent"),
        )

        params = adapter.list.call_args.kwargs["params"]
        assert params.deployment_types == [DeploymentType("agent")]


# ---------------------------------------------------------------------------
# _list_deployments_synced
# ---------------------------------------------------------------------------


class TestListDeploymentsSynced:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=2)
    @patch(f"{MODULE}._fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_keeps_provider_confirmed_rows(self, mock_list, mock_fetch, mock_count):
        """Rows whose resource_key is in the provider's known set are kept."""
        row1 = _mock_deployment_row("rk-1")
        row2 = _mock_deployment_row("rk-2")
        mock_list.side_effect = [[(row1, 0, []), (row2, 1, ["fv-1"])], []]
        mock_fetch.return_value = {"rk-1", "rk-2"}

        from langflow.api.v1.deployments import _list_deployments_synced

        accepted, total = await _list_deployments_synced(
            deployment_adapter=AsyncMock(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 2
        assert accepted[0][0] is row1
        assert accepted[1][0] is row2
        assert total == 2

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}._fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_deletes_stale_rows(self, mock_list, mock_fetch, mock_delete, mock_count):
        """Rows not recognised by the provider are deleted."""
        stale_row = _mock_deployment_row("rk-stale")
        good_row = _mock_deployment_row("rk-good")
        uid = uuid4()

        # First call returns stale + good; second call returns empty (all consumed)
        mock_list.side_effect = [
            [(stale_row, 0, []), (good_row, 1, [])],
            [],
        ]
        mock_fetch.return_value = {"rk-good"}  # only rk-good is known

        from langflow.api.v1.deployments import _list_deployments_synced

        accepted, _ = await _list_deployments_synced(
            deployment_adapter=AsyncMock(),
            user_id=uid,
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 1
        assert accepted[0][0] is good_row
        mock_delete.assert_awaited_once_with(
            mock_delete.call_args.args[0],  # db
            user_id=uid,
            deployment_id=stale_row.id,
        )

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}._fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_empty_batch_stops_loop(self, mock_list, mock_fetch, mock_count):
        """An empty batch from the DB ends the loop."""
        mock_list.return_value = []

        from langflow.api.v1.deployments import _list_deployments_synced

        accepted, total = await _list_deployments_synced(
            deployment_adapter=AsyncMock(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=None,
        )

        assert accepted == []
        assert total == 0
        mock_fetch.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=2)
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}._fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_mismatched_type_not_in_known_skips_without_deleting(
        self, mock_list, mock_fetch, mock_delete, mock_count
    ):
        """Row not in known but with a different local type is skipped, not deleted.

        The provider was filtered by type, so absence only means the type didn't
        match — the resource may still exist on the provider.
        """
        row_match = _mock_deployment_row("rk-1", deployment_type="agent")
        row_other = _mock_deployment_row("rk-2", deployment_type="other")
        mock_list.side_effect = [
            [(row_match, 0, []), (row_other, 0, [])],
            [],
        ]
        # Provider filtered by "agent" — only rk-1 returned
        mock_fetch.return_value = {"rk-1"}

        from langflow.api.v1.deployments import DeploymentType, _list_deployments_synced

        accepted, _ = await _list_deployments_synced(
            deployment_adapter=AsyncMock(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=DeploymentType("agent"),
        )

        assert len(accepted) == 1
        assert accepted[0][0] is row_match
        # rk-2 was NOT deleted — just skipped
        mock_delete.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}._fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_cursor_does_not_advance_on_delete(self, mock_list, mock_fetch, mock_delete, mock_count):
        """When a stale row is deleted the cursor stays put (offset doesn't increment)."""
        stale = _mock_deployment_row("rk-stale")
        good = _mock_deployment_row("rk-good")

        # First batch: stale row only. Cursor should stay at 0 for next fetch.
        # Second batch: good row at the same offset (because deletion shifted it).
        mock_list.side_effect = [
            [(stale, 0, [])],
            [(good, 0, [])],
            [],
        ]
        mock_fetch.side_effect = [
            set(),       # stale not known
            {"rk-good"}, # good is known
        ]

        from langflow.api.v1.deployments import _list_deployments_synced

        accepted, _ = await _list_deployments_synced(
            deployment_adapter=AsyncMock(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=None,
        )

        # Both list_deployments_page calls should use offset=0
        offsets = [call.kwargs["offset"] for call in mock_list.call_args_list[:2]]
        assert offsets == [0, 0], f"Expected cursor to stay at 0 after deletion, got offsets={offsets}"
        assert len(accepted) == 1
        assert accepted[0][0] is good

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=5)
    @patch(f"{MODULE}._fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_page_offset_calculation(self, mock_list, mock_fetch, mock_count):
        """Page 2 with size 5 should start at offset 5."""
        mock_list.return_value = []

        from langflow.api.v1.deployments import _list_deployments_synced

        await _list_deployments_synced(
            deployment_adapter=AsyncMock(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=2,
            size=5,
            deployment_type=None,
        )

        assert mock_list.call_args.kwargs["offset"] == 5

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}._fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_guard_prevents_infinite_loop(self, mock_list, mock_fetch, mock_delete, mock_count):
        """The guard counter breaks the loop if too many iterations occur."""
        stale = _mock_deployment_row("rk-stale")
        # Always return a stale row — should eventually stop via guard
        mock_list.return_value = [(stale, 0, [])]
        mock_fetch.return_value = set()  # never known

        from langflow.api.v1.deployments import _list_deployments_synced

        accepted, _ = await _list_deployments_synced(
            deployment_adapter=AsyncMock(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=2,
            deployment_type=None,
        )

        assert accepted == []
        # guard = size * 4 + 20 = 28, so loop ran at most 28 times
        assert mock_list.call_count <= 28

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=3)
    @patch(f"{MODULE}._fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_passes_flow_version_ids_through(self, mock_list, mock_fetch, mock_count):
        """flow_version_ids are forwarded to list_deployments_page and count."""
        mock_list.return_value = []
        fv_ids = [uuid4(), uuid4()]

        from langflow.api.v1.deployments import _list_deployments_synced

        await _list_deployments_synced(
            deployment_adapter=AsyncMock(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=None,
            flow_version_ids=fv_ids,
        )

        assert mock_list.call_args.kwargs["flow_version_ids"] == fv_ids
        assert mock_count.call_args.kwargs["flow_version_ids"] == fv_ids

"""Tests for deployment provider-sync helpers.

Covers:
- fetch_provider_resource_keys: ID-only matching, error handling
- list_deployments_synced: cursor-based sync with inline stale-row deletion
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper
from langflow.api.v1.mappers.deployments.contracts import (
    CreateSnapshotBinding,
    CreateSnapshotBindings,
    UpdateSnapshotBinding,
    UpdateSnapshotBindings,
)
from langflow.api.v1.schemas.deployments import DeploymentUpdateRequest
from lfx.services.adapters.deployment.exceptions import ServiceUnavailableError
from lfx.services.adapters.deployment.schema import (
    DeploymentCreateResult,
    DeploymentGetResult,
    DeploymentUpdateResult,
    SnapshotItem,
    SnapshotListResult,
)

try:
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper
except ModuleNotFoundError:
    pytest.skip(
        "Skipping Watsonx deployment sync tests: optional IBM SDK dependencies not available.",
        allow_module_level=True,
    )

MODULE = "langflow.api.v1.mappers.deployments.helpers"
SYNC_MODULE = "langflow.api.v1.mappers.deployments.sync"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_item(*, item_id: str, name: str = "irrelevant") -> SimpleNamespace:
    return SimpleNamespace(id=item_id, name=name)


def _mock_provider_view(items: list) -> SimpleNamespace:
    return SimpleNamespace(deployments=items)


def _mock_deployment_row(resource_key: str, deployment_type: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        resource_key=resource_key,
        deployment_type=deployment_type,
        deployment_provider_account_id=uuid4(),
    )


class _AsyncNoopSavepoint:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


# ---------------------------------------------------------------------------
# fetch_provider_resource_keys
# ---------------------------------------------------------------------------


class TestFetchProviderResourceKeys:
    @pytest.mark.asyncio
    async def test_returns_ids_only(self):
        """Provider items matched by str(item.id), not item.name."""
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view(
            [
                _mock_item(item_id="rk-1", name="deploy-one"),
                _mock_item(item_id="rk-2", name="deploy-two"),
            ]
        )

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        known_keys, provider_view = await fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=["rk-1", "rk-2"],
        )

        assert known_keys == {"rk-1", "rk-2"}
        assert provider_view is adapter.list.return_value

    @pytest.mark.asyncio
    async def test_does_not_match_by_name(self):
        """If a name matches a resource_key but the id doesn't, it should NOT be included."""
        adapter = AsyncMock()
        # Provider returns item with id="different" but name="rk-1"
        adapter.list.return_value = _mock_provider_view(
            [
                _mock_item(item_id="different", name="rk-1"),
            ]
        )

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        known_keys, provider_view = await fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=["rk-1"],
        )

        # "rk-1" is NOT in the result because only id is checked, and id="different"
        assert "rk-1" not in known_keys
        assert known_keys == {"different"}
        assert provider_view is adapter.list.return_value

    @pytest.mark.asyncio
    async def test_empty_provider_id_raises_value_error(self):
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view(
            [
                _mock_item(item_id="rk-1"),
                _mock_item(item_id=""),  # falsy id
            ]
        )

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        with pytest.raises(ValueError, match="empty id"):
            await fetch_provider_resource_keys(
                deployment_adapter=adapter,
                user_id=uuid4(),
                provider_id=uuid4(),
                db=AsyncMock(),
                resource_keys=["rk-1"],
            )

    @pytest.mark.asyncio
    async def test_empty_provider_response(self):
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view([])

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        known_keys, provider_view = await fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=["rk-1"],
        )

        assert known_keys == set()
        assert provider_view is adapter.list.return_value

    @pytest.mark.asyncio
    async def test_provider_error_raises_500_for_unhandled_exception(self):
        adapter = AsyncMock()
        adapter.list.side_effect = RuntimeError("provider down")

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        with pytest.raises(HTTPException) as exc_info:
            await fetch_provider_resource_keys(
                deployment_adapter=adapter,
                user_id=uuid4(),
                provider_id=uuid4(),
                db=AsyncMock(),
                resource_keys=["rk-1"],
            )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_provider_deployment_service_error_uses_mapped_http_status(self):
        adapter = AsyncMock()
        adapter.list.side_effect = ServiceUnavailableError("provider down")

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        with pytest.raises(HTTPException) as exc_info:
            await fetch_provider_resource_keys(
                deployment_adapter=adapter,
                user_id=uuid4(),
                provider_id=uuid4(),
                db=AsyncMock(),
                resource_keys=["rk-1"],
            )

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "provider down"

    @pytest.mark.asyncio
    async def test_passes_resource_keys_as_deployment_ids(self):
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view([])

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        keys = ["rk-1", "rk-2", "rk-3"]
        await fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=keys,
        )

        call_args = adapter.list.call_args
        params = call_args.kwargs["params"]
        assert params.deployment_ids == keys
        assert params.provider_params is None
        assert params.deployment_types is None

    @pytest.mark.asyncio
    async def test_empty_resource_keys_returns_empty_set(self):
        adapter = AsyncMock()

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        known_keys, provider_view = await fetch_provider_resource_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            resource_keys=[],
        )

        assert known_keys == set()
        assert provider_view.deployments == []
        adapter.list.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_passes_deployment_type_filter(self):
        """When deployment_type is provided, it's forwarded to the provider."""
        adapter = AsyncMock()
        adapter.list.return_value = _mock_provider_view([])

        from langflow.api.v1.mappers.deployments.helpers import DeploymentType, fetch_provider_resource_keys

        await fetch_provider_resource_keys(
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
# list_deployments_synced
# ---------------------------------------------------------------------------


class TestListDeploymentsSynced:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=2)
    @patch(f"{MODULE}.count_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.delete_unbound_attachments", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_keeps_provider_confirmed_rows(
        self,
        mock_list,
        mock_fetch,
        mock_delete_unbound,
        mock_count_attachments,
        mock_count,
    ):
        """Rows whose resource_key is in the provider's known set are kept."""
        row1 = _mock_deployment_row("rk-1")
        row2 = _mock_deployment_row("rk-2")
        fv_id = uuid4()
        mock_list.side_effect = [[(row1, 0, []), (row2, 1, [(fv_id, "snap-1")])], []]
        mock_fetch.return_value = ({"rk-1", "rk-2"}, None)
        mock_count_attachments.return_value = {row1.id: 0, row2.id: 1}
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, total = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=db,
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 2
        assert accepted[0][0] is row1
        assert accepted[1][0] is row2
        assert total == 2
        mock_delete_unbound.assert_awaited_once()
        mock_count.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.count_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.delete_unbound_attachments", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_deletes_stale_rows(
        self,
        mock_list,
        mock_fetch,
        mock_delete,
        mock_delete_unbound,
        mock_count_attachments,
        mock_count,
    ):
        """Rows not recognised by the provider are deleted."""
        stale_row = _mock_deployment_row("rk-stale")
        good_row = _mock_deployment_row("rk-good")
        uid = uuid4()
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        # First call returns stale + good; second call returns empty (all consumed)
        mock_list.side_effect = [
            [(stale_row, 0, []), (good_row, 1, [])],
            [],
        ]
        mock_fetch.return_value = ({"rk-good"}, None)  # only rk-good is known
        mock_count_attachments.return_value = {good_row.id: 1}

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
            user_id=uid,
            provider_id=uuid4(),
            db=db,
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 1
        assert accepted[0][0] is good_row
        mock_delete.assert_awaited_once_with(
            db,
            user_id=uid,
            deployment_id=stale_row.id,
        )
        mock_delete_unbound.assert_awaited_once()
        mock_count.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_empty_batch_stops_loop(self, mock_list, mock_fetch, mock_count):
        """An empty batch from the DB ends the loop."""
        mock_list.return_value = []

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, total = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
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
        mock_count.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=2)
    @patch(f"{MODULE}.count_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.delete_unbound_attachments", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_mismatched_type_not_in_known_skips_without_deleting(
        self,
        mock_list,
        mock_fetch,
        mock_delete,
        mock_delete_unbound,
        mock_count_attachments,
        mock_count,
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
        mock_fetch.return_value = ({"rk-1"}, None)
        mock_count_attachments.return_value = {row_match.id: 0}
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.helpers import DeploymentType, list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=db,
            page=1,
            size=10,
            deployment_type=DeploymentType("agent"),
        )

        assert len(accepted) == 1
        assert accepted[0][0] is row_match
        # rk-2 was NOT deleted — just skipped
        mock_delete.assert_not_awaited()
        mock_delete_unbound.assert_awaited_once()
        mock_count.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.count_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.delete_unbound_attachments", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_cursor_does_not_advance_on_delete(
        self,
        mock_list,
        mock_fetch,
        mock_delete,
        mock_delete_unbound,
        mock_count_attachments,
        mock_count,
    ):
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
            (set(), None),  # stale not known
            ({"rk-good"}, None),  # good is known
        ]
        mock_count_attachments.return_value = {good.id: 0}
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=db,
            page=1,
            size=10,
            deployment_type=None,
        )

        # Both list_deployments_page calls should use offset=0
        offsets = [call.kwargs["offset"] for call in mock_list.call_args_list[:2]]
        assert offsets == [0, 0], f"Expected cursor to stay at 0 after deletion, got offsets={offsets}"
        assert len(accepted) == 1
        assert accepted[0][0] is good
        mock_delete.assert_awaited_once()
        mock_delete_unbound.assert_awaited_once()
        mock_count.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=5)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_page_offset_calculation(self, mock_list, mock_fetch, mock_count):
        """Page 2 with size 5 should start at offset 5."""
        mock_list.return_value = []

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=2,
            size=5,
            deployment_type=None,
        )

        assert mock_list.call_args.kwargs["offset"] == 5
        mock_fetch.assert_not_awaited()
        mock_count.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_stops_after_one_refill(self, mock_list, mock_fetch, mock_delete, mock_count):
        """Only two sync rounds run: initial fetch + one refill."""
        stale = _mock_deployment_row("rk-stale")
        # Always return a stale row — the function should still stop after 2 rounds.
        mock_list.return_value = [(stale, 0, [])]
        mock_fetch.return_value = (set(), None)  # never known

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=2,
            deployment_type=None,
        )

        assert accepted == []
        assert mock_list.call_count == 2
        assert mock_delete.await_count == 2
        mock_count.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=3)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_passes_flow_version_ids_through(self, mock_list, mock_fetch, mock_count):
        """flow_version_ids are forwarded to list_deployments_page and count."""
        mock_list.return_value = []
        fv_ids = [uuid4(), uuid4()]

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
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
        mock_fetch.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_passes_project_id_through(self, mock_list, mock_fetch, mock_count):
        """project_id is forwarded to list_deployments_page and count."""
        mock_list.return_value = []
        project_id = uuid4()

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=None,
            project_id=project_id,
        )

        assert mock_list.call_args.kwargs["project_id"] == project_id
        assert mock_count.call_args.kwargs["project_id"] == project_id
        mock_fetch.assert_not_awaited()


class _FakeMapper(BaseDeploymentMapper):
    def util_create_snapshot_bindings(self, *, result) -> CreateSnapshotBindings:  # type: ignore[override]
        provider_result = result.provider_result
        if not isinstance(provider_result, dict):
            return CreateSnapshotBindings()
        snapshot_bindings = provider_result.get("snapshot_bindings")
        if not isinstance(snapshot_bindings, list):
            return CreateSnapshotBindings()
        resolved: list[CreateSnapshotBinding] = []
        for binding in snapshot_bindings:
            if not isinstance(binding, dict):
                continue
            source_ref = str(binding.get("source_ref") or "").strip()
            snapshot_id = str(binding.get("snapshot_id") or "").strip()
            if source_ref and snapshot_id:
                resolved.append(
                    CreateSnapshotBinding(
                        source_ref=source_ref,
                        snapshot_id=snapshot_id,
                    )
                )
        return CreateSnapshotBindings(snapshot_bindings=resolved)

    def util_update_snapshot_bindings(self, *, result) -> UpdateSnapshotBindings:  # type: ignore[override]
        provider_result = result.provider_result
        if not isinstance(provider_result, dict):
            return UpdateSnapshotBindings()
        snapshot_bindings = provider_result.get("added_snapshot_bindings")
        if not isinstance(snapshot_bindings, list):
            return UpdateSnapshotBindings()
        resolved: list[UpdateSnapshotBinding] = []
        for binding in snapshot_bindings:
            if not isinstance(binding, dict):
                continue
            source_ref = str(binding.get("source_ref") or "").strip()
            snapshot_id = str(binding.get("snapshot_id") or "").strip()
            if source_ref and snapshot_id:
                resolved.append(
                    UpdateSnapshotBinding(
                        source_ref=source_ref,
                        snapshot_id=snapshot_id,
                    )
                )
        return UpdateSnapshotBindings(snapshot_bindings=resolved)


class TestCreateSnapshotMapping:
    def test_resolve_snapshot_map_for_create_maps_source_ref_to_flow_version_ids(self):
        from langflow.api.v1.mappers.deployments.helpers import resolve_snapshot_map_for_create

        flow_version_ids = [uuid4(), uuid4()]
        resolved = resolve_snapshot_map_for_create(
            deployment_mapper=_FakeMapper(),
            result=DeploymentCreateResult(
                id="provider-id",
                provider_result={
                    "snapshot_bindings": [
                        {"source_ref": str(flow_version_ids[0]), "snapshot_id": "snap-1"},
                        {"source_ref": str(flow_version_ids[1]), "snapshot_id": "snap-2"},
                    ]
                },
            ),
            flow_version_ids=flow_version_ids,
        )

        assert resolved == {
            flow_version_ids[0]: "snap-1",
            flow_version_ids[1]: "snap-2",
        }

    def test_resolve_snapshot_map_for_create_rejects_missing_bindings(self):
        from langflow.api.v1.mappers.deployments.helpers import resolve_snapshot_map_for_create

        with pytest.raises(HTTPException, match="missing required snapshot bindings"):
            resolve_snapshot_map_for_create(
                deployment_mapper=_FakeMapper(),
                result=DeploymentCreateResult(id="provider-id"),
                flow_version_ids=[uuid4()],
            )


class TestUpdateSnapshotMapping:
    def test_resolve_added_snapshot_bindings_for_update_maps_source_ref(self):
        from langflow.api.v1.mappers.deployments.helpers import resolve_added_snapshot_bindings_for_update

        flow_version_ids = [uuid4(), uuid4()]
        resolved = resolve_added_snapshot_bindings_for_update(
            deployment_mapper=_FakeMapper(),
            added_flow_version_ids=flow_version_ids,
            result=DeploymentUpdateResult(
                id="provider-id",
                provider_result={
                    "added_snapshot_bindings": [
                        {"source_ref": str(flow_version_ids[0]), "snapshot_id": "snap-1"},
                        {"source_ref": str(flow_version_ids[1]), "snapshot_id": "snap-2"},
                    ]
                },
            ),
        )

        assert resolved == [
            (flow_version_ids[0], "snap-1"),
            (flow_version_ids[1], "snap-2"),
        ]

    def test_resolve_added_snapshot_bindings_for_update_rejects_unexpected_source_ref(self):
        from langflow.api.v1.mappers.deployments.helpers import resolve_added_snapshot_bindings_for_update

        with pytest.raises(HTTPException, match="Unexpected source_ref in update snapshot bindings"):
            resolve_added_snapshot_bindings_for_update(
                deployment_mapper=_FakeMapper(),
                added_flow_version_ids=[uuid4()],
                result=DeploymentUpdateResult(
                    id="provider-id",
                    provider_result={
                        "added_snapshot_bindings": [
                            {"source_ref": "other", "snapshot_id": "snap-extra"},
                        ]
                    },
                ),
            )

    def test_resolve_added_snapshot_bindings_for_update_rejects_missing_expected_source_ref(self):
        from langflow.api.v1.mappers.deployments.helpers import resolve_added_snapshot_bindings_for_update

        with pytest.raises(HTTPException, match="Missing snapshot bindings for added flow versions"):
            resolve_added_snapshot_bindings_for_update(
                deployment_mapper=_FakeMapper(),
                added_flow_version_ids=[uuid4()],
                result=DeploymentUpdateResult(
                    id="provider-id",
                    provider_result={
                        "added_snapshot_bindings": [],
                    },
                ),
            )

    def test_resolve_snapshot_map_for_create_rejects_unexpected_source_ref(self):
        from langflow.api.v1.mappers.deployments.helpers import resolve_snapshot_map_for_create

        with pytest.raises(HTTPException, match="Unexpected source_ref"):
            resolve_snapshot_map_for_create(
                deployment_mapper=_FakeMapper(),
                result=DeploymentCreateResult(
                    id="provider-id",
                    provider_result={"snapshot_bindings": [{"source_ref": "other-ref", "snapshot_id": "snap-1"}]},
                ),
                flow_version_ids=[uuid4()],
            )


def test_watsonx_mapper_util_created_snapshot_ids_uses_adapter_slot():
    created = WatsonxOrchestrateDeploymentMapper().util_created_snapshot_ids(
        result=DeploymentUpdateResult(
            id="provider-id",
            provider_result={"created_snapshot_ids": ["snap-1", "snap-2"]},
        ),
    )

    assert created.ids == ["snap-1", "snap-2"]


def test_watsonx_mapper_extract_snapshot_bindings_from_provider_view():
    mapper = WatsonxOrchestrateDeploymentMapper()
    provider_view = _mock_provider_view(
        [
            SimpleNamespace(id="agent-1", provider_data={"tool_ids": ["tool-1", "tool-2"]}),
            SimpleNamespace(id="agent-2", provider_data={"tool_ids": ["tool-3"]}),
        ]
    )

    bindings = mapper.extract_snapshot_bindings(provider_view)
    assert [(binding.resource_key, binding.snapshot_id) for binding in bindings] == [
        ("agent-1", "tool-1"),
        ("agent-1", "tool-2"),
        ("agent-2", "tool-3"),
    ]


def test_watsonx_mapper_extract_snapshot_bindings_requires_tool_ids():
    mapper = WatsonxOrchestrateDeploymentMapper()
    provider_view = _mock_provider_view(
        [
            SimpleNamespace(id="agent-1", provider_data={}),
        ]
    )

    with pytest.raises(ValueError, match=r"^tool_ids is required from wxO adapter\.$"):
        mapper.extract_snapshot_bindings(provider_view)


def test_watsonx_mapper_extract_snapshot_bindings_allows_empty_tool_ids():
    mapper = WatsonxOrchestrateDeploymentMapper()
    provider_view = _mock_provider_view(
        [
            SimpleNamespace(id="agent-1", provider_data={"tool_ids": []}),
        ]
    )

    bindings = mapper.extract_snapshot_bindings(provider_view)
    assert bindings == []


def test_watsonx_mapper_extract_snapshot_bindings_requires_deployment_id():
    mapper = WatsonxOrchestrateDeploymentMapper()
    provider_view = _mock_provider_view(
        [
            SimpleNamespace(id=None, provider_data={"tool_ids": ["tool-ignored"]}),
        ]
    )

    with pytest.raises(ValueError, match=r"^deployment id is required from wxO adapter\.$"):
        mapper.extract_snapshot_bindings(provider_view)


def test_watsonx_mapper_extract_snapshot_bindings_for_get():
    mapper = WatsonxOrchestrateDeploymentMapper()
    get_result = DeploymentGetResult(
        id="agent-1",
        name="agent-name",
        type="agent",
        provider_data={"tool_ids": ["tool-1", "tool-2"]},
    )

    bindings = mapper.extract_snapshot_bindings_for_get(get_result, resource_key="agent-1")

    assert [(binding.resource_key, binding.snapshot_id) for binding in bindings] == [
        ("agent-1", "tool-1"),
        ("agent-1", "tool-2"),
    ]


def test_watsonx_mapper_extract_snapshot_bindings_for_get_requires_tool_ids():
    mapper = WatsonxOrchestrateDeploymentMapper()
    get_result = DeploymentGetResult(
        id="agent-1",
        name="agent-name",
        type="agent",
        provider_data={},
    )

    with pytest.raises(
        ValueError,
        match=r"^An internal error occured\. provider_data must contain 'tool_ids' from wxO adapter for get\(\)\.$",
    ):
        mapper.extract_snapshot_bindings_for_get(get_result, resource_key="agent-1")


def test_watsonx_mapper_extract_snapshot_bindings_for_get_requires_provider_data():
    mapper = WatsonxOrchestrateDeploymentMapper()
    get_result = DeploymentGetResult(
        id="agent-1",
        name="agent-name",
        type="agent",
        provider_data=None,
    )

    with pytest.raises(
        ValueError,
        match=r"^An internal error occured\. provider_data is required from wxO adapter for get\(\)\.$",
    ):
        mapper.extract_snapshot_bindings_for_get(get_result, resource_key="agent-1")


def test_watsonx_mapper_extract_snapshot_bindings_for_get_requires_tool_ids_list_type():
    mapper = WatsonxOrchestrateDeploymentMapper()
    get_result = DeploymentGetResult(
        id="agent-1",
        name="agent-name",
        type="agent",
        provider_data={"tool_ids": "tool-1"},
    )

    with pytest.raises(
        ValueError,
        match=(
            r"^An internal error occured\. provider_data\['tool_ids'\] must be a list "
            r"from wxO adapter for get\(\)\.$"
        ),
    ):
        mapper.extract_snapshot_bindings_for_get(get_result, resource_key="agent-1")


def test_watsonx_mapper_shape_deployment_get_data_hides_internal_sync_fields():
    mapper = WatsonxOrchestrateDeploymentMapper()

    shaped = mapper.shape_deployment_get_data(
        {
            "llm": "my-llm",
            "tool_ids": ["tool-1", "tool-2"],
        }
    )

    assert shaped == {"llm": "my-llm"}


def test_watsonx_mapper_shape_deployment_get_data_requires_provider_data():
    mapper = WatsonxOrchestrateDeploymentMapper()

    with pytest.raises(
        HTTPException,
        match=r"^500: An internal error occured\. provider_data is required from wxO adapter for get\(\)\.$",
    ):
        mapper.shape_deployment_get_data(None)


def test_base_mapper_extract_snapshot_bindings_for_get_raises_not_implemented():
    mapper = BaseDeploymentMapper()
    get_result = DeploymentGetResult(
        id="agent-1",
        name="agent-name",
        type="agent",
        provider_data={"tool_ids": ["tool-1"]},
    )

    with pytest.raises(NotImplementedError, match="extract_snapshot_bindings_for_get"):
        mapper.extract_snapshot_bindings_for_get(get_result, resource_key="agent-1")


def test_resolve_flow_version_patch_for_update_watsonx_operations():
    from langflow.api.v1.mappers.deployments.helpers import resolve_flow_version_patch_for_update

    add_id = uuid4()
    unbind_only_id = uuid4()
    remove_id = uuid4()
    add_ids, remove_ids = resolve_flow_version_patch_for_update(
        deployment_mapper=WatsonxOrchestrateDeploymentMapper(),
        payload=DeploymentUpdateRequest(
            provider_data={
                "llm": "test-llm",
                "upsert_flows": [
                    {
                        "flow_version_id": str(add_id),
                        "add_app_ids": ["app-one"],
                        "remove_app_ids": [],
                    },
                    {
                        "flow_version_id": str(unbind_only_id),
                        "add_app_ids": [],
                        "remove_app_ids": ["app-one"],
                    },
                ],
                "remove_flows": [str(remove_id)],
            }
        ),
    )

    assert add_ids == [add_id]
    assert remove_ids == [remove_id]


class _FakeCountExecResult:
    def __init__(self, count_value: int):
        self._count_value = count_value

    def one(self):
        return self._count_value


class _FakeCountDb:
    def __init__(self, count_value: int):
        self._count_value = count_value

    async def exec(self, _statement):
        return _FakeCountExecResult(self._count_value)


@pytest.mark.asyncio
async def test_validate_project_scoped_flow_version_ids_accepts_all_ids():
    from langflow.api.v1.mappers.deployments.helpers import validate_project_scoped_flow_version_ids

    flow_version_id = uuid4()
    await validate_project_scoped_flow_version_ids(
        flow_version_ids=[flow_version_id, flow_version_id],
        user_id=uuid4(),
        project_id=uuid4(),
        db=_FakeCountDb(count_value=1),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_validate_project_scoped_flow_version_ids_rejects_out_of_project_ids():
    from langflow.api.v1.mappers.deployments.helpers import validate_project_scoped_flow_version_ids

    with pytest.raises(HTTPException, match="selected project"):
        await validate_project_scoped_flow_version_ids(
            flow_version_ids=[uuid4(), uuid4()],
            user_id=uuid4(),
            project_id=uuid4(),
            db=_FakeCountDb(count_value=1),  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# fetch_provider_snapshot_keys
# ---------------------------------------------------------------------------


def _mock_snapshot_item(*, item_id: str, name: str = "irrelevant") -> SimpleNamespace:
    return SimpleNamespace(id=item_id, name=name)


def _mock_snapshot_view(items: list) -> SimpleNamespace:
    return SimpleNamespace(snapshots=items)


class TestFetchProviderSnapshotKeys:
    @pytest.mark.asyncio
    async def test_returns_recognized_snapshot_ids(self):
        adapter = AsyncMock()
        adapter.list_snapshots.return_value = _mock_snapshot_view(
            [_mock_snapshot_item(item_id="snap-1"), _mock_snapshot_item(item_id="snap-2")]
        )

        from langflow.api.v1.mappers.deployments.sync import fetch_provider_snapshot_keys

        result = await fetch_provider_snapshot_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            snapshot_ids=["snap-1", "snap-2", "snap-3"],
        )

        assert result == {"snap-1", "snap-2"}

    @pytest.mark.asyncio
    async def test_empty_snapshot_ids_returns_empty_set(self):
        adapter = AsyncMock()

        from langflow.api.v1.mappers.deployments.sync import fetch_provider_snapshot_keys

        result = await fetch_provider_snapshot_keys(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            snapshot_ids=[],
        )

        assert result == set()
        adapter.list_snapshots.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_provider_error_raises_500(self):
        adapter = AsyncMock()
        adapter.list_snapshots.side_effect = RuntimeError("provider down")

        from langflow.api.v1.mappers.deployments.sync import fetch_provider_snapshot_keys

        with pytest.raises(HTTPException) as exc_info:
            await fetch_provider_snapshot_keys(
                deployment_adapter=adapter,
                user_id=uuid4(),
                provider_id=uuid4(),
                db=AsyncMock(),
                snapshot_ids=["snap-1"],
            )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_falsy_snapshot_id_from_provider_raises_value_error(self):
        adapter = AsyncMock()
        adapter.list_snapshots.return_value = _mock_snapshot_view([_mock_snapshot_item(item_id="")])

        from langflow.api.v1.mappers.deployments.sync import fetch_provider_snapshot_keys

        with pytest.raises(ValueError, match="snapshot with an empty id"):
            await fetch_provider_snapshot_keys(
                deployment_adapter=adapter,
                user_id=uuid4(),
                provider_id=uuid4(),
                db=AsyncMock(),
                snapshot_ids=["snap-1"],
            )


# ---------------------------------------------------------------------------
# sync_attachment_snapshot_ids
# ---------------------------------------------------------------------------


def _mock_attachment(*, flow_version_id=None, provider_snapshot_id=None, deployment_id=None) -> SimpleNamespace:
    return SimpleNamespace(
        flow_version_id=flow_version_id or uuid4(),
        provider_snapshot_id=provider_snapshot_id,
        deployment_id=deployment_id or uuid4(),
    )


class TestSyncAttachmentSnapshotIds:
    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_deployment_attachments_by_keys", new_callable=AsyncMock)
    async def test_deletes_stale_attachments(self, mock_delete_att):
        """Attachments with snapshot IDs not in the known set are deleted."""
        dep_id = uuid4()
        uid = uuid4()
        fv_good = uuid4()
        fv_stale_a = uuid4()
        fv_stale_b = uuid4()
        attachments = [
            _mock_attachment(flow_version_id=fv_good, provider_snapshot_id="snap-good", deployment_id=dep_id),
            _mock_attachment(flow_version_id=fv_stale_a, provider_snapshot_id="snap-stale", deployment_id=dep_id),
            _mock_attachment(flow_version_id=fv_stale_b, provider_snapshot_id="snap-stale", deployment_id=dep_id),
        ]

        from langflow.api.v1.mappers.deployments.sync import sync_attachment_snapshot_ids

        counts = await sync_attachment_snapshot_ids(
            user_id=uid,
            attachments=attachments,
            known_snapshot_ids={"snap-good"},
            db=AsyncMock(),
        )

        assert counts[dep_id] == 1
        mock_delete_att.assert_awaited_once()
        call_kwargs = mock_delete_att.call_args.kwargs
        assert call_kwargs["user_id"] == uid
        key_batch = call_kwargs["attachment_key_batch"]
        key_pairs = [(key.deployment_id, key.flow_version_id) for key in key_batch.keys]
        assert key_pairs == [
            (dep_id, fv_stale_a),
            (dep_id, fv_stale_b),
        ]

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_deployment_attachments_by_keys", new_callable=AsyncMock)
    async def test_raises_on_falsy_snapshot_id(self, mock_delete_att):
        """Attachments with empty provider_snapshot_id raise data-integrity errors."""
        dep_id = uuid4()
        attachments = [
            _mock_attachment(provider_snapshot_id=None, deployment_id=dep_id),
            _mock_attachment(provider_snapshot_id="", deployment_id=dep_id),
        ]

        from langflow.api.v1.mappers.deployments.sync import sync_attachment_snapshot_ids

        with pytest.raises(ValueError, match="provider_snapshot_id must be non-empty"):
            await sync_attachment_snapshot_ids(
                user_id=uuid4(),
                attachments=attachments,
                known_snapshot_ids=set(),
                db=AsyncMock(),
            )
        mock_delete_att.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_deployment_attachments_by_keys", new_callable=AsyncMock)
    async def test_falsy_snapshot_short_circuits_before_batch_delete(self, mock_delete_att):
        """If any attachment has a falsy snapshot id, sync aborts before deleting stale keys."""
        dep_id = uuid4()
        attachments = [
            _mock_attachment(provider_snapshot_id="snap-known", deployment_id=dep_id),
            _mock_attachment(provider_snapshot_id="snap-stale", deployment_id=dep_id),
            _mock_attachment(provider_snapshot_id="   ", deployment_id=dep_id),
        ]

        from langflow.api.v1.mappers.deployments.sync import sync_attachment_snapshot_ids

        with pytest.raises(ValueError, match="provider_snapshot_id must be non-empty"):
            await sync_attachment_snapshot_ids(
                user_id=uuid4(),
                attachments=attachments,
                known_snapshot_ids={"snap-known"},
                db=AsyncMock(),
            )
        mock_delete_att.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_deployment_attachments_by_keys", new_callable=AsyncMock)
    async def test_all_snapshots_known_nothing_deleted(self, mock_delete_att):
        dep_id = uuid4()
        attachments = [
            _mock_attachment(provider_snapshot_id="snap-1", deployment_id=dep_id),
            _mock_attachment(provider_snapshot_id="snap-2", deployment_id=dep_id),
        ]

        from langflow.api.v1.mappers.deployments.sync import sync_attachment_snapshot_ids

        counts = await sync_attachment_snapshot_ids(
            user_id=uuid4(),
            attachments=attachments,
            known_snapshot_ids={"snap-1", "snap-2"},
            db=AsyncMock(),
        )

        assert counts[dep_id] == 2
        mock_delete_att.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_deployment_attachments_by_keys", new_callable=AsyncMock)
    async def test_extra_known_provider_snapshots_are_ignored(self, mock_delete_att):
        dep_id = uuid4()
        attachments = [
            _mock_attachment(provider_snapshot_id="snap-1", deployment_id=dep_id),
            _mock_attachment(provider_snapshot_id="snap-2", deployment_id=dep_id),
        ]

        from langflow.api.v1.mappers.deployments.sync import sync_attachment_snapshot_ids

        counts = await sync_attachment_snapshot_ids(
            user_id=uuid4(),
            attachments=attachments,
            known_snapshot_ids={"snap-1", "snap-2", "snap-extra"},
            db=AsyncMock(),
        )

        assert counts[dep_id] == 2
        mock_delete_att.assert_not_awaited()


# ---------------------------------------------------------------------------
# sync_flow_version_attachments
# ---------------------------------------------------------------------------


class TestSyncFlowVersionAttachments:
    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.get_deployment_adapter")
    @patch("langflow.api.v1.mappers.deployments.registry.get_deployment_mapper")
    @patch(f"{SYNC_MODULE}.list_deployments_for_flows_with_provider_info", new_callable=AsyncMock)
    async def test_snapshot_cleanup_runs_inside_savepoint(
        self,
        mock_list_rows,
        mock_get_mapper,
        mock_get_adapter,
        mock_fetch_resource_keys,
        mock_delete_unbound,
    ):
        """Binding cleanup is isolated so a failed best-effort sync cannot dirty the outer transaction."""
        deployment = _mock_deployment_row("rk-1")
        provider_view = _mock_provider_view([_mock_item(item_id="rk-1")])
        mock_list_rows.return_value = [(deployment, "watsonx-orchestrate")]
        mapper = MagicMock()
        mapper.extract_snapshot_bindings.return_value = []
        mock_get_mapper.return_value = mapper
        mock_get_adapter.return_value = AsyncMock()
        mock_fetch_resource_keys.return_value = ({"rk-1"}, provider_view)
        mock_delete_unbound.side_effect = RuntimeError("delete failed")

        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.sync import sync_flow_version_attachments

        await sync_flow_version_attachments(
            db=db,
            flow_id=uuid4(),
            user_id=uuid4(),
        )

        db.begin_nested.assert_called_once()
        mock_delete_unbound.assert_awaited_once()


# ---------------------------------------------------------------------------
# _sync_deployments_and_attachments_by_provider
# ---------------------------------------------------------------------------


class TestSyncDeploymentsAndAttachmentsByProvider:
    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_deployments_by_ids", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.get_deployment_adapter")
    @patch("langflow.api.v1.mappers.deployments.registry.get_deployment_mapper")
    async def test_batches_stale_deletions_once_per_provider_group(
        self,
        mock_get_mapper,
        mock_get_adapter,
        mock_fetch_resource_keys,
        mock_delete_unbound,
        mock_delete_deployments,
    ):
        provider_account_id = uuid4()
        stale_a = SimpleNamespace(
            id=uuid4(),
            resource_key="rk-stale-a",
            deployment_provider_account_id=provider_account_id,
        )
        stale_b = SimpleNamespace(
            id=uuid4(),
            resource_key="rk-stale-b",
            deployment_provider_account_id=provider_account_id,
        )
        surviving = SimpleNamespace(
            id=uuid4(),
            resource_key="rk-live",
            deployment_provider_account_id=provider_account_id,
        )
        provider_view = _mock_provider_view([_mock_item(item_id="rk-live")])
        mock_get_adapter.return_value = AsyncMock()
        mock_fetch_resource_keys.return_value = ({"rk-live"}, provider_view)
        mapper = MagicMock()
        mapper.extract_snapshot_bindings.return_value = ["binding-1"]
        mock_get_mapper.return_value = mapper

        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.sync import _sync_deployments_and_attachments_by_provider

        await _sync_deployments_and_attachments_by_provider(
            db=db,
            user_id=uuid4(),
            deployments_with_provider=[
                (stale_a, "watsonx-orchestrate"),
                (stale_b, "watsonx-orchestrate"),
                (surviving, "watsonx-orchestrate"),
            ],
            stale_scope_label="flow",
            failure_log_message="ignored",
            failure_scope_value=uuid4(),
        )

        mock_delete_deployments.assert_awaited_once()
        assert set(mock_delete_deployments.await_args.kwargs["deployment_ids"]) == {stale_a.id, stale_b.id}
        mock_delete_unbound.assert_awaited_once()
        assert mock_delete_unbound.await_args.kwargs["deployment_ids"] == [surviving.id]
        assert mock_delete_unbound.await_args.kwargs["bindings"] == ["binding-1"]


# ---------------------------------------------------------------------------
# provider-account scoped sync entry points
# ---------------------------------------------------------------------------


class TestProviderAccountScopedSync:
    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_orphan_attachments_for_flow_ids", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.list_deployments_for_flows_with_provider_info", new_callable=AsyncMock)
    async def test_sync_flow_deployment_state_returns_early_when_flow_ids_empty(
        self,
        mock_list_deployments,
        mock_delete_orphans,
    ):
        from langflow.api.v1.mappers.deployments.sync import sync_flow_deployment_state

        await sync_flow_deployment_state(
            db=AsyncMock(),
            flow_ids=[],
            user_id=uuid4(),
        )

        mock_delete_orphans.assert_not_awaited()
        mock_list_deployments.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_orphan_attachments_for_flow_ids", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}._sync_deployments_and_attachments_by_provider", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.list_deployments_for_flows_with_provider_info", new_callable=AsyncMock)
    async def test_sync_flow_deployment_state_deduplicates_flow_ids(
        self,
        mock_list_deployments,
        mock_sync_by_provider,
        mock_delete_orphans,
    ):
        from langflow.api.v1.mappers.deployments.sync import sync_flow_deployment_state

        flow_id = uuid4()
        mock_list_deployments.return_value = [(_mock_deployment_row("rk-1"), "watsonx-orchestrate")]

        await sync_flow_deployment_state(
            db=AsyncMock(),
            flow_ids=[flow_id, flow_id],
            user_id=uuid4(),
        )

        assert mock_delete_orphans.await_args.kwargs["flow_ids"] == [flow_id]
        assert mock_list_deployments.await_args.kwargs["flow_ids"] == [flow_id]
        mock_sync_by_provider.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_orphan_attachments_for_project", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}._sync_deployments_and_attachments_by_provider", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.list_project_deployments_with_provider_info", new_callable=AsyncMock, return_value=[])
    async def test_sync_project_deployments_returns_when_no_deployments(
        self,
        mock_list_deployments,
        mock_sync_by_provider,
        mock_delete_orphans,
    ):
        from langflow.api.v1.mappers.deployments.sync import sync_project_deployments

        project_id = uuid4()
        await sync_project_deployments(
            db=AsyncMock(),
            project_id=project_id,
            user_id=uuid4(),
        )

        mock_delete_orphans.assert_awaited_once()
        mock_list_deployments.assert_awaited_once()
        mock_sync_by_provider.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_orphan_attachments_for_flow_ids", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}._sync_deployments_and_attachments_by_provider", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.list_deployments_for_flows_with_provider_info", new_callable=AsyncMock)
    async def test_sync_flow_deployment_state_passes_provider_account_filter(
        self,
        mock_list_deployments,
        mock_sync_by_provider,
        mock_delete_orphans,
    ):
        from langflow.api.v1.mappers.deployments.sync import sync_flow_deployment_state

        provider_account_id = uuid4()
        mock_list_deployments.return_value = [(_mock_deployment_row("rk-1"), "watsonx-orchestrate")]
        await sync_flow_deployment_state(
            db=AsyncMock(),
            flow_ids=[uuid4()],
            user_id=uuid4(),
            deployment_provider_account_id=provider_account_id,
        )

        assert mock_list_deployments.call_args.kwargs["provider_account_id"] == provider_account_id
        mock_delete_orphans.assert_awaited_once()
        mock_sync_by_provider.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_orphan_attachments_for_flow_ids", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}._sync_deployments_and_attachments_by_provider", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.list_deployments_for_flows_with_provider_info", new_callable=AsyncMock)
    async def test_sync_flow_version_attachments_passes_provider_account_filter(
        self,
        mock_list_deployments,
        mock_sync_by_provider,
        mock_delete_orphans,
    ):
        from langflow.api.v1.mappers.deployments.sync import sync_flow_version_attachments

        provider_account_id = uuid4()
        mock_list_deployments.return_value = [(_mock_deployment_row("rk-1"), "watsonx-orchestrate")]
        await sync_flow_version_attachments(
            db=AsyncMock(),
            flow_id=uuid4(),
            user_id=uuid4(),
            deployment_provider_account_id=provider_account_id,
        )

        assert mock_list_deployments.call_args.kwargs["provider_account_id"] == provider_account_id
        mock_delete_orphans.assert_awaited_once()
        mock_sync_by_provider.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_orphan_attachments_for_project", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}._sync_deployments_and_attachments_by_provider", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.list_project_deployments_with_provider_info", new_callable=AsyncMock)
    async def test_sync_project_deployments_passes_provider_account_filter(
        self,
        mock_list_deployments,
        mock_sync_by_provider,
        mock_delete_orphans,
    ):
        from langflow.api.v1.mappers.deployments.sync import sync_project_deployments

        provider_account_id = uuid4()
        mock_list_deployments.return_value = [(_mock_deployment_row("rk-1"), "watsonx-orchestrate")]
        await sync_project_deployments(
            db=AsyncMock(),
            project_id=uuid4(),
            user_id=uuid4(),
            deployment_provider_account_id=provider_account_id,
        )

        assert mock_list_deployments.call_args.kwargs["provider_account_id"] == provider_account_id
        mock_delete_orphans.assert_awaited_once()
        mock_sync_by_provider.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_orphan_attachments_for_flow_ids", new_callable=AsyncMock, side_effect=Exception("db"))
    @patch(f"{SYNC_MODULE}._sync_deployments_and_attachments_by_provider", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.list_deployments_for_flows_with_provider_info", new_callable=AsyncMock)
    async def test_sync_flow_deployment_state_continues_when_orphan_cleanup_fails(
        self,
        mock_list_deployments,
        mock_sync_by_provider,
        mock_delete_orphans,
    ):
        from langflow.api.v1.mappers.deployments.sync import sync_flow_deployment_state

        mock_list_deployments.return_value = [(_mock_deployment_row("rk-1"), "watsonx-orchestrate")]
        await sync_flow_deployment_state(
            db=AsyncMock(),
            flow_ids=[uuid4()],
            user_id=uuid4(),
        )

        mock_delete_orphans.assert_awaited_once()
        mock_sync_by_provider.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_orphan_attachments_for_flow_ids", new_callable=AsyncMock, side_effect=Exception("db"))
    @patch(f"{SYNC_MODULE}._sync_deployments_and_attachments_by_provider", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.list_deployments_for_flows_with_provider_info", new_callable=AsyncMock)
    async def test_sync_flow_version_attachments_continues_when_orphan_cleanup_fails(
        self,
        mock_list_deployments,
        mock_sync_by_provider,
        mock_delete_orphans,
    ):
        from langflow.api.v1.mappers.deployments.sync import sync_flow_version_attachments

        mock_list_deployments.return_value = [(_mock_deployment_row("rk-1"), "watsonx-orchestrate")]
        await sync_flow_version_attachments(
            db=AsyncMock(),
            flow_id=uuid4(),
            user_id=uuid4(),
        )

        mock_delete_orphans.assert_awaited_once()
        mock_sync_by_provider.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{SYNC_MODULE}.delete_orphan_attachments_for_project", new_callable=AsyncMock, side_effect=Exception("db"))
    @patch(f"{SYNC_MODULE}._sync_deployments_and_attachments_by_provider", new_callable=AsyncMock)
    @patch(f"{SYNC_MODULE}.list_project_deployments_with_provider_info", new_callable=AsyncMock)
    async def test_sync_project_deployments_continues_when_orphan_cleanup_fails(
        self,
        mock_list_deployments,
        mock_sync_by_provider,
        mock_delete_orphans,
    ):
        from langflow.api.v1.mappers.deployments.sync import sync_project_deployments

        mock_list_deployments.return_value = [(_mock_deployment_row("rk-1"), "watsonx-orchestrate")]
        await sync_project_deployments(
            db=AsyncMock(),
            project_id=uuid4(),
            user_id=uuid4(),
        )

        mock_delete_orphans.assert_awaited_once()
        mock_sync_by_provider.assert_awaited_once()


# ---------------------------------------------------------------------------
# rollback_provider_create
# ---------------------------------------------------------------------------


class TestRollbackProviderCreate:
    @pytest.mark.asyncio
    async def test_calls_adapter_delete(self):
        """Compensating delete is called with the provider resource ID."""
        adapter = AsyncMock()

        from langflow.api.v1.mappers.deployments.helpers import rollback_provider_create

        await rollback_provider_create(
            deployment_adapter=adapter,
            provider_id=uuid4(),
            resource_id="provider-resource-123",
            user_id=uuid4(),
            db=AsyncMock(),
        )

        adapter.delete.assert_awaited_once()
        assert adapter.delete.call_args.kwargs["deployment_id"] == "provider-resource-123"

    @pytest.mark.asyncio
    async def test_uses_extended_provider_result_rollback_when_available(self):
        """Adapters can clean up create-time side resources before falling back to delete."""
        adapter = AsyncMock()

        from langflow.api.v1.mappers.deployments.helpers import rollback_provider_create

        provider_result = {"app_ids": ["app-1"], "tools_with_refs": [{"tool_id": "tool-1", "source_ref": "fv-1"}]}

        await rollback_provider_create(
            deployment_adapter=adapter,
            provider_id=uuid4(),
            resource_id="provider-resource-123",
            provider_result=provider_result,
            user_id=uuid4(),
            db=AsyncMock(),
        )

        adapter.rollback_create_result.assert_awaited_once()
        assert adapter.rollback_create_result.call_args.kwargs["provider_result"] == provider_result
        adapter.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_delete_when_extended_rollback_fails(self):
        """If the extended cleanup path fails, the helper still attempts the basic delete."""
        adapter = AsyncMock()
        adapter.rollback_create_result.side_effect = RuntimeError("rollback boom")

        from langflow.api.v1.mappers.deployments.helpers import rollback_provider_create

        await rollback_provider_create(
            deployment_adapter=adapter,
            provider_id=uuid4(),
            resource_id="provider-resource-123",
            provider_result={"app_ids": ["app-1"]},
            user_id=uuid4(),
            db=AsyncMock(),
        )

        adapter.rollback_create_result.assert_awaited_once()
        adapter.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_swallows_delete_failure(self):
        """If the compensating delete fails, exception is swallowed (logged)."""
        adapter = AsyncMock()
        adapter.delete.side_effect = RuntimeError("provider unreachable")

        from langflow.api.v1.mappers.deployments.helpers import rollback_provider_create

        # Should not raise
        await rollback_provider_create(
            deployment_adapter=adapter,
            provider_id=uuid4(),
            resource_id="orphaned-resource",
            user_id=uuid4(),
            db=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_skips_delete_fallback_when_disabled_and_extended_rollback_fails(self):
        """When delete fallback is disabled, extended rollback failures do not trigger delete."""
        adapter = AsyncMock()
        adapter.rollback_create_result.side_effect = RuntimeError("rollback boom")

        from langflow.api.v1.mappers.deployments.helpers import rollback_provider_create

        await rollback_provider_create(
            deployment_adapter=adapter,
            provider_id=uuid4(),
            resource_id="existing-resource-1",
            provider_result={"app_ids": ["app-1"]},
            allow_delete_fallback=False,
            user_id=uuid4(),
            db=AsyncMock(),
        )

        adapter.rollback_create_result.assert_awaited_once()
        adapter.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# rollback_provider_update
# ---------------------------------------------------------------------------


class TestRollbackProviderUpdate:
    @pytest.mark.asyncio
    async def test_returns_early_when_mapper_returns_none(self):
        """When the mapper cannot build a rollback payload, no adapter call is made."""
        adapter = AsyncMock()
        mapper = AsyncMock(spec=BaseDeploymentMapper)
        mapper.resolve_rollback_update = AsyncMock(return_value=None)
        dep_row = _mock_deployment_row("rk-1")

        from langflow.api.v1.mappers.deployments.helpers import rollback_provider_update

        await rollback_provider_update(
            deployment_adapter=adapter,
            deployment_mapper=mapper,
            deployment_db_id=dep_row.id,
            deployment_resource_key=dep_row.resource_key,
            deployment_provider_account_id=dep_row.deployment_provider_account_id,
            user_id=uuid4(),
            db=AsyncMock(),
        )

        adapter.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_calls_adapter_update_with_rollback_payload(self):
        """When mapper returns a payload, compensating update is issued."""
        adapter = AsyncMock()
        rollback_payload = MagicMock()
        mapper = AsyncMock(spec=BaseDeploymentMapper)
        mapper.resolve_rollback_update = AsyncMock(return_value=rollback_payload)
        dep_row = _mock_deployment_row("rk-1")
        dep_row.deployment_provider_account_id = uuid4()

        from langflow.api.v1.mappers.deployments.helpers import rollback_provider_update

        await rollback_provider_update(
            deployment_adapter=adapter,
            deployment_mapper=mapper,
            deployment_db_id=dep_row.id,
            deployment_resource_key=dep_row.resource_key,
            deployment_provider_account_id=dep_row.deployment_provider_account_id,
            user_id=uuid4(),
            db=AsyncMock(),
        )

        adapter.update.assert_awaited_once()
        assert adapter.update.call_args.kwargs["payload"] is rollback_payload

    @pytest.mark.asyncio
    async def test_swallows_adapter_update_failure(self):
        """If the compensating update fails, exception is swallowed."""
        adapter = AsyncMock()
        adapter.update.side_effect = RuntimeError("provider error")
        mapper = AsyncMock(spec=BaseDeploymentMapper)
        mapper.resolve_rollback_update = AsyncMock(return_value=MagicMock())
        dep_row = _mock_deployment_row("rk-1")
        dep_row.deployment_provider_account_id = uuid4()

        from langflow.api.v1.mappers.deployments.helpers import rollback_provider_update

        # Should not raise
        await rollback_provider_update(
            deployment_adapter=adapter,
            deployment_mapper=mapper,
            deployment_db_id=dep_row.id,
            deployment_resource_key=dep_row.resource_key,
            deployment_provider_account_id=dep_row.deployment_provider_account_id,
            user_id=uuid4(),
            db=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_swallows_mapper_failure(self):
        """If mapper.resolve_rollback_update raises, exception is swallowed."""
        adapter = AsyncMock()
        mapper = AsyncMock(spec=BaseDeploymentMapper)
        mapper.resolve_rollback_update = AsyncMock(side_effect=RuntimeError("mapper error"))
        dep_row = _mock_deployment_row("rk-1")

        from langflow.api.v1.mappers.deployments.helpers import rollback_provider_update

        # Should not raise
        await rollback_provider_update(
            deployment_adapter=adapter,
            deployment_mapper=mapper,
            deployment_db_id=dep_row.id,
            deployment_resource_key=dep_row.resource_key,
            deployment_provider_account_id=dep_row.deployment_provider_account_id,
            user_id=uuid4(),
            db=AsyncMock(),
        )

        adapter.update.assert_not_awaited()


# ---------------------------------------------------------------------------
# WatsonxOrchestrateDeploymentMapper.resolve_rollback_update
# ---------------------------------------------------------------------------


DEP_CRUD_MODULE = "langflow.services.database.models.deployment.crud"
ATT_CRUD_MODULE = "langflow.services.database.models.flow_version_deployment_attachment.crud"


class TestWxoResolveRollbackUpdate:
    @pytest.mark.asyncio
    @patch(f"{ATT_CRUD_MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{DEP_CRUD_MODULE}.get_deployment", new_callable=AsyncMock)
    async def test_returns_none_when_deployment_not_found(self, mock_get_dep, mock_list_att):
        """If the deployment row no longer exists, returns None."""
        mock_get_dep.return_value = None
        mapper = WatsonxOrchestrateDeploymentMapper()

        result = await mapper.resolve_rollback_update(
            user_id=uuid4(),
            deployment_db_id=uuid4(),
            deployment_resource_key="rk-1",
            db=AsyncMock(),
        )

        assert result is None
        mock_list_att.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{ATT_CRUD_MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{DEP_CRUD_MODULE}.get_deployment", new_callable=AsyncMock)
    async def test_builds_put_tools_from_attachment_snapshot_ids(self, mock_get_dep, mock_list_att):
        """Rollback payload contains put_tools with provider_snapshot_ids from DB attachments.

        att3/att4 simulate legacy rows that may still have NULL/blank snapshot IDs
        in the DB from before the non-empty invariant was enforced at the app level.
        """
        dep = MagicMock()
        dep.name = "test-dep"
        dep.description = "desc"
        mock_get_dep.return_value = dep

        att1 = MagicMock()
        att1.provider_snapshot_id = "tool-1"
        att2 = MagicMock()
        att2.provider_snapshot_id = "tool-2"
        att3 = MagicMock()
        att3.provider_snapshot_id = None
        att4 = MagicMock()
        att4.provider_snapshot_id = "  "
        mock_list_att.return_value = [att1, att2, att3, att4]

        mapper = WatsonxOrchestrateDeploymentMapper()

        result = await mapper.resolve_rollback_update(
            user_id=uuid4(),
            deployment_db_id=uuid4(),
            deployment_resource_key="rk-1",
            db=AsyncMock(),
        )

        assert result is not None
        assert result.spec is not None
        assert result.spec.name == "test-dep"
        assert result.spec.description == "desc"
        provider_data = result.provider_data
        assert provider_data["put_tools"] == ["tool-1", "tool-2"]

    @pytest.mark.asyncio
    @patch(f"{ATT_CRUD_MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    @patch(f"{DEP_CRUD_MODULE}.get_deployment", new_callable=AsyncMock)
    async def test_empty_attachments_produces_empty_put_tools(self, mock_get_dep, mock_list_att):
        """When no attachments exist, put_tools is an empty list (clears all tools)."""
        dep = MagicMock()
        dep.name = "test-dep"
        dep.description = None
        mock_get_dep.return_value = dep
        mock_list_att.return_value = []

        mapper = WatsonxOrchestrateDeploymentMapper()

        result = await mapper.resolve_rollback_update(
            user_id=uuid4(),
            deployment_db_id=uuid4(),
            deployment_resource_key="rk-1",
            db=AsyncMock(),
        )

        assert result is not None
        assert result.provider_data["put_tools"] == []
        assert result.spec is not None
        assert result.spec.description == ""


# ---------------------------------------------------------------------------
# list_deployments_synced: phase-2 binding sync
# ---------------------------------------------------------------------------


class TestListDeploymentsSyncedBindingPhase:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.count_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_binding_sync_corrects_attached_count(
        self,
        mock_list,
        mock_fetch_rk,
        mock_delete_unbound,
        mock_count_attachments,
        mock_count,  # noqa: ARG002
    ):
        """Phase 2 corrects attached_count using binding-level cleanup + recount."""
        row = _mock_deployment_row("rk-1")
        mock_list.side_effect = [[(row, 3, [])], []]
        mock_fetch_rk.return_value = (
            {"rk-1"},
            _mock_provider_view([SimpleNamespace(id="rk-1", provider_data={"tool_ids": ["snap-1"]})]),
        )
        mock_count_attachments.return_value = {row.id: 2}
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=WatsonxOrchestrateDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=db,
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 1
        assert accepted[0][1] == 2
        db.begin_nested.assert_called_once()
        mock_delete_unbound.assert_awaited_once()
        mock_count_attachments.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.count_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_binding_cleanup_runs_with_empty_bindings(
        self,
        mock_list,
        mock_fetch_rk,
        mock_delete_unbound,
        mock_count_attachments,
        mock_count,  # noqa: ARG002
    ):
        """Phase 2 still runs when mapper extracts no bindings."""
        row = _mock_deployment_row("rk-1")
        mock_list.side_effect = [[(row, 0, [])], []]
        mock_fetch_rk.return_value = (
            {"rk-1"},
            _mock_provider_view([SimpleNamespace(id="rk-1", provider_data={"tool_ids": []})]),
        )
        mock_count_attachments.return_value = {row.id: 0}
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()
        provider_id = uuid4()

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=WatsonxOrchestrateDeploymentMapper(),
            user_id=uuid4(),
            provider_id=provider_id,
            db=db,
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 1
        mock_delete_unbound.assert_awaited_once()
        assert mock_delete_unbound.await_args.kwargs["bindings"] == []
        assert mock_delete_unbound.await_args.kwargs["provider_account_id"] == provider_id
        mock_count_attachments.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.count_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_binding_sync_error_preserves_original_counts(
        self,
        mock_list,
        mock_fetch_rk,
        mock_delete_unbound,
        mock_count_attachments,
        mock_count,  # noqa: ARG002
    ):
        """When Phase 2 raises, accepted rows keep their original attached_count."""
        row = _mock_deployment_row("rk-1")
        mock_list.side_effect = [[(row, 3, [])], []]
        mock_fetch_rk.return_value = (
            {"rk-1"},
            _mock_provider_view([SimpleNamespace(id="rk-1", provider_data={"tool_ids": ["snap-1"]})]),
        )
        mock_delete_unbound.side_effect = RuntimeError("cleanup failed")
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=WatsonxOrchestrateDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=db,
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 1
        assert accepted[0][1] == 3
        mock_count_attachments.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.count_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.delete_unbound_attachments", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_binding_cleanup_runs_inside_savepoint(
        self,
        mock_list,
        mock_fetch_rk,
        mock_delete_unbound,
        mock_count_attachments,
        mock_count,  # noqa: ARG002
    ):
        """Phase 2 cleanup uses a savepoint so failures don't leak partial writes."""
        row = _mock_deployment_row("rk-1")
        mock_list.side_effect = [[(row, 3, [])], []]
        mock_fetch_rk.return_value = (
            {"rk-1"},
            _mock_provider_view([SimpleNamespace(id="rk-1", provider_data={"tool_ids": ["snap-1"]})]),
        )
        mock_count_attachments.return_value = {row.id: 3}
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=WatsonxOrchestrateDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=db,
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 1
        assert accepted[0][1] == 3
        db.begin_nested.assert_called_once()
        mock_delete_unbound.assert_awaited_once()


# ---------------------------------------------------------------------------
# list_deployment_flow_versions_synced
# ---------------------------------------------------------------------------


class TestListDeploymentFlowVersionsSynced:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployment_attachments", new_callable=AsyncMock, return_value=2)
    @patch(f"{MODULE}.list_deployment_attachments_with_versions", new_callable=AsyncMock)
    @patch(f"{MODULE}.sync_attachment_snapshot_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    async def test_syncs_snapshots_with_snapshot_ids_and_returns_enrichment(
        self,
        mock_list_attachments,
        mock_sync_snapshot_ids,
        mock_list_with_versions,
        mock_count_attachments,
    ):
        deployment_id = uuid4()
        attachments = [
            _mock_attachment(provider_snapshot_id="snap-1", deployment_id=deployment_id),
            _mock_attachment(provider_snapshot_id="snap-stale", deployment_id=deployment_id),
        ]
        mock_list_attachments.return_value = attachments
        rows = [(SimpleNamespace(provider_snapshot_id="snap-1"), SimpleNamespace())]
        mock_list_with_versions.return_value = rows

        adapter = AsyncMock()
        adapter.list_snapshots.return_value = SnapshotListResult(
            snapshots=[
                SnapshotItem(
                    id="snap-1",
                    name="tool-1",
                    provider_data={"connections": {"cfg-1": "conn-1"}},
                )
            ]
        )
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.helpers import list_deployment_flow_versions_synced

        out_rows, total, snapshot_result = await list_deployment_flow_versions_synced(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            deployment_id=deployment_id,
            db=db,
            page=2,
            size=3,
        )

        assert out_rows == rows
        assert total == 2
        assert isinstance(snapshot_result, SnapshotListResult)
        assert [snapshot.id for snapshot in snapshot_result.snapshots] == ["snap-1"]
        adapter.list_snapshots.assert_awaited_once()
        adapter_params = adapter.list_snapshots.call_args.kwargs["params"]
        assert adapter_params.snapshot_ids == ["snap-1", "snap-stale"]
        mock_sync_snapshot_ids.assert_awaited_once()
        assert mock_sync_snapshot_ids.call_args.kwargs["known_snapshot_ids"] == {"snap-1"}
        assert mock_list_with_versions.call_args.kwargs["offset"] == 3
        assert mock_list_with_versions.call_args.kwargs["limit"] == 3
        mock_count_attachments.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployment_attachments", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.list_deployment_attachments_with_versions", new_callable=AsyncMock)
    @patch(f"{MODULE}.sync_attachment_snapshot_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    async def test_fails_fast_when_attachment_snapshot_ids_are_falsy(
        self,
        mock_list_attachments,
        mock_sync_snapshot_ids,
        mock_list_with_versions,
        mock_count_attachments,
    ):
        deployment_id = uuid4()
        attachments = [
            _mock_attachment(provider_snapshot_id=None, deployment_id=deployment_id),
            _mock_attachment(provider_snapshot_id="", deployment_id=deployment_id),
        ]
        mock_list_attachments.return_value = attachments

        adapter = AsyncMock()

        from langflow.api.v1.mappers.deployments.helpers import list_deployment_flow_versions_synced

        with pytest.raises(ValueError, match="provider_snapshot_id must be non-empty"):
            await list_deployment_flow_versions_synced(
                deployment_adapter=adapter,
                user_id=uuid4(),
                provider_id=uuid4(),
                deployment_id=deployment_id,
                db=AsyncMock(),
                page=1,
                size=10,
            )
        adapter.list_snapshots.assert_not_awaited()
        mock_sync_snapshot_ids.assert_not_awaited()
        mock_count_attachments.assert_not_awaited()
        mock_list_with_versions.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployment_attachments", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.list_deployment_attachments_with_versions", new_callable=AsyncMock)
    @patch(f"{MODULE}.sync_attachment_snapshot_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    async def test_snapshot_sync_savepoint_failure_clears_enrichment_payload(
        self,
        mock_list_attachments,
        mock_sync_snapshot_ids,
        mock_list_with_versions,
        mock_count_attachments,
    ):
        deployment_id = uuid4()
        mock_list_attachments.return_value = [
            _mock_attachment(provider_snapshot_id="snap-1", deployment_id=deployment_id)
        ]
        rows = [(SimpleNamespace(provider_snapshot_id="snap-1"), SimpleNamespace())]
        mock_list_with_versions.return_value = rows

        adapter = AsyncMock()
        adapter.list_snapshots.return_value = SnapshotListResult(
            snapshots=[
                SnapshotItem(
                    id="snap-1",
                    name="tool-1",
                    provider_data={"connections": {"cfg-1": "conn-1"}},
                )
            ]
        )
        mock_sync_snapshot_ids.side_effect = RuntimeError("savepoint failed")
        db = MagicMock()
        db.begin_nested.return_value = _AsyncNoopSavepoint()

        from langflow.api.v1.mappers.deployments.helpers import list_deployment_flow_versions_synced

        out_rows, total, snapshot_result = await list_deployment_flow_versions_synced(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            deployment_id=deployment_id,
            db=db,
            page=1,
            size=20,
        )

        assert out_rows == rows
        assert total == 1
        assert snapshot_result is None
        adapter.list_snapshots.assert_awaited_once()
        mock_sync_snapshot_ids.assert_awaited_once()
        mock_count_attachments.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployment_attachments", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.list_deployment_attachments_with_versions", new_callable=AsyncMock)
    @patch(f"{MODULE}.sync_attachment_snapshot_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    async def test_snapshot_sync_errors_fall_back_to_db_rows_without_enrichment(
        self,
        mock_list_attachments,
        mock_sync_snapshot_ids,
        mock_list_with_versions,
        mock_count_attachments,
    ):
        deployment_id = uuid4()
        mock_list_attachments.return_value = [
            _mock_attachment(provider_snapshot_id="snap-1", deployment_id=deployment_id)
        ]
        rows = [(SimpleNamespace(provider_snapshot_id="snap-1"), SimpleNamespace())]
        mock_list_with_versions.return_value = rows

        adapter = AsyncMock()
        adapter.list_snapshots.side_effect = RuntimeError("provider down")
        from langflow.api.v1.mappers.deployments.helpers import list_deployment_flow_versions_synced

        out_rows, total, snapshot_result = await list_deployment_flow_versions_synced(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            deployment_id=deployment_id,
            db=AsyncMock(),
            page=1,
            size=20,
        )

        assert out_rows == rows
        assert total == 1
        assert snapshot_result is None
        mock_sync_snapshot_ids.assert_not_awaited()
        mock_count_attachments.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployment_attachments", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.list_deployment_attachments_with_versions", new_callable=AsyncMock, return_value=[])
    @patch(f"{MODULE}.list_deployment_attachments", new_callable=AsyncMock, return_value=[])
    async def test_forwards_flow_ids_filter_to_attachment_queries(
        self,
        mock_list_attachments,
        mock_list_with_versions,
        mock_count_attachments,
    ):
        deployment_id = uuid4()
        flow_id = uuid4()
        adapter = AsyncMock()
        from langflow.api.v1.mappers.deployments.helpers import list_deployment_flow_versions_synced

        await list_deployment_flow_versions_synced(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            deployment_id=deployment_id,
            db=AsyncMock(),
            page=1,
            size=10,
            flow_ids=[flow_id],
        )

        assert mock_list_attachments.call_args.kwargs["flow_ids"] == [flow_id]
        assert mock_list_with_versions.call_args.kwargs["flow_ids"] == [flow_id]
        assert mock_count_attachments.call_args.kwargs["flow_ids"] == [flow_id]

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployment_attachments", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.list_deployment_attachments_with_versions", new_callable=AsyncMock)
    @patch(f"{MODULE}.sync_attachment_snapshot_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployment_attachments", new_callable=AsyncMock)
    async def test_provider_snapshot_result_with_falsy_id_falls_back_without_enrichment(
        self,
        mock_list_attachments,
        mock_sync_snapshot_ids,
        mock_list_with_versions,
        mock_count_attachments,
    ):
        deployment_id = uuid4()
        mock_list_attachments.return_value = [
            _mock_attachment(provider_snapshot_id="snap-1", deployment_id=deployment_id)
        ]
        rows = [(SimpleNamespace(provider_snapshot_id="snap-1"), SimpleNamespace())]
        mock_list_with_versions.return_value = rows
        adapter = AsyncMock()
        adapter.list_snapshots.return_value = _mock_snapshot_view([_mock_snapshot_item(item_id="")])

        from langflow.api.v1.mappers.deployments.helpers import list_deployment_flow_versions_synced

        out_rows, total, snapshot_result = await list_deployment_flow_versions_synced(
            deployment_adapter=adapter,
            user_id=uuid4(),
            provider_id=uuid4(),
            deployment_id=deployment_id,
            db=AsyncMock(),
            page=1,
            size=20,
        )

        assert out_rows == rows
        assert total == 1
        assert snapshot_result is None
        adapter.list_snapshots.assert_awaited_once()
        mock_sync_snapshot_ids.assert_not_awaited()
        mock_list_with_versions.assert_awaited_once()
        mock_count_attachments.assert_awaited_once()


# ---------------------------------------------------------------------------
# flow_version_deployment_attachment CRUD helpers
# ---------------------------------------------------------------------------


class _FakeAllResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeOneResult:
    def __init__(self, value):
        self._value = value

    def one(self):
        return self._value


class _CaptureDb:
    def __init__(self, result):
        self._result = result
        self.statements = []

    async def exec(self, statement):
        self.statements.append(statement)
        return self._result


class TestFlowVersionDeploymentAttachmentCrud:
    @pytest.mark.asyncio
    async def test_list_deployment_attachments_with_versions_orders_by_attachment_timestamps(self):
        from langflow.services.database.models.flow_version_deployment_attachment.crud import (
            list_deployment_attachments_with_versions,
        )

        rows = [(SimpleNamespace(), SimpleNamespace())]
        db = _CaptureDb(_FakeAllResult(rows))

        result = await list_deployment_attachments_with_versions(
            db,
            user_id=uuid4(),
            deployment_id=uuid4(),
            offset=5,
            limit=10,
        )

        assert result == rows
        statement_text = str(db.statements[0]).lower()
        assert "order by" in statement_text
        assert "created_at desc" in statement_text
        assert "updated_at desc" in statement_text

    @pytest.mark.asyncio
    async def test_list_deployment_attachments_with_versions_skips_query_when_limit_non_positive(self):
        from langflow.services.database.models.flow_version_deployment_attachment.crud import (
            list_deployment_attachments_with_versions,
        )

        db = _CaptureDb(_FakeAllResult([]))
        result = await list_deployment_attachments_with_versions(
            db,
            user_id=uuid4(),
            deployment_id=uuid4(),
            offset=0,
            limit=0,
        )

        assert result == []
        assert db.statements == []

    @pytest.mark.asyncio
    async def test_count_deployment_attachments_returns_scalar_count(self):
        from langflow.services.database.models.flow_version_deployment_attachment.crud import (
            count_deployment_attachments,
        )

        db = _CaptureDb(_FakeOneResult(4))

        total = await count_deployment_attachments(
            db,
            user_id=uuid4(),
            deployment_id=uuid4(),
        )

        assert total == 4
        assert len(db.statements) == 1
        # String-match on compiled SQL because these tests use captured
        # statement objects without a real database engine.
        statement_text = str(db.statements[0]).lower()
        assert "join flow_version" in statement_text

    @pytest.mark.asyncio
    async def test_count_attachments_by_deployment_ids_joins_flow_version(self):
        from langflow.services.database.models.flow_version_deployment_attachment.crud import (
            count_attachments_by_deployment_ids,
        )

        deployment_id = uuid4()
        db = _CaptureDb(_FakeAllResult([]))
        counts = await count_attachments_by_deployment_ids(
            db,
            user_id=uuid4(),
            deployment_ids=[deployment_id],
        )

        assert counts == {deployment_id: 0}
        assert len(db.statements) == 1
        statement_text = str(db.statements[0]).lower()
        assert "join flow_version" in statement_text

    @pytest.mark.asyncio
    async def test_delete_orphan_attachments_for_flow_ids_joins_flow_version_and_deployment(self):
        from langflow.services.database.models.flow_version_deployment_attachment.crud import (
            delete_orphan_attachments_for_flow_ids,
        )

        db = _CaptureDb(SimpleNamespace(rowcount=2))
        deleted = await delete_orphan_attachments_for_flow_ids(
            db,
            user_id=uuid4(),
            flow_ids=[uuid4()],
        )

        assert deleted == 2
        statement_text = str(db.statements[0]).lower()
        assert "delete from flow_version_deployment_attachment" in statement_text
        assert "join flow_version" in statement_text
        assert "join deployment" in statement_text

    @pytest.mark.asyncio
    async def test_delete_orphan_attachments_for_project_joins_flow_scope_and_deployment(self):
        from langflow.services.database.models.flow_version_deployment_attachment.crud import (
            delete_orphan_attachments_for_project,
        )

        db = _CaptureDb(SimpleNamespace(rowcount=1))
        deleted = await delete_orphan_attachments_for_project(
            db,
            user_id=uuid4(),
            project_id=uuid4(),
        )

        assert deleted == 1
        statement_text = str(db.statements[0]).lower()
        assert "delete from flow_version_deployment_attachment" in statement_text
        assert "join flow_version" in statement_text
        assert "join flow" in statement_text
        assert "join deployment" in statement_text

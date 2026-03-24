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
from langflow.api.v1.mappers.deployments.watsonx_orchestrate import WatsonxOrchestrateDeploymentMapper
from langflow.api.v1.schemas.deployments import DeploymentUpdateRequest
from lfx.services.adapters.deployment.schema import DeploymentCreateResult, DeploymentUpdateResult

MODULE = "langflow.api.v1.mappers.deployments.helpers"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_item(*, item_id: str, name: str = "irrelevant") -> SimpleNamespace:
    return SimpleNamespace(id=item_id, name=name)


def _mock_provider_view(items: list) -> SimpleNamespace:
    return SimpleNamespace(deployments=items)


def _mock_deployment_row(resource_key: str, deployment_type: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), resource_key=resource_key, deployment_type=deployment_type)


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

        result = await fetch_provider_resource_keys(
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
        adapter.list.return_value = _mock_provider_view(
            [
                _mock_item(item_id="different", name="rk-1"),
            ]
        )

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        result = await fetch_provider_resource_keys(
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
        adapter.list.return_value = _mock_provider_view(
            [
                _mock_item(item_id="rk-1"),
                _mock_item(item_id=""),  # falsy id
            ]
        )

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        result = await fetch_provider_resource_keys(
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

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        result = await fetch_provider_resource_keys(
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

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_resource_keys

        with pytest.raises(HTTPException) as exc_info:
            await fetch_provider_resource_keys(
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
        assert params.provider_params == {"ids": keys}
        assert params.deployment_types is None

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
    @patch(f"{MODULE}.list_attachments_by_deployment_ids", new_callable=AsyncMock, return_value=[])
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_keeps_provider_confirmed_rows(self, mock_list, mock_fetch, mock_list_att, mock_count):  # noqa: ARG002
        """Rows whose resource_key is in the provider's known set are kept."""
        row1 = _mock_deployment_row("rk-1")
        row2 = _mock_deployment_row("rk-2")
        mock_list.side_effect = [[(row1, 0, []), (row2, 1, ["fv-1"])], []]
        mock_fetch.return_value = {"rk-1", "rk-2"}

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

        assert len(accepted) == 2
        assert accepted[0][0] is row1
        assert accepted[1][0] is row2
        assert total == 2
        mock_count.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.list_attachments_by_deployment_ids", new_callable=AsyncMock, return_value=[])
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_deletes_stale_rows(self, mock_list, mock_fetch, mock_delete, mock_list_att, mock_count):  # noqa: ARG002
        """Rows not recognised by the provider are deleted."""
        stale_row = _mock_deployment_row("rk-stale")
        good_row = _mock_deployment_row("rk-good")
        uid = uuid4()
        db = AsyncMock()

        # First call returns stale + good; second call returns empty (all consumed)
        mock_list.side_effect = [
            [(stale_row, 0, []), (good_row, 1, [])],
            [],
        ]
        mock_fetch.return_value = {"rk-good"}  # only rk-good is known

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
    @patch(f"{MODULE}.list_attachments_by_deployment_ids", new_callable=AsyncMock, return_value=[])
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_mismatched_type_not_in_known_skips_without_deleting(
        self,
        mock_list,
        mock_fetch,
        mock_delete,
        mock_list_att,  # noqa: ARG002
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
        mock_fetch.return_value = {"rk-1"}

        from langflow.api.v1.mappers.deployments.helpers import DeploymentType, list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
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
        mock_count.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=0)
    @patch(f"{MODULE}.list_attachments_by_deployment_ids", new_callable=AsyncMock, return_value=[])
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_cursor_does_not_advance_on_delete(
        self,
        mock_list,
        mock_fetch,
        mock_delete,
        mock_list_att,  # noqa: ARG002
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
            set(),  # stale not known
            {"rk-good"},  # good is known
        ]

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=BaseDeploymentMapper(),
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
        mock_delete.assert_awaited_once()
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
    @patch(f"{MODULE}.list_attachments_by_deployment_ids", new_callable=AsyncMock, return_value=[])
    @patch(f"{MODULE}.delete_deployment_by_id", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_guard_prevents_infinite_loop(self, mock_list, mock_fetch, mock_delete, mock_list_att, mock_count):  # noqa: ARG002
        """The guard counter breaks the loop if too many iterations occur."""
        stale = _mock_deployment_row("rk-stale")
        # Always return a stale row — should eventually stop via guard
        mock_list.return_value = [(stale, 0, [])]
        mock_fetch.return_value = set()  # never known

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
        # guard = size * 4 + 20 = 28, so loop ran at most 28 times
        assert mock_list.call_count <= 28
        assert mock_delete.await_count > 0
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

        with pytest.raises(HTTPException, match="Unexpected source_ref"):
            resolve_added_snapshot_bindings_for_update(
                deployment_mapper=_FakeMapper(),
                added_flow_version_ids=[uuid4()],
                result=DeploymentUpdateResult(
                    id="provider-id",
                    provider_result={
                        "added_snapshot_bindings": [
                            {"source_ref": "other", "snapshot_id": "snap-1"},
                        ]
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


def test_as_uuid_accepts_uuid_instances():
    from langflow.api.v1.mappers.deployments.helpers import as_uuid

    value = uuid4()
    assert as_uuid(value) == value


def test_watsonx_mapper_util_created_snapshot_ids_uses_adapter_slot():
    created = WatsonxOrchestrateDeploymentMapper().util_created_snapshot_ids(
        result=DeploymentUpdateResult(
            id="provider-id",
            provider_result={"created_snapshot_ids": ["snap-1", "snap-2"]},
        ),
    )

    assert created.ids == ["snap-1", "snap-2"]


def test_resolve_flow_version_patch_for_update_watsonx_operations():
    from langflow.api.v1.mappers.deployments.helpers import resolve_flow_version_patch_for_update

    add_id = uuid4()
    remove_id = uuid4()
    add_ids, remove_ids = resolve_flow_version_patch_for_update(
        deployment_mapper=_FakeMapper(),
        payload=DeploymentUpdateRequest(
            add_flow_version_ids=[add_id],
            remove_flow_version_ids=[remove_id],
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

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_snapshot_keys

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

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_snapshot_keys

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
    async def test_provider_error_raises_502(self):
        adapter = AsyncMock()
        adapter.list_snapshots.side_effect = RuntimeError("provider down")

        from langflow.api.v1.mappers.deployments.helpers import fetch_provider_snapshot_keys

        with pytest.raises(HTTPException) as exc_info:
            await fetch_provider_snapshot_keys(
                deployment_adapter=adapter,
                user_id=uuid4(),
                provider_id=uuid4(),
                db=AsyncMock(),
                snapshot_ids=["snap-1"],
            )

        assert exc_info.value.status_code == 502


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
    @patch(f"{MODULE}.delete_deployment_attachment", new_callable=AsyncMock)
    async def test_deletes_stale_attachments(self, mock_delete_att):
        """Attachments with snapshot IDs not in the known set are deleted."""
        dep_id = uuid4()
        uid = uuid4()
        fv_good = uuid4()
        fv_stale = uuid4()
        attachments = [
            _mock_attachment(flow_version_id=fv_good, provider_snapshot_id="snap-good", deployment_id=dep_id),
            _mock_attachment(flow_version_id=fv_stale, provider_snapshot_id="snap-stale", deployment_id=dep_id),
        ]

        from langflow.api.v1.mappers.deployments.helpers import sync_attachment_snapshot_ids

        counts = await sync_attachment_snapshot_ids(
            user_id=uid,
            deployment_ids=[dep_id],
            attachments=attachments,
            known_snapshot_ids={"snap-good"},
            db=AsyncMock(),
        )

        assert counts[dep_id] == 1
        mock_delete_att.assert_awaited_once()
        call_kwargs = mock_delete_att.call_args.kwargs
        assert call_kwargs["flow_version_id"] == fv_stale
        assert call_kwargs["deployment_id"] == dep_id

    @pytest.mark.asyncio
    @patch(f"{MODULE}.delete_deployment_attachment", new_callable=AsyncMock)
    async def test_keeps_attachments_without_snapshot_id(self, mock_delete_att):
        """Attachments with no provider_snapshot_id are kept (not verified)."""
        dep_id = uuid4()
        attachments = [
            _mock_attachment(provider_snapshot_id=None, deployment_id=dep_id),
            _mock_attachment(provider_snapshot_id="", deployment_id=dep_id),
        ]

        from langflow.api.v1.mappers.deployments.helpers import sync_attachment_snapshot_ids

        counts = await sync_attachment_snapshot_ids(
            user_id=uuid4(),
            deployment_ids=[dep_id],
            attachments=attachments,
            known_snapshot_ids=set(),
            db=AsyncMock(),
        )

        assert counts[dep_id] == 2
        mock_delete_att.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.delete_deployment_attachment", new_callable=AsyncMock)
    async def test_all_snapshots_known_nothing_deleted(self, mock_delete_att):
        dep_id = uuid4()
        attachments = [
            _mock_attachment(provider_snapshot_id="snap-1", deployment_id=dep_id),
            _mock_attachment(provider_snapshot_id="snap-2", deployment_id=dep_id),
        ]

        from langflow.api.v1.mappers.deployments.helpers import sync_attachment_snapshot_ids

        counts = await sync_attachment_snapshot_ids(
            user_id=uuid4(),
            deployment_ids=[dep_id],
            attachments=attachments,
            known_snapshot_ids={"snap-1", "snap-2"},
            db=AsyncMock(),
        )

        assert counts[dep_id] == 2
        mock_delete_att.assert_not_awaited()


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
            deployment_row=dep_row,
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
            deployment_row=dep_row,
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
            deployment_row=dep_row,
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
            deployment_row=dep_row,
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
        """Rollback payload contains put_tools with provider_snapshot_ids from DB attachments."""
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
        assert result.spec.description == ""


# ---------------------------------------------------------------------------
# list_deployments_synced: phase-2 snapshot sync
# ---------------------------------------------------------------------------


class TestListDeploymentsSyncedSnapshotPhase:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.sync_attachment_snapshot_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_snapshot_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_snapshot_sync_corrects_attached_count(
        self,
        mock_list,
        mock_fetch_rk,
        mock_list_att,
        mock_fetch_snap,
        mock_sync_snap,
        mock_count,  # noqa: ARG002
    ):
        """Phase 2 corrects attached_count using snapshot-level sync."""
        row = _mock_deployment_row("rk-1")
        mock_list.side_effect = [[(row, 3, [])], []]
        mock_fetch_rk.return_value = {"rk-1"}
        mock_list_att.return_value = [
            _mock_attachment(provider_snapshot_id="snap-1", deployment_id=row.id),
            _mock_attachment(provider_snapshot_id="snap-stale", deployment_id=row.id),
            _mock_attachment(provider_snapshot_id="snap-2", deployment_id=row.id),
        ]
        mock_fetch_snap.return_value = {"snap-1", "snap-2"}
        mock_sync_snap.return_value = {row.id: 2}

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=WatsonxOrchestrateDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 1
        assert accepted[0][1] == 2  # corrected count

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.fetch_provider_snapshot_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_no_snapshot_sync_when_no_snapshot_ids(
        self,
        mock_list,
        mock_fetch_rk,
        mock_list_att,
        mock_fetch_snap,
        mock_count,  # noqa: ARG002
    ):
        """Phase 2 is skipped when attachments exist but none have provider_snapshot_id."""
        row = _mock_deployment_row("rk-1")
        mock_list.side_effect = [[(row, 0, [])], []]
        mock_fetch_rk.return_value = {"rk-1"}
        mock_list_att.return_value = [
            _mock_attachment(provider_snapshot_id=None, deployment_id=row.id),
            _mock_attachment(provider_snapshot_id="", deployment_id=row.id),
        ]

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=WatsonxOrchestrateDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 1
        mock_fetch_snap.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.count_deployments_by_provider", new_callable=AsyncMock, return_value=1)
    @patch(f"{MODULE}.fetch_provider_snapshot_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_attachments_by_deployment_ids", new_callable=AsyncMock)
    @patch(f"{MODULE}.fetch_provider_resource_keys", new_callable=AsyncMock)
    @patch(f"{MODULE}.list_deployments_page", new_callable=AsyncMock)
    async def test_snapshot_sync_error_preserves_original_counts(
        self,
        mock_list,
        mock_fetch_rk,
        mock_list_att,
        mock_fetch_snap,
        mock_count,  # noqa: ARG002
    ):
        """When Phase 2 raises, accepted rows keep their original attached_count."""
        row = _mock_deployment_row("rk-1")
        mock_list.side_effect = [[(row, 3, [])], []]
        mock_fetch_rk.return_value = {"rk-1"}
        mock_list_att.return_value = [
            _mock_attachment(provider_snapshot_id="snap-1", deployment_id=row.id),
        ]
        mock_fetch_snap.side_effect = RuntimeError("provider down")

        from langflow.api.v1.mappers.deployments.helpers import list_deployments_synced

        accepted, _ = await list_deployments_synced(
            deployment_adapter=AsyncMock(),
            deployment_mapper=WatsonxOrchestrateDeploymentMapper(),
            user_id=uuid4(),
            provider_id=uuid4(),
            db=AsyncMock(),
            page=1,
            size=10,
            deployment_type=None,
        )

        assert len(accepted) == 1
        assert accepted[0][1] == 3  # original count preserved, not corrected

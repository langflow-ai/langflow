import tempfile
import uuid
from uuid import UUID

from fastapi import status
from httpx import AsyncClient


def _catalog_flow_data(component_key: str) -> dict:
    return {
        "nodes": [{"id": f"{component_key}-node", "data": {"type": component_key}}],
        "edges": [],
    }


async def _attach_deployment_to_flow(*, user_id: UUID, flow_id: UUID, project_id: UUID) -> None:
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import (
        DeploymentProviderAccount,
        DeploymentProviderKey,
    )
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.flow_version_deployment_attachment.model import (
        FlowVersionDeploymentAttachment,
    )
    from langflow.services.deps import session_scope
    from lfx.services.adapters.deployment.schema import DeploymentType

    async with session_scope() as session:
        provider = DeploymentProviderAccount(
            user_id=user_id,
            name=f"provider-{flow_id.hex[:8]}",
            provider_tenant_id="tenant-1",
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            provider_url=f"https://provider-{flow_id.hex[:8]}.example.com",
            api_key="encrypted-value",  # pragma: allowlist secret
        )
        session.add(provider)
        await session.flush()

        deployment = Deployment(
            user_id=user_id,
            project_id=project_id,
            deployment_provider_account_id=provider.id,
            resource_key=f"rk-{flow_id.hex[:8]}",
            display_name=f"deployment-{flow_id.hex[:8]}",
            deployment_type=DeploymentType.AGENT,
        )
        session.add(deployment)
        await session.flush()

        flow_version = FlowVersion(
            flow_id=flow_id,
            user_id=user_id,
            version_number=1,
            data={"nodes": [], "edges": []},
        )
        session.add(flow_version)
        await session.flush()

        attachment = FlowVersionDeploymentAttachment(
            user_id=user_id,
            flow_version_id=flow_version.id,
            deployment_id=deployment.id,
            provider_snapshot_id=f"snapshot-{flow_id.hex[:8]}",
        )
        session.add(attachment)
        await session.commit()


async def test_create_flow(client: AsyncClient, logged_in_headers):
    # Use relative path - absolute paths outside allowed directory are rejected
    flow_filename = f"{uuid.uuid4()}.json"
    basic_case = {
        "name": "string",
        "description": "string",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "string",
        "tags": ["string"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "fs_path": flow_filename,
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "data" in result, "The result must have a 'data' key"
    assert "description" in result, "The result must have a 'description' key"
    assert "endpoint_name" in result, "The result must have a 'endpoint_name' key"
    assert "folder_id" in result, "The result must have a 'folder_id' key"
    assert "gradient" in result, "The result must have a 'gradient' key"
    assert "icon" in result, "The result must have a 'icon' key"
    assert "icon_bg_color" in result, "The result must have a 'icon_bg_color' key"
    assert "id" in result, "The result must have a 'id' key"
    assert "is_component" in result, "The result must have a 'is_component' key"
    assert "name" in result, "The result must have a 'name' key"
    assert "tags" in result, "The result must have a 'tags' key"
    assert "updated_at" in result, "The result must have a 'updated_at' key"
    assert "user_id" in result, "The result must have a 'user_id' key"
    assert "webhook" in result, "The result must have a 'webhook' key"


async def test_create_flow_retries_transient_sqlite_lock_with_fresh_payload(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    """A transient SQLite writer lock retries from a deeply copied FlowCreate snapshot."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from sqlalchemy.exc import OperationalError

    original_new_flow = flows_module._new_flow
    attempts: list[object] = []
    expected_name = f"create-lock-retry-{uuid.uuid4()}"
    expected_data = {
        "nodes": [{"id": "original-node", "data": {"settings": {"values": ["original"]}}}],
        "edges": [],
    }
    insert_statement = "INSERT INTO flow (id, name) VALUES (?, ?)"

    async def create_after_one_lock(**kwargs):
        attempts.append(kwargs["flow"])
        if len(attempts) == 1:
            kwargs["flow"].name = "mutated-during-failed-attempt"
            kwargs["flow"].data["nodes"][0]["data"]["settings"]["values"].append("mutated")
            raise OperationalError(
                insert_statement,
                {"name": expected_name},
                sqlite3.OperationalError("database is locked"),
            )
        return await original_new_flow(**kwargs)

    monkeypatch.setattr(flows_module, "_new_flow", create_after_one_lock)

    response = await client.post(
        "api/v1/flows/",
        json={"name": expected_name, "data": expected_data},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["name"] == expected_name
    assert response.json()["data"] == expected_data
    assert len(attempts) == 2
    assert attempts[0] is not attempts[1]
    assert attempts[0].data is not attempts[1].data
    assert attempts[0].data["nodes"][0] is not attempts[1].data["nodes"][0]


async def test_create_flow_duplicate_explicit_id_returns_sanitized_unique_error(client: AsyncClient, logged_in_headers):
    """A real duplicate primary-key failure reaches the route's uniqueness mapping."""
    explicit_id = str(uuid.uuid4())
    first_response = await client.post(
        "api/v1/flows/",
        json={"id": explicit_id, "name": f"explicit-id-first-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    assert first_response.status_code == status.HTTP_201_CREATED, first_response.text

    duplicate_response = await client.post(
        "api/v1/flows/",
        json={"id": explicit_id, "name": f"explicit-id-second-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )

    assert duplicate_response.status_code == status.HTTP_400_BAD_REQUEST, duplicate_response.text
    assert duplicate_response.json()["detail"] == "Id must be unique"
    assert explicit_id not in duplicate_response.text
    assert "INSERT INTO" not in duplicate_response.text
    assert "sqlalche.me" not in duplicate_response.text


def test_flow_unique_constraint_error_maps_postgres_sqlstate_without_leaking_values():
    """PostgreSQL 23505 diagnostics map only known flow constraints to safe field names."""
    from types import SimpleNamespace

    from langflow.api.v1 import flows as flows_module
    from sqlalchemy.exc import IntegrityError

    leaked_id = str(uuid.uuid4())
    expected_details = {
        "flow_pkey": "Id must be unique",
        "pk_flow": "Id must be unique",
        "uq_flow_id": "Id must be unique",
        "unique_flow_name": "Name must be unique",
        "unique_flow_endpoint_name": "Endpoint name must be unique",
    }

    for constraint_name, expected_detail in expected_details.items():
        driver_error = RuntimeError(f"duplicate key value {leaked_id}")
        driver_error.sqlstate = "23505"
        driver_error.diag = SimpleNamespace(constraint_name=constraint_name)
        integrity_error = IntegrityError("INSERT INTO flow ...", {"id": leaked_id}, driver_error)

        response_error = flows_module._handle_unique_constraint_error(integrity_error)

        assert response_error.status_code == status.HTTP_400_BAD_REQUEST
        assert response_error.detail == expected_detail
        assert leaked_id not in str(response_error.detail)

    marker_driver_error = RuntimeError(f"duplicate key value UNIQUE constraint failed: flow.id {leaked_id}")
    marker_driver_error.sqlstate = "23505"
    marker_driver_error.diag = SimpleNamespace(constraint_name="unique_flow_name")
    marker_integrity_error = IntegrityError("INSERT INTO flow ...", {"name": leaked_id}, marker_driver_error)

    marker_response_error = flows_module._handle_unique_constraint_error(marker_integrity_error)

    assert marker_response_error.status_code == status.HTTP_400_BAD_REQUEST
    assert marker_response_error.detail == "Name must be unique"
    assert leaked_id not in str(marker_response_error.detail)

    unknown_driver_error = RuntimeError(f"duplicate key value {leaked_id}")
    unknown_driver_error.sqlstate = "23505"
    unknown_driver_error.diag = SimpleNamespace(constraint_name="unrelated_unique_constraint")
    unknown_integrity_error = IntegrityError("INSERT INTO other ...", {"id": leaked_id}, unknown_driver_error)

    unknown_response_error = flows_module._handle_unique_constraint_error(unknown_integrity_error)

    assert unknown_response_error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert unknown_response_error.detail == "Could not persist the flow."
    assert leaked_id not in str(unknown_response_error.detail)


def test_flow_unique_constraint_error_rejects_unknown_sqlite_table():
    """SQLite messages for other tables or unknown flow constraint shapes stay generic."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from sqlalchemy.exc import IntegrityError

    leaked_id = str(uuid.uuid4())
    unknown_constraints = (
        "unrelated.id",
        "other.name",
        "flow.name",
        "flow.user_id, unrelated.name",
    )

    for constraint in unknown_constraints:
        driver_error = sqlite3.IntegrityError(f"UNIQUE constraint failed: {constraint}")
        integrity_error = IntegrityError("INSERT INTO other ...", {"id": leaked_id}, driver_error)

        response_error = flows_module._handle_unique_constraint_error(integrity_error)

        assert response_error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response_error.detail == "Could not persist the flow."
        assert constraint not in str(response_error.detail)
        assert leaked_id not in str(response_error.detail)


async def test_create_flow_real_competing_sqlite_writer_is_retried(client: AsyncClient, logged_in_headers, monkeypatch):
    """A real second SQLite connection holding the write lock triggers a create retry."""
    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.deps import session_scope
    from sqlalchemy import text

    original_new_flow = flows_module._new_flow
    attempts = {"count": 0}
    expected_name = f"create-real-lock-{uuid.uuid4()}"

    async def create_after_competing_write(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            async with session_scope() as competing_session:
                competing_session.add(Folder(name=f"create-competing-write-{uuid.uuid4()}", user_id=None))
                await competing_session.flush()
                # The competing connection now holds SQLite's write lock. Make
                # the route connection report the real lock immediately; the
                # failed attempt unwinds this context and releases the writer.
                await kwargs["session"].exec(text("PRAGMA busy_timeout = 0"))
                return await original_new_flow(**kwargs)
        return await original_new_flow(**kwargs)

    monkeypatch.setattr(flows_module, "_new_flow", create_after_competing_write)

    response = await client.post(
        "api/v1/flows/",
        json={"name": expected_name, "data": {}},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["name"] == expected_name
    assert attempts["count"] >= 2


async def test_create_flow_exhausted_lock_retries_return_sanitized_503(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    """Exhausted create retries expose neither SQL nor bound values."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.lock_retry import DEFAULT_LOCK_RETRY_ATTEMPTS
    from sqlalchemy.exc import OperationalError

    leaked_statement = "INSERT INTO flow (id, name) VALUES (?, ?)"
    leaked_value = f"secret-create-value-{uuid.uuid4()}"
    leaked_id = str(uuid.uuid4())
    attempts = {"count": 0}

    async def always_locked(**_kwargs):
        attempts["count"] += 1
        raise OperationalError(
            leaked_statement,
            {"id": leaked_id, "name": leaked_value},
            sqlite3.OperationalError("database is locked"),
        )

    monkeypatch.setattr(flows_module, "_new_flow", always_locked)
    original_retry = flows_module.run_with_lock_retry

    async def run_without_delay(operation, *, session, description):
        return await original_retry(operation, session=session, description=description, base_delay=0)

    monkeypatch.setattr(flows_module, "run_with_lock_retry", run_without_delay)

    response = await client.post(
        "api/v1/flows/",
        json={"name": leaked_value, "id": leaked_id, "data": {}},
        headers=logged_in_headers,
    )

    assert attempts["count"] == DEFAULT_LOCK_RETRY_ATTEMPTS
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.headers["Retry-After"] == "1"
    assert response.json()["detail"] == flows_module.FLOW_CREATE_BUSY
    assert leaked_statement not in response.text
    assert leaked_value not in response.text
    assert leaked_id not in response.text
    assert "sqlalche.me" not in response.text


async def test_create_flow_non_lock_failure_returns_sanitized_500(client: AsyncClient, logged_in_headers, monkeypatch):
    """A non-lock failure inside the real create helper is not retried or disclosed."""
    from langflow.api.v1 import flows as flows_module
    from langflow.api.v1 import flows_helpers

    leaked_detail = f"sensitive-create-detail-{uuid.uuid4()} UNIQUE constraint failed: flow.id"
    attempts = {"count": 0}

    async def fail_save(*_args, **_kwargs):
        attempts["count"] += 1
        raise RuntimeError(leaked_detail)

    monkeypatch.setattr(flows_helpers, "_save_flow_to_fs", fail_save)

    response = await client.post(
        "api/v1/flows/",
        json={"name": f"create-non-lock-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )

    assert attempts["count"] == 1
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == flows_module.FLOW_CREATE_FAILED
    assert leaked_detail not in response.text
    assert "Retry-After" not in response.headers


async def test_create_flow_helper_http_500_returns_sanitized_500(client: AsyncClient, logged_in_headers, monkeypatch):
    """A helper HTTP 500 cannot disclose filesystem paths or flow identifiers."""
    from fastapi import HTTPException
    from langflow.api.v1 import flows as flows_module
    from langflow.api.v1 import flows_helpers

    leaked_id = str(uuid.uuid4())
    leaked_detail = f"Failed to write flow to filesystem: /private/flows/{leaked_id}.json"

    async def fail_save(*_args, **_kwargs):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=leaked_detail)

    monkeypatch.setattr(flows_helpers, "_save_flow_to_fs", fail_save)

    response = await client.post(
        "api/v1/flows/",
        json={"name": f"create-helper-http-500-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == flows_module.FLOW_CREATE_FAILED
    assert leaked_detail not in response.text
    assert leaked_id not in response.text


async def test_new_flow_default_sanitizes_unhandled_error(active_user, monkeypatch):
    """Direct helper callers retain the safe default instead of receiving raw persistence errors."""
    import pytest
    from fastapi import HTTPException
    from langflow.api.v1 import flows_helpers
    from langflow.services.database.models.flow.model import FlowCreate
    from langflow.services.deps import get_storage_service, session_scope

    leaked_id = str(uuid.uuid4())
    leaked_statement = "INSERT INTO flow VALUES (?)"
    leaked_detail = f"{leaked_statement}: {leaked_id}"

    async def fail_save(*_args, **_kwargs):
        raise RuntimeError(leaked_detail)

    monkeypatch.setattr(flows_helpers, "_save_flow_to_fs", fail_save)

    with pytest.raises(HTTPException) as exc_info:
        async with session_scope() as session:
            await flows_helpers._new_flow(
                session=session,
                flow=FlowCreate(name=f"direct-helper-failure-{uuid.uuid4()}", data={}),
                user_id=active_user.id,
                storage_service=get_storage_service(),
            )

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "An internal error occurred while creating the flow."
    assert leaked_detail not in str(exc_info.value)
    assert leaked_id not in str(exc_info.value)


async def test_create_and_put_flow_enforce_catalog_policy_with_default_allow(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    from langflow.api.v1 import flows
    from lfx.services.catalog_policy import CatalogPolicySnapshot

    class MutableCatalogPolicyService:
        snapshot = CatalogPolicySnapshot()

    service = MutableCatalogPolicyService()
    monkeypatch.setattr(flows, "get_catalog_policy_service", lambda: service)
    blocked_key = "BlockedForFlowWrites"
    graph = _catalog_flow_data(blocked_key)

    allowed_response = await client.post(
        "api/v1/flows/",
        json={"name": f"catalog-default-allow-{uuid.uuid4()}", "data": graph},
        headers=logged_in_headers,
    )
    assert allowed_response.status_code == status.HTTP_201_CREATED, allowed_response.text

    service.snapshot = CatalogPolicySnapshot(blocked_component_keys={blocked_key})
    blocked_create = await client.post(
        "api/v1/flows/",
        json={"name": f"catalog-blocked-create-{uuid.uuid4()}", "data": graph},
        headers=logged_in_headers,
    )
    assert blocked_create.status_code == status.HTTP_400_BAD_REQUEST
    assert blocked_create.json()["detail"].endswith(blocked_key)

    put_flow_id = uuid.uuid4()
    blocked_put = await client.put(
        f"api/v1/flows/{put_flow_id}",
        json={"name": f"catalog-blocked-put-{uuid.uuid4()}", "data": graph},
        headers=logged_in_headers,
    )
    assert blocked_put.status_code == status.HTTP_400_BAD_REQUEST
    assert blocked_put.json()["detail"].endswith(blocked_key)


async def test_create_flow_maps_catalog_identity_unavailable_to_503(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    from langflow.api.v1 import flows
    from lfx.services.catalog_policy import CatalogPolicySnapshot
    from lfx.utils.flow_validation import CatalogPolicyIdentityUnavailableError

    detail = "Catalog policy component identities are still initializing. Please try again in a few seconds."

    def identities_unavailable(_flow_data, *, snapshot):
        assert snapshot.blocked_component_keys
        raise CatalogPolicyIdentityUnavailableError(detail)

    service = type(
        "CatalogPolicyService",
        (),
        {"snapshot": CatalogPolicySnapshot(blocked_component_keys={"Prompt Template"})},
    )()
    monkeypatch.setattr(flows, "get_catalog_policy_service", lambda: service)
    monkeypatch.setattr(flows, "validate_catalog_policy_for_flow", identities_unavailable)

    response = await client.post(
        "api/v1/flows/",
        json={"name": f"catalog-identities-unavailable-{uuid.uuid4()}", "data": _catalog_flow_data("Prompt")},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == detail


async def test_patch_and_put_metadata_only_updates_validate_stored_graph(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    from langflow.api.v1 import flows
    from lfx.services.catalog_policy import CatalogPolicySnapshot

    class MutableCatalogPolicyService:
        snapshot = CatalogPolicySnapshot()

    service = MutableCatalogPolicyService()
    monkeypatch.setattr(flows, "get_catalog_policy_service", lambda: service)
    blocked_key = "BlockedStoredGraph"
    graph = _catalog_flow_data(blocked_key)

    patch_source = await client.post(
        "api/v1/flows/",
        json={"name": f"catalog-patch-source-{uuid.uuid4()}", "description": "original", "data": graph},
        headers=logged_in_headers,
    )
    put_source = await client.post(
        "api/v1/flows/",
        json={"name": f"catalog-put-source-{uuid.uuid4()}", "description": "original", "data": graph},
        headers=logged_in_headers,
    )
    assert patch_source.status_code == status.HTTP_201_CREATED, patch_source.text
    assert put_source.status_code == status.HTTP_201_CREATED, put_source.text

    service.snapshot = CatalogPolicySnapshot(blocked_component_keys={blocked_key})
    patch_response = await client.patch(
        f"api/v1/flows/{patch_source.json()['id']}",
        json={"description": "metadata-only patch"},
        headers=logged_in_headers,
    )
    put_response = await client.put(
        f"api/v1/flows/{put_source.json()['id']}",
        json={"name": put_source.json()["name"], "description": "metadata-only put"},
        headers=logged_in_headers,
    )

    assert patch_response.status_code == status.HTTP_400_BAD_REQUEST
    assert patch_response.json()["detail"].endswith(blocked_key)
    assert put_response.status_code == status.HTTP_400_BAD_REQUEST
    assert put_response.json()["detail"].endswith(blocked_key)

    unchanged_patch = await client.get(
        f"api/v1/flows/{patch_source.json()['id']}",
        headers=logged_in_headers,
    )
    unchanged_put = await client.get(
        f"api/v1/flows/{put_source.json()['id']}",
        headers=logged_in_headers,
    )
    assert unchanged_patch.json()["description"] == "original"
    assert unchanged_put.json()["description"] == "original"


async def test_read_flows(client: AsyncClient, logged_in_headers):
    params = {
        "remove_example_flows": False,
        "components_only": False,
        "get_all": True,
        "header_flows": False,
        "page": 1,
        "size": 50,
    }
    response = await client.get("api/v1/flows/", params=params, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"


async def test_get_flows_with_malformed_bearer_token_returns_401(client: AsyncClient):
    """CT-010: GET /api/v1/flows with malformed Bearer token must return 401 Unauthorized."""
    headers = {"Authorization": "Bearer invalid.token.here"}
    response = await client.get("api/v1/flows/", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert "detail" in data
    assert "token" in data["detail"].lower() or "credential" in data["detail"].lower()


async def test_read_flow(client: AsyncClient, logged_in_headers):
    basic_case = {
        "name": "string",
        "description": "string",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "string",
        "tags": ["string"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    response_ = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]
    response = await client.get(f"api/v1/flows/{id_}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "data" in result, "The result must have a 'data' key"
    assert "description" in result, "The result must have a 'description' key"
    assert "endpoint_name" in result, "The result must have a 'endpoint_name' key"
    assert "folder_id" in result, "The result must have a 'folder_id' key"
    assert "gradient" in result, "The result must have a 'gradient' key"
    assert "icon" in result, "The result must have a 'icon' key"
    assert "icon_bg_color" in result, "The result must have a 'icon_bg_color' key"
    assert "id" in result, "The result must have a 'id' key"
    assert "is_component" in result, "The result must have a 'is_component' key"
    assert "name" in result, "The result must have a 'name' key"
    assert "tags" in result, "The result must have a 'tags' key"
    assert "updated_at" in result, "The result must have a 'updated_at' key"
    assert "user_id" in result, "The result must have a 'user_id' key"
    assert "webhook" in result, "The result must have a 'webhook' key"


async def test_update_flow(client: AsyncClient, logged_in_headers):
    name = "first_name"
    updated_name = "second_name"
    basic_case = {
        "description": "string",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "string",
        "tags": ["string"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    basic_case["name"] = name
    response_ = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    id_ = response_.json()["id"]

    # Use relative path - absolute paths outside allowed directory are rejected
    flow_filename = f"{uuid.uuid4()!s}.json"
    basic_case["name"] = updated_name
    basic_case["fs_path"] = flow_filename

    response = await client.patch(f"api/v1/flows/{id_}", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert isinstance(result, dict), "The result must be a dictionary"
    assert "data" in result, "The result must have a 'data' key"
    assert "description" in result, "The result must have a 'description' key"
    assert "endpoint_name" in result, "The result must have a 'endpoint_name' key"
    assert "folder_id" in result, "The result must have a 'folder_id' key"
    assert "gradient" in result, "The result must have a 'gradient' key"
    assert "icon" in result, "The result must have a 'icon' key"
    assert "icon_bg_color" in result, "The result must have a 'icon_bg_color' key"
    assert "id" in result, "The result must have a 'id' key"
    assert "is_component" in result, "The result must have a 'is_component' key"
    assert "name" in result, "The result must have a 'name' key"
    assert "tags" in result, "The result must have a 'tags' key"
    assert "updated_at" in result, "The result must have a 'updated_at' key"
    assert "user_id" in result, "The result must have a 'user_id' key"
    assert "webhook" in result, "The result must have a 'webhook' key"
    assert result["name"] == updated_name, "The name must be updated"


async def test_locked_flow_rejects_api_updates_until_unlocked(client: AsyncClient, logged_in_headers):
    original_data = {"nodes": [], "edges": []}
    create_response = await client.post(
        "api/v1/flows/",
        json={"name": "locked-flow", "description": "original", "data": original_data, "locked": True},
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created = create_response.json()
    flow_id = created["id"]

    # Navigation can submit the full current flow even when nothing changed.
    # A no-op save must succeed so the UI can leave a locked flow cleanly.
    no_op_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={
            "name": created["name"],
            "description": created["description"],
            "data": created["data"],
            "folder_id": created["folder_id"],
            "endpoint_name": created["endpoint_name"],
            "locked": True,
        },
        headers=logged_in_headers,
    )
    assert no_op_response.status_code == status.HTTP_200_OK
    assert no_op_response.json()["locked"] is True

    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"description": "changed via PATCH"},
        headers=logged_in_headers,
    )
    assert patch_response.status_code == status.HTTP_423_LOCKED
    assert patch_response.json()["detail"] == "Flow is locked. Unlock it before making changes."

    put_response = await client.put(
        f"api/v1/flows/{flow_id}",
        json={"name": "changed-via-put", "description": "original", "data": original_data},
        headers=logged_in_headers,
    )
    assert put_response.status_code == status.HTTP_423_LOCKED

    combined_unlock_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"locked": False, "description": "changed while unlocking"},
        headers=logged_in_headers,
    )
    assert combined_unlock_response.status_code == status.HTTP_423_LOCKED

    unchanged_response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert unchanged_response.status_code == status.HTTP_200_OK
    assert unchanged_response.json()["name"] == "locked-flow"
    assert unchanged_response.json()["description"] == "original"

    # The UI sends the current flow fields along with the lock toggle. Equal
    # values must not prevent an unlock-only request from succeeding.
    unlock_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={
            "name": created["name"],
            "description": created["description"],
            "data": created["data"],
            "folder_id": created["folder_id"],
            "endpoint_name": created["endpoint_name"],
            "locked": False,
        },
        headers=logged_in_headers,
    )
    assert unlock_response.status_code == status.HTTP_200_OK
    assert unlock_response.json()["locked"] is False

    update_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"description": "changed after unlock"},
        headers=logged_in_headers,
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["description"] == "changed after unlock"


async def test_patch_flow_keeps_existing_endpoint_when_not_provided(client: AsyncClient, logged_in_headers):
    """Test that PATCH preserves endpoint_name when the field is omitted."""
    initial_flow = {
        "name": "patch_endpoint_flow",
        "endpoint_name": "keep_patch_endpoint",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"name": "patch_endpoint_flow_updated"},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["endpoint_name"] == "keep_patch_endpoint"


async def test_patch_flow_allows_clearing_endpoint_with_null(client: AsyncClient, logged_in_headers):
    """Test that PATCH clears endpoint_name when it is explicitly set to null."""
    initial_flow = {
        "name": "patch_clear_endpoint_flow",
        "endpoint_name": "clear_patch_endpoint",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"endpoint_name": None},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["endpoint_name"] is None


async def test_patch_flow_updates_access_and_action_fields(client: AsyncClient, logged_in_headers):
    """PATCH should persist public-sharing and MCP action metadata fields."""
    create_response = await client.post(
        "api/v1/flows/",
        json={"name": "patch_access_type_flow", "data": {}},
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={
            "access_type": "PUBLIC",
            "action_name": "shared_action",
            "action_description": "Shared flow action",
        },
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["access_type"] == "PUBLIC"
    assert result["action_name"] == "shared_action"
    assert result["action_description"] == "Shared flow action"


async def test_create_flow_defaults_to_workflow_type(client: AsyncClient, logged_in_headers):
    """A flow created without flow_type is a workflow with A2A off."""
    response = await client.post(
        "api/v1/flows/",
        json={"name": "default_type_flow", "data": {}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()
    assert result["flow_type"] == "workflow"
    assert result["a2a_enabled"] is False
    assert result["a2a_card_overrides"] is None


async def test_create_agent_flow_round_trips(client: AsyncClient, logged_in_headers):
    """flow_type=agent and the a2a fields persist through create and read."""
    create_response = await client.post(
        "api/v1/flows/",
        json={
            "name": "agent_flow",
            "data": {},
            "flow_type": "agent",
            "a2a_enabled": True,
            "a2a_card_overrides": {"skill_description": "does things"},
        },
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created = create_response.json()
    assert created["flow_type"] == "agent"
    assert created["a2a_enabled"] is True

    flow_id = created["id"]
    read_response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert read_response.status_code == status.HTTP_200_OK
    read = read_response.json()
    assert read["flow_type"] == "agent"
    assert read["a2a_enabled"] is True
    assert read["a2a_card_overrides"] == {"skill_description": "does things"}


async def test_patch_flow_updates_flow_type_and_a2a(client: AsyncClient, logged_in_headers):
    """PATCH can promote a workflow to an agent and set the a2a fields."""
    create_response = await client.post(
        "api/v1/flows/",
        json={"name": "patch_flow_type_flow", "data": {}},
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"flow_type": "agent", "a2a_enabled": True, "a2a_card_overrides": {"tags": ["x"]}},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["flow_type"] == "agent"
    assert result["a2a_enabled"] is True
    assert result["a2a_card_overrides"] == {"tags": ["x"]}


async def test_read_flows_filtered_by_flow_type(client: AsyncClient, logged_in_headers):
    """The list endpoint filtered by flow_type=agent returns only agent flows."""
    workflow_response = await client.post(
        "api/v1/flows/",
        json={"name": "a_workflow_flow", "data": {}},
        headers=logged_in_headers,
    )
    agent_response = await client.post(
        "api/v1/flows/",
        json={"name": "an_agent_flow", "data": {}, "flow_type": "agent"},
        headers=logged_in_headers,
    )
    workflow_id = workflow_response.json()["id"]
    agent_id = agent_response.json()["id"]

    response = await client.get(
        "api/v1/flows/",
        params={"get_all": True, "flow_type": "agent"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    returned_ids = {flow["id"] for flow in result}
    assert agent_id in returned_ids
    assert workflow_id not in returned_ids
    assert all(flow["flow_type"] == "agent" for flow in result)


async def test_create_agent_flow_defaults_a2a_disabled(client: AsyncClient, logged_in_headers):
    """Creating an agent flow without a2a_enabled leaves A2A off by default."""
    response = await client.post(
        "api/v1/flows/",
        json={"name": "agent_no_a2a_flow", "data": {}, "flow_type": "agent"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()
    assert result["flow_type"] == "agent"
    assert result["a2a_enabled"] is False


async def test_read_flows_rejects_invalid_flow_type(client: AsyncClient, logged_in_headers):
    """An unknown flow_type query value is rejected by enum validation."""
    response = await client.get(
        "api/v1/flows/",
        params={"get_all": True, "flow_type": "not_a_real_type"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_read_flows_header_mode_filtered_by_flow_type(client: AsyncClient, logged_in_headers):
    """The flow_type filter also applies on the header_flows (compressed) list path."""
    await client.post(
        "api/v1/flows/",
        json={"name": "header_workflow_flow", "data": {}},
        headers=logged_in_headers,
    )
    agent_response = await client.post(
        "api/v1/flows/",
        json={"name": "header_agent_flow", "data": {}, "flow_type": "agent"},
        headers=logged_in_headers,
    )
    agent_id = agent_response.json()["id"]

    response = await client.get(
        "api/v1/flows/",
        params={"get_all": True, "header_flows": True, "flow_type": "agent"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    returned_ids = {flow["id"] for flow in result}
    assert agent_id in returned_ids
    assert all(flow["flow_type"] == "agent" for flow in result)


async def test_create_flows(client: AsyncClient, logged_in_headers):
    amount_flows = 10
    basic_case = {
        "description": "string",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "tags": ["string"],
    }
    cases = []
    for i in range(amount_flows):
        case = basic_case.copy()
        case["name"] = f"string_{i}"
        case["endpoint_name"] = f"string_{i}"
        cases.append(case)

    response = await client.post("api/v1/flows/batch/", json={"flows": cases}, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, list), "The result must be a list"
    assert len(result) == amount_flows, "The result must have the same amount of flows"


async def test_create_flows_catalog_policy_preflight_is_atomic_and_uses_one_snapshot(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    from langflow.api.v1 import flows
    from lfx.services.catalog_policy import CatalogPolicySnapshot

    blocked_key = "BlockedLateInBatch"

    class RotatingCatalogPolicyService:
        calls = 0

        @property
        def snapshot(self):
            self.calls += 1
            if self.calls == 1:
                return CatalogPolicySnapshot(blocked_component_keys={blocked_key})
            return CatalogPolicySnapshot()

    service = RotatingCatalogPolicyService()
    monkeypatch.setattr(flows, "get_catalog_policy_service", lambda: service)
    allowed_name = f"catalog-batch-allowed-{uuid.uuid4()}"
    blocked_name = f"catalog-batch-blocked-{uuid.uuid4()}"

    response = await client.post(
        "api/v1/flows/batch/",
        json={
            "flows": [
                {"name": allowed_name, "data": _catalog_flow_data("AllowedInBatch")},
                {"name": blocked_name, "data": _catalog_flow_data(blocked_key)},
            ]
        },
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"].endswith(blocked_key)
    assert service.calls == 1

    listed = await client.get("api/v1/flows/", headers=logged_in_headers)
    persisted_names = {flow["name"] for flow in listed.json()}
    assert allowed_name not in persisted_names
    assert blocked_name not in persisted_names


async def test_create_flows_with_explicit_folder(client: AsyncClient, logged_in_headers):
    project_response = await client.post(
        "api/v1/projects/",
        json={"name": "batch-folder-target", "description": "", "flows_list": [], "components_list": []},
        headers=logged_in_headers,
    )
    assert project_response.status_code == status.HTTP_201_CREATED
    project_id = project_response.json()["id"]

    amount_flows = 3
    basic_case = {
        "description": "string",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "tags": ["string"],
        "folder_id": project_id,
    }
    cases = []
    for i in range(amount_flows):
        case = basic_case.copy()
        case["name"] = f"string_folder_{i}"
        case["endpoint_name"] = f"string_folder_{i}"
        cases.append(case)

    response = await client.post("api/v1/flows/batch/", json={"flows": cases}, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, list), "The result must be a list"
    assert len(result) == amount_flows, "The result must have the same amount of flows"
    assert all(item["folder_id"] == project_id for item in result), "All flows must be created in the target folder"


async def test_read_basic_examples(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/flows/basic_examples/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"
    assert len(result) > 0, "The result must have at least one flow"
    assert all(item["name_key"] for item in result)


async def test_read_basic_examples_catalog_policy_preserves_public_cache_and_unblocks(
    client: AsyncClient,
    monkeypatch,
):
    from langflow.api.v1 import flows
    from lfx.services.catalog_policy import CatalogPolicySnapshot

    class MutableCatalogPolicyService:
        snapshot = CatalogPolicySnapshot(blocked_template_keys={"basic_prompting"})

    service = MutableCatalogPolicyService()
    monkeypatch.setattr(flows, "get_catalog_policy_service", lambda: service)
    flows._starter_flows_cache.clear()
    flows._starter_flows_translated_cache.clear()

    blocked_response = await client.get("api/v1/flows/basic_examples/")
    assert blocked_response.status_code == status.HTTP_200_OK, blocked_response.text
    blocked_keys = {flow["name_key"] for flow in blocked_response.json()}
    assert "basic_prompting" not in blocked_keys

    service.snapshot = CatalogPolicySnapshot()
    unblocked_response = await client.get("api/v1/flows/basic_examples/")
    assert unblocked_response.status_code == status.HTTP_200_OK, unblocked_response.text
    unblocked_keys = {flow["name_key"] for flow in unblocked_response.json()}
    assert "basic_prompting" in unblocked_keys


async def test_read_basic_examples_include_blocked_requires_superuser(
    client: AsyncClient,
    logged_in_headers,
):
    anonymous_response = await client.get("api/v1/flows/basic_examples/?include_blocked=true")
    assert anonymous_response.status_code == status.HTTP_403_FORBIDDEN

    denied_response = await client.get(
        "api/v1/flows/basic_examples/?include_blocked=true",
        headers=logged_in_headers,
    )
    assert denied_response.status_code == status.HTTP_403_FORBIDDEN


async def test_read_basic_examples_superuser_can_include_blocked(
    client: AsyncClient,
    logged_in_headers_super_user,
    monkeypatch,
):
    from langflow.api.v1 import flows
    from lfx.services.catalog_policy import CatalogPolicySnapshot

    service = type(
        "CatalogPolicyService",
        (),
        {"snapshot": CatalogPolicySnapshot(blocked_template_keys={"basic_prompting"})},
    )()
    monkeypatch.setattr(flows, "get_catalog_policy_service", lambda: service)

    override_response = await client.get(
        "api/v1/flows/basic_examples/?include_blocked=true",
        headers=logged_in_headers_super_user,
    )
    assert override_response.status_code == status.HTTP_200_OK, override_response.text
    assert "basic_prompting" in {flow["name_key"] for flow in override_response.json()}


async def test_read_flows_user_isolation(client: AsyncClient, logged_in_headers, active_user):
    """Test that read_flows returns only flows from the current user."""
    from uuid import uuid4

    from langflow.services.auth.utils import get_password_hash
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import session_scope

    # Create a second user
    other_user_id = uuid4()
    async with session_scope() as session:
        other_user = User(
            id=other_user_id,
            username="other_test_user",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(other_user)
        await session.commit()
        await session.refresh(other_user)

    # Login as the other user to get headers
    login_data = {"username": "other_test_user", "password": "testpassword"}  # pragma: allowlist secret
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    other_user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Create flows for the first user (active_user)
    flow_user1_1 = {
        "name": "user1_flow_1",
        "description": "Flow 1 for user 1",
        "icon": "string",
        "icon_bg_color": "#ff00ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "user1_flow_1_endpoint",
        "tags": ["user1"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }

    flow_user1_2 = {
        "name": "user1_flow_2",
        "description": "Flow 2 for user 1",
        "icon": "string",
        "icon_bg_color": "#00ff00",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "user1_flow_2_endpoint",
        "tags": ["user1"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }

    # Create flows for the second user
    flow_user2_1 = {
        "name": "user2_flow_1",
        "description": "Flow 1 for user 2",
        "icon": "string",
        "icon_bg_color": "#0000ff",
        "gradient": "string",
        "data": {},
        "is_component": False,
        "webhook": False,
        "endpoint_name": "user2_flow_1_endpoint",
        "tags": ["user2"],
        "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }

    # Create flows using the appropriate user headers
    response1 = await client.post("api/v1/flows/", json=flow_user1_1, headers=logged_in_headers)
    assert response1.status_code == status.HTTP_201_CREATED

    response2 = await client.post("api/v1/flows/", json=flow_user1_2, headers=logged_in_headers)
    assert response2.status_code == status.HTTP_201_CREATED

    response3 = await client.post("api/v1/flows/", json=flow_user2_1, headers=other_user_headers)
    assert response3.status_code == status.HTTP_201_CREATED

    # Test read_flows for user 1 - should only return user 1's flows
    params = {
        "remove_example_flows": True,  # Exclude example flows to focus on our test flows
        "components_only": False,
        "get_all": True,
        "header_flows": False,
        "page": 1,
        "size": 50,
    }

    response_user1 = await client.get("api/v1/flows/", params=params, headers=logged_in_headers)
    result_user1 = response_user1.json()

    assert response_user1.status_code == status.HTTP_200_OK
    assert isinstance(result_user1, list), "The result must be a list"

    # Verify only user 1's flows are returned
    user1_flow_names = [flow["name"] for flow in result_user1]
    assert "user1_flow_1" in user1_flow_names, "User 1's first flow should be returned"
    assert "user1_flow_2" in user1_flow_names, "User 1's second flow should be returned"
    assert "user2_flow_1" not in user1_flow_names, "User 2's flow should not be returned for user 1"

    # Verify all returned flows belong to user 1
    for flow in result_user1:
        assert str(flow["user_id"]) == str(active_user.id), f"Flow {flow['name']} should belong to user 1"

    # Test read_flows for user 2 - should only return user 2's flows
    response_user2 = await client.get("api/v1/flows/", params=params, headers=other_user_headers)
    result_user2 = response_user2.json()

    assert response_user2.status_code == status.HTTP_200_OK
    assert isinstance(result_user2, list), "The result must be a list"

    # Verify only user 2's flows are returned
    user2_flow_names = [flow["name"] for flow in result_user2]
    assert "user2_flow_1" in user2_flow_names, "User 2's flow should be returned"
    assert "user1_flow_1" not in user2_flow_names, "User 1's first flow should not be returned for user 2"
    assert "user1_flow_2" not in user2_flow_names, "User 1's second flow should not be returned for user 2"

    # Verify all returned flows belong to user 2
    for flow in result_user2:
        assert str(flow["user_id"]) == str(other_user_id), f"Flow {flow['name']} should belong to user 2"

    # Cleanup: Delete the other user
    async with session_scope() as session:
        user = await session.get(User, other_user_id)
        if user:
            await session.delete(user)
            await session.commit()


async def test_create_flow_rejects_absolute_path_outside_allowed_directory(client: AsyncClient, logged_in_headers):
    """Test that absolute paths outside the allowed directory are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "/etc/passwd",  # Absolute path outside allowed directory should be rejected
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "within" in response.json()["detail"].lower() or "outside" in response.json()["detail"].lower()


async def test_create_flow_rejects_directory_traversal(client: AsyncClient, logged_in_headers):
    """Test that directory traversal sequences are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "../../etc/passwd",  # Directory traversal should be rejected
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "directory traversal" in response.json()["detail"].lower()
        or "absolute paths" in response.json()["detail"].lower()
    )


async def test_create_flow_rejects_null_bytes(client: AsyncClient, logged_in_headers):
    """Test that null bytes in paths are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "file\x00name.json",  # Null byte should be rejected
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "absolute paths" in response.json()["detail"].lower() or "null" in response.json()["detail"].lower()


async def test_create_flow_rejects_windows_absolute_path_outside_allowed_directory(
    client: AsyncClient, logged_in_headers
):
    """Test that Windows-style absolute paths outside the allowed directory are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "C:\\Windows\\System32\\config\\sam",  # Windows absolute path outside
        # allowed directory should be rejected
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "within" in response.json()["detail"].lower() or "outside" in response.json()["detail"].lower()


async def test_create_flow_accepts_relative_path(client: AsyncClient, logged_in_headers):
    """Test that valid relative paths are accepted."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "my_flow.json",  # Valid relative path
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED


async def test_create_flow_accepts_nested_relative_path(client: AsyncClient, logged_in_headers):
    """Test that nested relative paths are accepted."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "subfolder/my_flow.json",  # Valid nested relative path
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED


async def test_update_flow_rejects_absolute_path_outside_allowed_directory(client: AsyncClient, logged_in_headers):
    """Test that updating a flow with an absolute path outside allowed directory is rejected."""
    # First create a flow
    basic_case = {
        "name": "test_flow",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    # Try to update with absolute path outside allowed directory
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        update_case = {
            "fs_path": temp_file.name,
        }
    update_response = await client.patch(f"api/v1/flows/{flow_id}", json=update_case, headers=logged_in_headers)
    assert update_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "within" in update_response.json()["detail"].lower() or "outside" in update_response.json()["detail"].lower()


async def test_update_flow_accepts_relative_path(client: AsyncClient, logged_in_headers):
    """Test that updating a flow with a relative path is accepted."""
    # First create a flow
    basic_case = {
        "name": "test_flow",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    # Update with valid relative path
    update_case = {
        "fs_path": "updated_flow.json",
    }
    update_response = await client.patch(f"api/v1/flows/{flow_id}", json=update_case, headers=logged_in_headers)
    assert update_response.status_code == status.HTTP_200_OK


async def test_create_flow_rejects_empty_path(client: AsyncClient, logged_in_headers):
    """Test that empty fs_path is handled correctly (should be allowed as None).

    But empty string should fail validation.
    """
    # Empty string should fail validation if fs_path validation is called
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "",  # Empty string
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    # Empty string should be rejected by validation
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_create_flow_allows_none_path(client: AsyncClient, logged_in_headers):
    """Test that None/null fs_path is allowed (no file saving)."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        # fs_path not provided (None)
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED


async def test_create_flow_rejects_multiple_traversal(client: AsyncClient, logged_in_headers):
    """Test that multiple directory traversal sequences are rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "../../../etc/passwd",  # Multiple traversals
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_create_flow_rejects_traversal_in_subpath(client: AsyncClient, logged_in_headers):
    """Test that directory traversal in subpaths is rejected."""
    basic_case = {
        "name": "test_flow",
        "data": {},
        "fs_path": "subfolder/../../etc/passwd",  # Traversal in subpath
    }
    response = await client.post("api/v1/flows/", json=basic_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_upload_flow_rejects_list_payload(client: AsyncClient, logged_in_headers):
    """Regression: uploading a JSON array (not an object) must return 422, not 500.

    orjson.loads() on a list payload returns a Python list.  Before the isinstance
    guard, 'flows' in <list> silently evaluates to False, routing to the else branch
    where **normalize_code_for_import(list) raises TypeError — escaping as a 500.
    """
    import json

    file_content = json.dumps([{"name": "flow1", "data": {}}])

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_upload_flow_rejects_scalar_payload(client: AsyncClient, logged_in_headers):
    """Regression: uploading a JSON scalar (string/number) must return 422, not 500."""
    import json

    file_content = json.dumps("just a string")

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_upload_flow_rejects_endpoint_name_with_dots(client: AsyncClient, logged_in_headers):
    """Regression: endpoint_name containing dots must return 422, not 500.

    Previously a ValidationError from the Pydantic model escaped the handler
    and hit the global exception_handler, producing a 500 and a Scarf telemetry
    event.  The import path now wraps FlowCreate construction in a try/except
    and re-raises as HTTPException(422).
    """
    import json

    flow_data = {
        "name": "neuro-vision",
        "data": {},
        "endpoint_name": "neuro-vision-planning.phase1.contract",
    }
    file_content = json.dumps({"folder_name": "proj", "flows": [flow_data]})

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_upload_flow_accepts_valid_endpoint_name(client: AsyncClient, logged_in_headers):
    """Endpoint names with only letters, numbers, hyphens, and underscores are accepted."""
    import json

    flow_data = {
        "name": "neuro-vision",
        "data": {},
        "endpoint_name": "neuro-vision-planning_phase1",
    }
    file_content = json.dumps({"folder_name": "proj", "flows": [flow_data]})

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["name"] == "neuro-vision"


async def test_upload_catalog_policy_preflights_all_effective_graphs_before_upsert(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    import json

    from langflow.api.v1 import flows
    from lfx.services.catalog_policy import CatalogPolicySnapshot

    class MutableCatalogPolicyService:
        snapshot = CatalogPolicySnapshot()

    service = MutableCatalogPolicyService()
    monkeypatch.setattr(flows, "get_catalog_policy_service", lambda: service)
    blocked_key = "BlockedStoredUploadGraph"
    original_name = f"catalog-upload-source-{uuid.uuid4()}"
    source = await client.post(
        "api/v1/flows/",
        json={"name": original_name, "description": "original", "data": _catalog_flow_data(blocked_key)},
        headers=logged_in_headers,
    )
    assert source.status_code == status.HTTP_201_CREATED, source.text

    mutation_calls = 0

    async def track_unexpected_mutation(**_kwargs):
        nonlocal mutation_calls
        mutation_calls += 1
        return []

    monkeypatch.setattr(flows, "_new_flow", track_unexpected_mutation)
    monkeypatch.setattr(flows, "_update_existing_flow", track_unexpected_mutation)
    service.snapshot = CatalogPolicySnapshot(blocked_component_keys={blocked_key})
    allowed_name = f"catalog-upload-allowed-{uuid.uuid4()}"
    changed_name = f"catalog-upload-changed-{uuid.uuid4()}"
    file_content = json.dumps(
        {
            "flows": [
                {"name": allowed_name, "data": _catalog_flow_data("AllowedInUpload")},
                {
                    "id": source.json()["id"],
                    "name": changed_name,
                    "description": "metadata-only upload update",
                },
            ]
        }
    )

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"].endswith(blocked_key)
    assert mutation_calls == 0

    unchanged = await client.get(f"api/v1/flows/{source.json()['id']}", headers=logged_in_headers)
    assert unchanged.status_code == status.HTTP_200_OK
    assert unchanged.json()["name"] == original_name
    listed = await client.get("api/v1/flows/", headers=logged_in_headers)
    assert allowed_name not in {flow["name"] for flow in listed.json()}


async def test_upload_flow_rejects_absolute_path(client: AsyncClient, logged_in_headers):
    """Test that uploading flows with absolute paths is rejected."""
    import json

    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        flow_data = {
            "name": "test_flow",
            "data": {},
            "fs_path": temp_file.name,  # Absolute path
        }
    # Create a JSON file content
    file_content = json.dumps({"flows": [flow_data]})

    response = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("flows.json", file_content, "application/json")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# PUT endpoint tests (upsert)


async def test_upsert_flow_creates_new_flow_with_specified_id(client: AsyncClient, logged_in_headers):
    """Test that PUT creates a new flow with the specified ID and returns 201."""
    specified_id = str(uuid.uuid4())
    flow_data = {
        "name": "upsert_new_flow",
        "description": "Created via upsert",
        "data": {},
    }

    response = await client.put(f"api/v1/flows/{specified_id}", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()
    assert result["id"] == specified_id
    assert result["name"] == "upsert_new_flow"


async def test_upsert_flow_updates_existing_flow(client: AsyncClient, logged_in_headers):
    """Test that PUT updates an existing flow and returns 200."""
    # First create a flow via POST
    initial_flow = {
        "name": "initial_flow_name",
        "description": "initial description",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    # Now update via PUT
    updated_flow = {
        "name": "updated_flow_name",
        "description": "updated description",
        "data": {"nodes": [], "edges": []},
    }
    response = await client.put(f"api/v1/flows/{flow_id}", json=updated_flow, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["id"] == flow_id
    assert result["name"] == "updated_flow_name"
    assert result["description"] == "updated description"


async def test_upsert_flow_returns_404_for_other_users_flow(client: AsyncClient, logged_in_headers):
    """Test that PUT returns 404 when trying to upsert another user's flow (avoids leaking existence)."""
    from langflow.services.auth.utils import get_password_hash
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import session_scope

    # Create another user
    other_user_id = uuid.uuid4()
    async with session_scope() as session:
        other_user = User(
            id=other_user_id,
            username="other_user_for_upsert_test",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        session.add(other_user)
        await session.commit()

    # Login as other user and create a flow
    login_data = {"username": "other_user_for_upsert_test", "password": "testpassword"}  # pragma: allowlist secret
    login_response = await client.post("api/v1/login", data=login_data)
    assert login_response.status_code == status.HTTP_200_OK, f"Login failed: {login_response.text}"
    other_user_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    flow_data = {"name": "other_user_flow", "data": {}}
    create_response = await client.post("api/v1/flows/", json=flow_data, headers=other_user_headers)
    other_user_flow_id = create_response.json()["id"]

    # Try to upsert other user's flow with original user's credentials
    update_data = {"name": "trying_to_steal", "data": {}}
    response = await client.put(f"api/v1/flows/{other_user_flow_id}", json=update_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()

    # Cleanup
    async with session_scope() as session:
        user = await session.get(User, other_user_id)
        if user:
            await session.delete(user)
            await session.commit()


async def test_upsert_flow_returns_400_for_invalid_folder_id(client: AsyncClient, logged_in_headers):
    """Test that PUT returns 400 when folder_id doesn't exist."""
    specified_id = str(uuid.uuid4())
    non_existent_folder_id = str(uuid.uuid4())
    flow_data = {
        "name": "flow_with_bad_folder",
        "data": {},
        "folder_id": non_existent_folder_id,
    }

    response = await client.put(f"api/v1/flows/{specified_id}", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "folder not found" in response.json()["detail"].lower()


async def test_upsert_flow_returns_409_for_endpoint_name_conflict_on_create(client: AsyncClient, logged_in_headers):
    """Test that PUT returns 409 when endpoint_name conflicts during CREATE."""
    # First create a flow with a specific endpoint_name
    first_flow = {
        "name": "first_flow",
        "endpoint_name": "unique_endpoint",
        "data": {},
    }
    await client.post("api/v1/flows/", json=first_flow, headers=logged_in_headers)

    # Try to create new flow via PUT with same endpoint_name
    specified_id = str(uuid.uuid4())
    second_flow = {
        "name": "second_flow",
        "endpoint_name": "unique_endpoint",  # Same endpoint_name
        "data": {},
    }

    response = await client.put(f"api/v1/flows/{specified_id}", json=second_flow, headers=logged_in_headers)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "endpoint" in response.json()["detail"].lower()


async def test_upsert_flow_auto_renames_name_on_create_conflict(client: AsyncClient, logged_in_headers):
    """Test that PUT auto-renames name when it conflicts during CREATE."""
    # First create a flow with a specific name
    first_flow = {
        "name": "duplicate_name",
        "data": {},
    }
    await client.post("api/v1/flows/", json=first_flow, headers=logged_in_headers)

    # Create new flow via PUT with same name - should auto-rename
    specified_id = str(uuid.uuid4())
    second_flow = {
        "name": "duplicate_name",  # Same name
        "data": {},
    }

    response = await client.put(f"api/v1/flows/{specified_id}", json=second_flow, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()
    assert result["name"] == "duplicate_name (1)"  # Auto-renamed


async def test_upsert_flow_returns_409_for_name_conflict_on_update(client: AsyncClient, logged_in_headers):
    """Test that PUT returns 409 when name conflicts with another flow during UPDATE."""
    # Create two flows
    first_flow = {"name": "flow_one", "data": {}}
    second_flow = {"name": "flow_two", "data": {}}

    await client.post("api/v1/flows/", json=first_flow, headers=logged_in_headers)
    second_response = await client.post("api/v1/flows/", json=second_flow, headers=logged_in_headers)
    second_flow_id = second_response.json()["id"]

    # Try to update second flow to have first flow's name
    update_data = {"name": "flow_one", "data": {}}  # Conflict with first flow

    response = await client.put(f"api/v1/flows/{second_flow_id}", json=update_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "name" in response.json()["detail"].lower()


async def test_upsert_flow_returns_409_for_endpoint_conflict_on_update(client: AsyncClient, logged_in_headers):
    """Test that PUT returns 409 when endpoint_name conflicts with another flow during UPDATE."""
    # Create two flows with different endpoint names
    first_flow = {"name": "endpoint_flow_one", "endpoint_name": "endpoint_one", "data": {}}
    second_flow = {"name": "endpoint_flow_two", "endpoint_name": "endpoint_two", "data": {}}

    await client.post("api/v1/flows/", json=first_flow, headers=logged_in_headers)
    second_response = await client.post("api/v1/flows/", json=second_flow, headers=logged_in_headers)
    second_flow_id = second_response.json()["id"]

    # Try to update second flow to have first flow's endpoint_name
    update_data = {"name": "endpoint_flow_two", "endpoint_name": "endpoint_one", "data": {}}

    response = await client.put(f"api/v1/flows/{second_flow_id}", json=update_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "endpoint" in response.json()["detail"].lower()


async def test_upsert_flow_keeps_existing_folder_on_update_when_not_provided(client: AsyncClient, logged_in_headers):
    """Test that PUT keeps existing folder_id when not provided during UPDATE."""
    # Create a flow (will be assigned to default folder)
    initial_flow = {"name": "folder_test_flow", "data": {}}
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    flow_id = create_response.json()["id"]
    original_folder_id = create_response.json()["folder_id"]

    # Update via PUT without providing folder_id
    update_data = {"name": "folder_test_flow_updated", "data": {}}

    response = await client.put(f"api/v1/flows/{flow_id}", json=update_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["folder_id"] == original_folder_id  # Folder unchanged


async def test_upsert_flow_keeps_existing_endpoint_when_not_provided(client: AsyncClient, logged_in_headers):
    """Test that PUT preserves endpoint_name when it is omitted during update."""
    initial_flow = {
        "name": "upsert_endpoint_flow",
        "endpoint_name": "keep_upsert_endpoint",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    response = await client.put(
        f"api/v1/flows/{flow_id}",
        json={"name": "upsert_endpoint_flow_updated", "data": {}},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["endpoint_name"] == "keep_upsert_endpoint"


async def test_upsert_flow_allows_clearing_endpoint_with_null(client: AsyncClient, logged_in_headers):
    """Test that PUT clears endpoint_name when it is explicitly set to null."""
    initial_flow = {
        "name": "upsert_clear_endpoint_flow",
        "endpoint_name": "clear_upsert_endpoint",
        "data": {},
    }
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]

    response = await client.put(
        f"api/v1/flows/{flow_id}",
        json={"name": "upsert_clear_endpoint_flow", "endpoint_name": None, "data": {}},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["endpoint_name"] is None


async def test_upsert_flow_ignores_user_id_from_body(client: AsyncClient, logged_in_headers, active_user):
    """Test that PUT ignores user_id from body and uses current user."""
    specified_id = str(uuid.uuid4())
    fake_user_id = str(uuid.uuid4())
    flow_data = {
        "name": "security_test_flow",
        "data": {},
        "user_id": fake_user_id,  # Should be ignored
    }

    response = await client.put(f"api/v1/flows/{specified_id}", json=flow_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
    result = response.json()
    assert result["user_id"] == str(active_user.id)  # Should be current user, not fake
    assert result["user_id"] != fake_user_id


async def test_upsert_flow_allows_updating_own_flow_name(client: AsyncClient, logged_in_headers):
    """Test that PUT allows updating a flow to keep the same name (no conflict with itself)."""
    # Create a flow
    initial_flow = {"name": "self_update_flow", "description": "initial", "data": {}}
    create_response = await client.post("api/v1/flows/", json=initial_flow, headers=logged_in_headers)
    flow_id = create_response.json()["id"]

    # Update the flow keeping the same name but changing description
    update_data = {"name": "self_update_flow", "description": "updated", "data": {}}

    response = await client.put(f"api/v1/flows/{flow_id}", json=update_data, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["name"] == "self_update_flow"
    assert result["description"] == "updated"


async def test_delete_flow_with_deployed_versions_returns_409(client: AsyncClient, logged_in_headers, active_user):
    flow_resp = await client.post(
        "api/v1/flows/",
        json={"name": "deployed-delete-flow", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert flow_resp.status_code == status.HTTP_201_CREATED
    flow_payload = flow_resp.json()
    flow_id = UUID(flow_payload["id"])
    source_project_id = UUID(flow_payload["folder_id"])

    await _attach_deployment_to_flow(
        user_id=active_user.id,
        flow_id=flow_id,
        project_id=source_project_id,
    )

    delete_resp = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert delete_resp.status_code == status.HTTP_409_CONFLICT
    assert "cannot be deleted because it has deployed versions" in delete_resp.json()["detail"].lower()


async def test_bulk_delete_with_deployed_flow_returns_409(client: AsyncClient, logged_in_headers, active_user):
    deployed_flow_resp = await client.post(
        "api/v1/flows/",
        json={"name": "deployed-bulk-flow", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert deployed_flow_resp.status_code == status.HTTP_201_CREATED
    deployed_payload = deployed_flow_resp.json()
    deployed_flow_id = UUID(deployed_payload["id"])
    source_project_id = UUID(deployed_payload["folder_id"])

    undeployed_flow_resp = await client.post(
        "api/v1/flows/",
        json={"name": "undeployed-bulk-flow", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert undeployed_flow_resp.status_code == status.HTTP_201_CREATED
    undeployed_flow_id = undeployed_flow_resp.json()["id"]

    await _attach_deployment_to_flow(
        user_id=active_user.id,
        flow_id=deployed_flow_id,
        project_id=source_project_id,
    )

    delete_resp = await client.request(
        "DELETE",
        "api/v1/flows/",
        json=[str(deployed_flow_id), undeployed_flow_id],
        headers=logged_in_headers,
    )
    assert delete_resp.status_code == status.HTTP_409_CONFLICT
    assert "cannot be deleted because it has deployed versions" in delete_resp.json()["detail"].lower()


async def test_delete_flow_retries_transient_sqlite_lock(client: AsyncClient, logged_in_headers, monkeypatch):
    """A transient SQLite lock retries the complete single-flow deletion."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from sqlalchemy.exc import OperationalError

    create_response = await client.post(
        "api/v1/flows/",
        json={"name": f"delete-lock-retry-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_id = create_response.json()["id"]
    original_delete = flows_module.cascade_delete_flow
    attempts = {"count": 0}
    statement = "DELETE FROM flow WHERE flow.id = ?"

    async def delete_after_one_lock(session, target_flow_id):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OperationalError(
                statement,
                {"id": target_flow_id},
                sqlite3.OperationalError("database is locked"),
            )
        return await original_delete(session, target_flow_id)

    monkeypatch.setattr(flows_module, "cascade_delete_flow", delete_after_one_lock)

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert attempts["count"] == 2
    read_response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert read_response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_flow_exhausted_lock_retries_return_sanitized_503(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    """Exhausted single-flow lock retries expose no SQL or bound values."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.lock_retry import DEFAULT_LOCK_RETRY_ATTEMPTS
    from sqlalchemy.exc import OperationalError

    create_response = await client.post(
        "api/v1/flows/",
        json={"name": f"delete-lock-exhausted-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    flow_id = create_response.json()["id"]
    leaked_statement = "DELETE FROM flow WHERE flow.id = ?"
    leaked_value = f"secret-bound-value-{uuid.uuid4()}"
    attempts = {"count": 0}

    async def always_locked(_session, _target_flow_id):
        attempts["count"] += 1
        raise OperationalError(
            leaked_statement,
            {"id": flow_id, "value": leaked_value},
            sqlite3.OperationalError("database is locked"),
        )

    monkeypatch.setattr(flows_module, "cascade_delete_flow", always_locked)
    original_retry = flows_module.run_with_lock_retry

    async def run_without_delay(operation, *, session, description):
        return await original_retry(operation, session=session, description=description, base_delay=0)

    monkeypatch.setattr(flows_module, "run_with_lock_retry", run_without_delay)

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    assert attempts["count"] == DEFAULT_LOCK_RETRY_ATTEMPTS
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.headers["Retry-After"] == "1"
    detail = response.json()["detail"]
    assert detail == flows_module.FLOW_DELETE_BUSY
    assert leaked_statement not in detail
    assert leaked_value not in detail
    assert flow_id not in detail
    assert "sqlalche.me" not in detail


async def test_delete_flow_non_lock_failure_returns_sanitized_500(client: AsyncClient, logged_in_headers, monkeypatch):
    """A non-lock failure is not retried and does not disclose exception details."""
    from langflow.api.v1 import flows as flows_module

    create_response = await client.post(
        "api/v1/flows/",
        json={"name": f"delete-non-lock-failure-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    flow_id = create_response.json()["id"]
    leaked_detail = f"sensitive-delete-detail-{uuid.uuid4()}"
    attempts = {"count": 0}

    async def fail_delete(_session, _target_flow_id):
        attempts["count"] += 1
        raise RuntimeError(leaked_detail)

    monkeypatch.setattr(flows_module, "cascade_delete_flow", fail_delete)

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    assert attempts["count"] == 1
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == flows_module.FLOW_DELETE_FAILED
    assert leaked_detail not in response.text
    assert "Retry-After" not in response.headers


async def test_delete_flow_real_competing_sqlite_writer_is_retried(client: AsyncClient, logged_in_headers, monkeypatch):
    """A real second SQLite connection holding the write lock triggers a retry."""
    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.deps import session_scope
    from sqlalchemy import text

    create_response = await client.post(
        "api/v1/flows/",
        json={"name": f"delete-real-lock-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    flow_id = create_response.json()["id"]
    original_delete = flows_module.cascade_delete_flow
    attempts = {"count": 0}

    async def delete_after_competing_commit(session, target_flow_id):
        attempts["count"] += 1
        if attempts["count"] == 1:
            async with session_scope() as competing_session:
                competing_session.add(Folder(name=f"delete-competing-write-{uuid.uuid4()}", user_id=None))
                await competing_session.flush()
                # The second connection now holds SQLite's write lock. Disable
                # waiting on the route connection so its real DELETE reports
                # the lock immediately and exercises the retry boundary.
                await session.exec(text("PRAGMA busy_timeout = 0"))
                return await original_delete(session, target_flow_id)
        return await original_delete(session, target_flow_id)

    monkeypatch.setattr(flows_module, "cascade_delete_flow", delete_after_competing_commit)

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert attempts["count"] >= 2
    read_response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert read_response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_flow_retry_is_idempotent_when_concurrent_delete_wins(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    """A retry treats an already-deleted target as successful."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.deps import session_scope
    from sqlalchemy.exc import OperationalError

    create_response = await client.post(
        "api/v1/flows/",
        json={"name": f"delete-concurrent-winner-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    flow_id = UUID(create_response.json()["id"])
    attempts = {"count": 0}
    statement = "DELETE FROM flow WHERE flow.id = ?"

    async def concurrent_delete_then_lock(_session, target_flow_id):
        attempts["count"] += 1
        async with session_scope() as competing_session:
            target = await competing_session.get(Flow, target_flow_id)
            if target is not None:
                await competing_session.delete(target)
        raise OperationalError(statement, {"id": target_flow_id}, sqlite3.OperationalError("database is locked"))

    monkeypatch.setattr(flows_module, "cascade_delete_flow", concurrent_delete_then_lock)

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert attempts["count"] == 1


async def test_delete_flow_retry_preserves_permission_denial(client: AsyncClient, logged_in_headers, monkeypatch):
    """A retry-time authorization denial remains a 403 instead of becoming a 500."""
    import sqlite3

    from fastapi import HTTPException
    from langflow.api.v1 import flows as flows_module
    from sqlalchemy.exc import OperationalError

    create_response = await client.post(
        "api/v1/flows/",
        json={"name": f"delete-retry-denied-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    flow_id = create_response.json()["id"]
    statement = "DELETE FROM flow WHERE flow.id = ?"

    async def locked_once(_session, target_flow_id):
        raise OperationalError(statement, {"id": target_flow_id}, sqlite3.OperationalError("database is locked"))

    async def deny_retry(*_args, **_kwargs):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="delete permission revoked")

    monkeypatch.setattr(flows_module, "cascade_delete_flow", locked_once)
    monkeypatch.setattr(flows_module, "ensure_flow_permission", deny_retry)
    original_retry = flows_module.run_with_lock_retry

    async def run_without_delay(operation, *, session, description):
        return await original_retry(operation, session=session, description=description, base_delay=0)

    monkeypatch.setattr(flows_module, "run_with_lock_retry", run_without_delay)

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "delete permission revoked"


async def test_delete_flow_deployment_guard_retry_reauthorizes_before_second_cascade(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    """A deployment-guard retry must reauthorize before attempting the delete again."""
    from fastapi import HTTPException
    from langflow.api.v1 import flows as flows_module
    from langflow.api.v1.mappers.deployments import sync as deployment_sync
    from langflow.services.database.models.deployment.exceptions import DeploymentGuardError

    create_response = await client.post(
        "api/v1/flows/",
        json={"name": f"delete-deployment-retry-denied-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    flow_payload = create_response.json()
    flow_id = UUID(flow_payload["id"])
    owner_id = UUID(flow_payload["user_id"])
    permission_attempts = 0
    cascade_attempts = 0
    repair_owner_maps: list[dict[UUID, UUID]] = []

    async def allow_then_deny(*_args, **_kwargs):
        nonlocal permission_attempts
        permission_attempts += 1
        if permission_attempts == 2:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="delete permission revoked")

    async def fail_deployment_guard_once(_session, _target_flow_id):
        nonlocal cascade_attempts
        cascade_attempts += 1
        raise DeploymentGuardError(
            code="FLOW_HAS_DEPLOYED_VERSIONS",
            technical_detail="Flow is deployed.",
            detail="Flow is deployed.",
        )

    async def record_deployment_repair(*, db, flow_owner_ids):  # noqa: ARG001
        repair_owner_maps.append(dict(flow_owner_ids))

    monkeypatch.setattr(flows_module, "ensure_flow_permission", allow_then_deny)
    monkeypatch.setattr(flows_module, "cascade_delete_flow", fail_deployment_guard_once)
    monkeypatch.setattr(deployment_sync, "sync_flow_deployment_state_by_owner", record_deployment_repair)

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "delete permission revoked"
    assert permission_attempts == 2
    assert cascade_attempts == 1
    assert repair_owner_maps == [{flow_id: owner_id}]
    read_response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert read_response.status_code == status.HTTP_200_OK


async def test_bulk_delete_retries_transient_sqlite_lock(client: AsyncClient, logged_in_headers, monkeypatch):
    """A transient SQLite lock retries the complete bulk deletion transaction."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from sqlalchemy.exc import OperationalError

    flow_ids = []
    for index in range(2):
        create_response = await client.post(
            "api/v1/flows/",
            json={"name": f"bulk-delete-lock-{index}-{uuid.uuid4()}", "data": {}},
            headers=logged_in_headers,
        )
        flow_ids.append(create_response.json()["id"])

    original_delete = flows_module.cascade_delete_flow
    attempts = {"count": 0}
    statement = "DELETE FROM flow WHERE flow.id = ?"

    async def delete_after_one_lock(session, target_flow_id):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OperationalError(
                statement,
                {"id": target_flow_id},
                sqlite3.OperationalError("database is locked"),
            )
        return await original_delete(session, target_flow_id)

    monkeypatch.setattr(flows_module, "cascade_delete_flow", delete_after_one_lock)

    response = await client.request("DELETE", "api/v1/flows/", json=flow_ids, headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == {"deleted": 2}
    assert attempts["count"] == 3
    for flow_id in flow_ids:
        assert (
            await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
        ).status_code == status.HTTP_404_NOT_FOUND


async def test_bulk_delete_retry_rebuilds_authorized_owner_map(client: AsyncClient, logged_in_headers, monkeypatch):
    """A retry passes the deployment guard only owners reloaded after rollback."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.deps import session_scope
    from sqlalchemy.exc import OperationalError

    flow_ids = []
    for index in range(2):
        create_response = await client.post(
            "api/v1/flows/",
            json={"name": f"bulk-delete-owner-reload-{index}-{uuid.uuid4()}", "data": {}},
            headers=logged_in_headers,
        )
        flow_ids.append(UUID(create_response.json()["id"]))

    original_delete = flows_module.cascade_delete_flow
    guard_maps: list[dict[UUID, UUID]] = []
    first_delete = True
    statement = "DELETE FROM flow WHERE flow.id = ?"

    async def delete_after_concurrent_removal(session, target_flow_id):
        nonlocal first_delete
        if first_delete:
            first_delete = False
            async with session_scope() as competing_session:
                removed = await competing_session.get(Flow, flow_ids[1])
                assert removed is not None
                await competing_session.delete(removed)
            raise OperationalError(
                statement,
                {"id": target_flow_id},
                sqlite3.OperationalError("database is locked"),
            )
        return await original_delete(session, target_flow_id)

    async def record_guard_map(*, db, flow_owner_ids, operation):  # noqa: ARG001
        try:
            return await operation()
        finally:
            guard_maps.append(dict(flow_owner_ids))

    monkeypatch.setattr(flows_module, "cascade_delete_flow", delete_after_concurrent_removal)
    monkeypatch.setattr(flows_module, "retry_flow_operation_on_deployment_guard", record_guard_map)

    response = await client.request(
        "DELETE",
        "api/v1/flows/",
        json=[str(flow_id) for flow_id in flow_ids],
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == {"deleted": 1}
    assert set(guard_maps[0]) == set(flow_ids)
    assert set(guard_maps[1]) == {flow_ids[0]}


async def test_bulk_delete_exhausted_lock_retries_return_sanitized_503(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    """Exhausted bulk-delete lock retries expose no SQL or bound values."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.lock_retry import DEFAULT_LOCK_RETRY_ATTEMPTS
    from sqlalchemy.exc import OperationalError

    create_response = await client.post(
        "api/v1/flows/",
        json={"name": f"bulk-delete-lock-exhausted-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    flow_id = create_response.json()["id"]
    leaked_statement = "DELETE FROM flow WHERE flow.id = ?"
    leaked_value = f"secret-bound-value-{uuid.uuid4()}"
    attempts = {"count": 0}

    async def always_locked(_session, _target_flow_id):
        attempts["count"] += 1
        raise OperationalError(
            leaked_statement,
            {"id": flow_id, "value": leaked_value},
            sqlite3.OperationalError("database is locked"),
        )

    monkeypatch.setattr(flows_module, "cascade_delete_flow", always_locked)
    original_retry = flows_module.run_with_lock_retry

    async def run_without_delay(operation, *, session, description):
        return await original_retry(operation, session=session, description=description, base_delay=0)

    monkeypatch.setattr(flows_module, "run_with_lock_retry", run_without_delay)

    response = await client.request("DELETE", "api/v1/flows/", json=[flow_id], headers=logged_in_headers)

    assert attempts["count"] == DEFAULT_LOCK_RETRY_ATTEMPTS
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.headers["Retry-After"] == "1"
    detail = response.json()["detail"]
    assert detail == flows_module.FLOW_DELETE_BUSY
    assert leaked_statement not in detail
    assert leaked_value not in detail
    assert flow_id not in detail
    assert "sqlalche.me" not in detail


async def test_patch_flow_folder_move_with_deployed_versions_returns_409(
    client: AsyncClient, logged_in_headers, active_user
):
    flow_resp = await client.post(
        "api/v1/flows/",
        json={"name": "deployed-patch-flow", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert flow_resp.status_code == status.HTTP_201_CREATED
    flow_payload = flow_resp.json()
    flow_id = flow_payload["id"]
    source_project_id = UUID(flow_payload["folder_id"])

    project_resp = await client.post(
        "api/v1/projects/",
        json={"name": "patch-target-project", "description": "", "flows_list": [], "components_list": []},
        headers=logged_in_headers,
    )
    assert project_resp.status_code == status.HTTP_201_CREATED
    target_project_id = project_resp.json()["id"]

    await _attach_deployment_to_flow(
        user_id=active_user.id,
        flow_id=UUID(flow_id),
        project_id=source_project_id,
    )

    patch_resp = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"folder_id": target_project_id},
        headers=logged_in_headers,
    )
    assert patch_resp.status_code == status.HTTP_409_CONFLICT
    assert "cannot be moved to another project" in patch_resp.json()["detail"].lower()


async def test_patch_flow_folder_move_recovers_from_concurrent_write_lock(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    """A competing SQLite commit must not turn a flow move into a 500."""
    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.deps import session_scope

    project_payload = {"description": "", "flows_list": [], "components_list": []}
    source_response = await client.post(
        "api/v1/projects/",
        json={**project_payload, "name": f"lock-source-{uuid.uuid4()}"},
        headers=logged_in_headers,
    )
    destination_response = await client.post(
        "api/v1/projects/",
        json={**project_payload, "name": f"lock-destination-{uuid.uuid4()}"},
        headers=logged_in_headers,
    )
    assert source_response.status_code == status.HTTP_201_CREATED
    assert destination_response.status_code == status.HTTP_201_CREATED
    source_project_id = source_response.json()["id"]
    destination_project_id = destination_response.json()["id"]

    flow_response = await client.post(
        "api/v1/flows/",
        json={"name": f"contended-move-{uuid.uuid4()}", "data": {}, "folder_id": source_project_id},
        headers=logged_in_headers,
    )
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    original_read_flow = flows_module._read_flow
    attempts = {"count": 0}

    async def read_flow_with_competing_commit(*args, **kwargs):
        db_flow = await original_read_flow(*args, **kwargs)
        attempts["count"] += 1
        if attempts["count"] == 1:
            async with session_scope() as competing_session:
                competing_session.add(Folder(name=f"competing-write-{uuid.uuid4()}", user_id=None))
        return db_flow

    monkeypatch.setattr(flows_module, "_read_flow", read_flow_with_competing_commit)

    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"folder_id": destination_project_id},
        headers=logged_in_headers,
    )

    assert patch_response.status_code == status.HTTP_200_OK, patch_response.text
    assert attempts["count"] >= 2, "the PATCH did not retry after its first stale-snapshot write failed"
    assert patch_response.json()["folder_id"] == destination_project_id

    persisted_response = await client.get(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert persisted_response.status_code == status.HTTP_200_OK
    assert persisted_response.json()["folder_id"] == destination_project_id


async def test_patch_flow_exhausted_lock_retries_do_not_leak_sql(client: AsyncClient, logged_in_headers, monkeypatch):
    """An exhausted SQLite lock retry returns a safe, retryable response."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from langflow.services.database.lock_retry import DEFAULT_LOCK_RETRY_ATTEMPTS
    from sqlalchemy.exc import OperationalError

    flow_response = await client.post(
        "api/v1/flows/",
        json={"name": f"locked-patch-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    leaked_statement = "UPDATE flow SET description = ? WHERE flow.id = ?"
    leaked_value = "bound-description-value"
    attempts = {"count": 0}

    async def always_locked(**_kwargs):
        attempts["count"] += 1
        raise OperationalError(
            leaked_statement,
            {"description": leaked_value, "id": flow_id},
            sqlite3.OperationalError("database is locked"),
        )

    monkeypatch.setattr(flows_module, "_patch_flow", always_locked)
    original_retry = flows_module.run_with_lock_retry

    async def run_without_delay(operation, *, session, description):
        return await original_retry(operation, session=session, description=description, base_delay=0)

    monkeypatch.setattr(flows_module, "run_with_lock_retry", run_without_delay)

    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"description": leaked_value},
        headers=logged_in_headers,
    )

    assert attempts["count"] == DEFAULT_LOCK_RETRY_ATTEMPTS
    assert patch_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert patch_response.headers["Retry-After"] == "1"
    detail = patch_response.json()["detail"]
    assert detail == flows_module.FLOW_UPDATE_BUSY
    assert "UPDATE flow" not in detail
    assert "sqlalche.me" not in detail
    assert flow_id not in detail
    assert leaked_value not in detail


async def test_patch_flow_lock_retry_supports_api_key_user(
    client: AsyncClient, logged_in_headers, created_api_key, monkeypatch
):
    """Retrying must work when authentication returns a detached UserRead."""
    import sqlite3

    from langflow.api.v1 import flows as flows_module
    from sqlalchemy.exc import OperationalError

    flow_response = await client.post(
        "api/v1/flows/",
        json={"name": f"api-key-lock-retry-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    assert flow_response.status_code == status.HTTP_201_CREATED
    flow_id = flow_response.json()["id"]

    original_patch_flow = flows_module._patch_flow
    attempts = {"count": 0}
    statement = "UPDATE flow SET description = ? WHERE flow.id = ?"

    async def patch_after_one_lock(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OperationalError(
                statement,
                {"description": "updated", "id": flow_id},
                sqlite3.OperationalError("database is locked"),
            )
        return await original_patch_flow(**kwargs)

    monkeypatch.setattr(flows_module, "_patch_flow", patch_after_one_lock)

    patch_response = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"description": "updated"},
        headers={"x-api-key": created_api_key.api_key},
    )

    assert attempts["count"] == 2
    assert patch_response.status_code == status.HTTP_200_OK, patch_response.text
    assert patch_response.json()["description"] == "updated"


async def test_patch_flow_unique_value_with_lock_text_is_not_retried(client: AsyncClient, logged_in_headers):
    """Bound values that mention lock text must remain ordinary constraint errors."""
    marker = f"database is locked {uuid.uuid4()}"
    existing_response = await client.post(
        "api/v1/flows/",
        json={"name": marker, "data": {}},
        headers=logged_in_headers,
    )
    victim_response = await client.post(
        "api/v1/flows/",
        json={"name": f"unique-lock-marker-{uuid.uuid4()}", "data": {}},
        headers=logged_in_headers,
    )
    assert existing_response.status_code == status.HTTP_201_CREATED
    assert victim_response.status_code == status.HTTP_201_CREATED

    patch_response = await client.patch(
        f"api/v1/flows/{victim_response.json()['id']}",
        json={"name": marker},
        headers=logged_in_headers,
    )

    assert patch_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "must be unique" in patch_response.json()["detail"].lower()


async def test_upsert_flow_folder_move_with_deployed_versions_returns_409(
    client: AsyncClient, logged_in_headers, active_user
):
    flow_resp = await client.post(
        "api/v1/flows/",
        json={"name": "deployed-put-flow", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert flow_resp.status_code == status.HTTP_201_CREATED
    flow_payload = flow_resp.json()
    flow_id = flow_payload["id"]
    source_project_id = UUID(flow_payload["folder_id"])

    project_resp = await client.post(
        "api/v1/projects/",
        json={"name": "put-target-project", "description": "", "flows_list": [], "components_list": []},
        headers=logged_in_headers,
    )
    assert project_resp.status_code == status.HTTP_201_CREATED
    target_project_id = project_resp.json()["id"]

    await _attach_deployment_to_flow(
        user_id=active_user.id,
        flow_id=UUID(flow_id),
        project_id=source_project_id,
    )

    put_resp = await client.put(
        f"api/v1/flows/{flow_id}",
        json={
            "name": "deployed-put-flow-updated",
            "data": {"nodes": [], "edges": []},
            "folder_id": target_project_id,
        },
        headers=logged_in_headers,
    )
    assert put_resp.status_code == status.HTTP_409_CONFLICT
    assert "cannot be moved to another project" in put_resp.json()["detail"].lower()


# _handle_unique_constraint_error: backend-agnostic mapping of unique violations.
#
# These are direct unit tests because the integration suite only ever runs SQLite, so the
# PostgreSQL branch — the one that matters for the deployment this feature targets — has no other
# coverage. Before this, a PostgreSQL unique violation fell through to a 500 whose detail was the
# whole SQLAlchemy string, i.e. the statement plus its bound parameters.


class _FakePgDriverError(Exception):
    """Stand-in for a psycopg driver exception, which exposes the SQLSTATE."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__("duplicate key")
        self.sqlstate = sqlstate


class _FakeDbError(Exception):
    """Stand-in for sqlalchemy.exc.IntegrityError, which wraps the driver exception in .orig."""

    def __init__(self, message: str, orig: Exception | None = None) -> None:
        super().__init__(message)
        self.orig = orig


def test_handle_unique_constraint_error_sqlite_composite_constraint():
    """The (user_id, name) constraint must name the field, not the table."""
    from langflow.api.v1.flows import _handle_unique_constraint_error

    exc = _FakeDbError("(sqlite3.IntegrityError) UNIQUE constraint failed: flow.user_id, flow.name")
    result = _handle_unique_constraint_error(exc, status_code=status.HTTP_409_CONFLICT)

    assert result.status_code == status.HTTP_409_CONFLICT
    assert result.detail == "Name must be unique"


def test_handle_unique_constraint_error_sqlite_endpoint_name():
    from langflow.api.v1.flows import _handle_unique_constraint_error

    exc = _FakeDbError("(sqlite3.IntegrityError) UNIQUE constraint failed: flow.user_id, flow.endpoint_name")
    result = _handle_unique_constraint_error(exc, status_code=status.HTTP_409_CONFLICT)

    assert result.detail == "Endpoint name must be unique"


def test_handle_unique_constraint_error_postgres_is_a_conflict_not_a_leaking_500():
    """A PostgreSQL unique violation must map to the conflict status, not fall through to 500."""
    from langflow.api.v1.flows import _handle_unique_constraint_error

    message = (
        '(psycopg.errors.UniqueViolation) duplicate key value violates unique constraint "unique_flow_name"\n'
        "DETAIL:  Key (user_id, name)=(abc, my-flow) already exists.\n"
        "[SQL: INSERT INTO flow (id, name) VALUES (%(id)s, %(name)s)]\n"
        "[parameters: {'id': 'abc', 'name': 'my-flow'}]"
    )
    exc = _FakeDbError(message, orig=_FakePgDriverError("23505"))
    result = _handle_unique_constraint_error(exc, status_code=status.HTTP_409_CONFLICT)

    assert result.status_code == status.HTTP_409_CONFLICT
    assert result.detail == "Name must be unique"
    assert "SQL" not in result.detail
    assert "parameters" not in result.detail


def test_handle_unique_constraint_error_primary_key_is_not_reported_as_a_name_conflict():
    """A concurrent upsert at the same id collides on the PK, not on (user_id, name)."""
    from langflow.api.v1.flows import _handle_unique_constraint_error

    exc = _FakeDbError("(sqlite3.IntegrityError) UNIQUE constraint failed: folder.id")
    result = _handle_unique_constraint_error(exc, status_code=status.HTTP_409_CONFLICT)

    assert result.status_code == status.HTTP_409_CONFLICT
    assert result.detail == "A project with this ID already exists"


def test_handle_unique_constraint_error_non_unique_error_is_sanitized():
    """Anything that is not a unique violation still becomes a 500, but must not echo the SQL."""
    from langflow.api.v1.flows import _handle_unique_constraint_error
    from sqlalchemy.exc import OperationalError

    exc = OperationalError("SELECT * FROM flow WHERE id = %(id)s", {"id": "secret-value"}, Exception("boom"))
    result = _handle_unique_constraint_error(exc)

    assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "secret-value" not in result.detail
    assert "SELECT" not in result.detail

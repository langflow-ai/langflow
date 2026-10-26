"""Exercise exact-resource ceilings through public list and mutation routes."""

from contextlib import contextmanager
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from langflow.services.auth.context import get_current_auth_context
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_settings_service, get_storage_service, session_scope
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE
from lfx.services.authorization import ResourceVisibilityScope
from lfx.services.settings.feature_flags import FEATURE_FLAGS

from tests.unit.services.authorization._policy_double import install_policy_authz


@contextmanager
def exact_resource_plugin(monkeypatch, *, structured=True):
    settings = get_settings_service()
    monkeypatch.setattr(settings.auth_settings, "API_KEY_SCOPES_ENABLED", True)
    with install_policy_authz(settings) as service:

        async def enforce(*, obj, act, context=None, **_kwargs):
            if not context or not context.get("api_key_restricted"):
                return True
            return any(
                obj.startswith(f"{grant['resource_type']}:")
                and act in grant["actions"]
                and (not grant.get("resource_ids") or obj.split(":", 1)[1] in grant["resource_ids"])
                for grant in context["api_key_permissions"]["restrictions"]
            )

        async def visibility(*, resource_type, **_kwargs):
            if not structured:
                return None
            credential = get_current_auth_context()
            if credential is None or not credential.api_key_restricted:
                return ResourceVisibilityScope(all_resources=True)
            ids = tuple(
                UUID(identifier)
                for grant in credential.api_key_permissions["restrictions"]
                if grant["resource_type"] == resource_type and "read" in grant["actions"]
                for identifier in grant.get("resource_ids", [])
            )
            return ResourceVisibilityScope(
                all_resources=True, intersections=(ResourceVisibilityScope(resource_ids=ids),)
            )

        monkeypatch.setattr(service, "validate_api_key_permissions", AsyncMock())
        monkeypatch.setattr(service, "enforce", enforce)
        monkeypatch.setattr(service, "get_resource_visibility", visibility)

        async def batch_enforce(*, requests, context=None, **kwargs):
            return [await enforce(obj=obj, act=act, context=context, **kwargs) for obj, act in requests]

        monkeypatch.setattr(service, "batch_enforce", batch_enforce)
        yield service


async def scoped_headers(client, logged_in_headers, *, resource_type, resource_ids=None, actions=None):
    response = await client.post(
        "api/v1/api_key/",
        headers=logged_in_headers,
        json={
            "name": "Exact resources",
            "permissions": {
                "restrictions": [
                    {
                        "resource_type": resource_type,
                        "actions": actions or ["read"],
                        **(
                            {"resource_ids": [str(value) for value in resource_ids]} if resource_ids is not None else {}
                        ),
                    }
                ]
            },
        },
    )
    assert response.status_code == 200, response.text
    client.cookies.clear()
    return {"x-api-key": response.json()["api_key"]}


@pytest.mark.parametrize(
    "resource_type",
    [
        "file",
        "variable",
        "knowledge_base",
        pytest.param(
            "provider_account",
            marks=pytest.mark.skipif(
                not FEATURE_FLAGS.wxo_deployments,
                reason="Deployment routes require their feature flag",
            ),
        ),
    ],
)
@pytest.mark.parametrize("structured", [True, False])
async def test_exact_resource_key_lists_selected_row(
    client,
    logged_in_headers,
    active_user,
    monkeypatch,
    resource_type,
    structured,
):
    def make_row():
        values = {"user_id": active_user.id, "name": f"scoped-{uuid4().hex}"}
        if resource_type == "file":
            return File(**values, path="unused", size=1)
        if resource_type == "variable":
            return Variable(**values, value="generic", type=GENERIC_TYPE)
        if resource_type == "knowledge_base":
            return KnowledgeBaseRecord(**values)
        from langflow.services.auth.utils import encrypt_api_key

        return DeploymentProviderAccount(
            **values,
            provider_key=DeploymentProviderKey.WATSONX_ORCHESTRATE,
            provider_url="https://example.invalid",
            provider_tenant_id=uuid4().hex,
            api_key=encrypt_api_key(uuid4().hex),
        )

    rows = [make_row() for _ in range(2)]
    async with session_scope() as session:
        session.add_all(rows)
    with exact_resource_plugin(monkeypatch, structured=structured):
        headers = await scoped_headers(
            client, logged_in_headers, resource_type=resource_type, resource_ids=[rows[0].id]
        )
        path = {
            "file": "api/v2/files/",
            "variable": "api/v1/variables/",
            "knowledge_base": "api/v1/knowledge_bases/",
            "provider_account": "api/v1/deployments/providers?page=1&size=1",
        }[resource_type]
        response = await client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        if resource_type == "provider_account":
            assert body["total"] == 1
            body = body["provider_accounts"]
        assert {row["id"] for row in body} == {str(rows[0].id)}


@pytest.mark.parametrize("operation", ["create", "write", "delete"])
async def test_restricted_key_cannot_mutate_credential_variables(
    client, logged_in_headers, active_user, monkeypatch, operation
):
    row = Variable(user_id=active_user.id, name=f"secret-{uuid4().hex}", value="unused", type=CREDENTIAL_TYPE)
    async with session_scope() as session:
        session.add(row)
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(
            client,
            logged_in_headers,
            resource_type="variable",
            resource_ids=None if operation == "create" else [row.id],
            actions=[operation],
        )
        if operation == "create":
            response = await client.post(
                "api/v1/variables/",
                headers=headers,
                json={"name": "new-secret", "value": "unused", "type": CREDENTIAL_TYPE, "default_fields": []},
            )
        elif operation == "write":
            response = await client.patch(
                f"api/v1/variables/{row.id}", headers=headers, json={"id": str(row.id), "value": "changed"}
            )
        else:
            response = await client.delete(f"api/v1/variables/{row.id}", headers=headers)
        assert response.status_code in {403, 404}, response.text


async def test_restricted_key_can_mutate_generic_variables(client, logged_in_headers, monkeypatch):
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(
            client,
            logged_in_headers,
            resource_type="variable",
            actions=["create", "write", "delete"],
        )
        created = await client.post(
            "api/v1/variables/",
            headers=headers,
            json={
                "name": "generic-scoped-value",
                "value": "before",
                "type": GENERIC_TYPE,
                "default_fields": [],
            },
        )
        assert created.status_code == 201, created.text
        identifier = created.json()["id"]
        updated = await client.patch(
            f"api/v1/variables/{identifier}", headers=headers, json={"id": identifier, "value": "after"}
        )
        assert updated.status_code == 200, updated.text
        deleted = await client.delete(f"api/v1/variables/{identifier}", headers=headers)
        assert deleted.status_code == 204, deleted.text


@pytest.mark.parametrize("operation", ["write", "delete"])
async def test_credential_denial_preserves_uuid_privacy(client, logged_in_headers, active_user, monkeypatch, operation):
    row = Variable(user_id=active_user.id, name="inaccessible-secret", value="unused", type=CREDENTIAL_TYPE)
    async with session_scope() as session:
        session.add(row)
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(
            client, logged_in_headers, resource_type="variable", resource_ids=[uuid4()], actions=[operation]
        )
        if operation == "write":
            response = await client.patch(
                f"api/v1/variables/{row.id}", headers=headers, json={"id": str(row.id), "value": "unused"}
            )
        else:
            response = await client.delete(f"api/v1/variables/{row.id}", headers=headers)
        assert response.status_code == 404, response.text


@pytest.mark.parametrize("ephemeral", [True, False])
@pytest.mark.parametrize("recorded", [True, False])
@pytest.mark.parametrize("can_write", [True, False])
async def test_appending_existing_file_requires_its_write_permission(
    client, logged_in_headers, active_user, monkeypatch, tmp_path, ephemeral, recorded, can_write
):
    import anyio

    row = File(user_id=active_user.id, name="existing", path=f"{active_user.id}/existing.txt", size=6)
    if recorded:
        async with session_scope() as session:
            session.add(row)
    storage = get_storage_service()
    monkeypatch.setattr(storage, "data_dir", anyio.Path(tmp_path))
    await storage.save_file(flow_id=str(active_user.id), file_name="existing.txt", data=b"before")
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(
            client, logged_in_headers, resource_type="file", actions=["create", "write"] if can_write else ["create"]
        )
        response = await client.post(
            "api/v2/files/",
            headers=headers,
            params={"append": True, "ephemeral": ephemeral},
            files={"file": ("existing.txt", b"after", "text/plain")},
        )
        allowed = recorded and can_write
        assert response.status_code == (201 if allowed else 403), response.text
        assert await storage.get_file(flow_id=str(active_user.id), file_name="existing.txt") == (
            b"beforeafter" if allowed else b"before"
        )


async def test_create_only_key_can_upload_new_file(client, logged_in_headers, monkeypatch, tmp_path):
    import anyio

    monkeypatch.setattr(get_storage_service(), "data_dir", anyio.Path(tmp_path))
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(client, logged_in_headers, resource_type="file", actions=["create"])
        result = await client.post("api/v2/files/", headers=headers, files={"file": ("new.txt", b"new", "text/plain")})
        assert result.status_code == 201, result.text


@pytest.mark.parametrize("filename", ["_mcp_servers.json", "_MCP_SERVERS_{owner}.json"])
async def test_restricted_key_cannot_upload_mcp_credential_config(
    client, logged_in_headers, active_user, monkeypatch, filename
):
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(client, logged_in_headers, resource_type="file", actions=["create"])
        result = await client.post(
            "api/v2/files/",
            headers=headers,
            files={"file": (filename.format(owner=active_user.id), b'{"mcpServers":{}}', "application/json")},
        )
        assert result.status_code == 404, result.text


@pytest.mark.parametrize("ephemeral", [False, True])
async def test_append_alias_cannot_modify_stored_mcp_credentials(
    client, logged_in_headers, active_user, monkeypatch, tmp_path, ephemeral
):
    import anyio

    stored_filename = f"_mcp_servers_{active_user.id}.json"
    row = File(user_id=active_user.id, name="harmless-alias", path=f"{active_user.id}/{stored_filename}", size=6)
    async with session_scope() as session:
        session.add(row)
    storage = get_storage_service()
    monkeypatch.setattr(storage, "data_dir", anyio.Path(tmp_path))
    await storage.save_file(flow_id=str(active_user.id), file_name=stored_filename, data=b"before")
    probe = AsyncMock(wraps=storage.get_file_size)
    write = AsyncMock(wraps=storage.save_file)
    monkeypatch.setattr(storage, "get_file_size", probe)
    monkeypatch.setattr(storage, "save_file", write)
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(client, logged_in_headers, resource_type="file", actions=["create", "write"])
        response = await client.post(
            "api/v2/files/",
            headers=headers,
            params={"append": True, "ephemeral": ephemeral},
            files={"file": ("harmless-alias.txt", b"after", "text/plain")},
        )
    assert response.status_code == 404, response.text
    probe.assert_not_awaited()
    write.assert_not_awaited()
    assert await storage.get_file(flow_id=str(active_user.id), file_name=stored_filename) == b"before"


@pytest.mark.usefixtures("client")
@pytest.mark.parametrize(
    "operation",
    [
        "read",
        "read_batch",
        "rename",
        "delete",
        "delete_batch",
        "variable_write",
        "variable_delete",
        "flow_read",
        "flow_read_direct",
        "flow_write",
    ],
)
async def test_restricted_file_and_variable_operations_release_single_connection(
    active_user, monkeypatch, tmp_path, operation
):
    from types import SimpleNamespace

    from langflow.api.v1 import files as files_v1
    from langflow.api.v1 import variable as variable_routes
    from langflow.api.v2 import files as files_v2
    from langflow.services.auth.context import AuthCredentialContext, set_current_auth_context
    from langflow.services.database.models.variable.model import VariableUpdate
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'file-variable-pool.db'}",
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.2,
    )
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        files = [
            File(user_id=active_user.id, name=f"file-{index}", path=f"{active_user.id}/file-{index}.txt", size=6)
            for index in range(2)
        ]
        variable = Variable(user_id=active_user.id, name="pool-value", value="before", type=GENERIC_TYPE)
        flow = Flow(user_id=active_user.id, name="pool-flow", data={})
        session.add_all([*files, variable, flow])
        await session.commit()

    async def enforce(**_kwargs):
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True

    async def read_storage(**_kwargs):
        await enforce()
        return b"content"

    async def delete_storage(**_kwargs):
        await enforce()

    plugin = SimpleNamespace(
        supports_api_key_scopes=AsyncMock(return_value=True),
        supports_cross_user_fetch=AsyncMock(return_value=True),
        is_enabled=AsyncMock(return_value=True),
        enforce=enforce,
    )
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr("langflow.services.authorization.guards.get_authorization_service", lambda: plugin)
    monkeypatch.setattr("langflow.services.authorization.fetch.get_authorization_service", lambda: plugin)
    monkeypatch.setattr("langflow.services.deps.get_authorization_service", lambda: plugin)
    storage = SimpleNamespace(get_file=read_storage, delete_file=delete_storage)
    previous = get_current_auth_context()
    set_current_auth_context(AuthCredentialContext(method="api_key", api_key_id=uuid4(), api_key_restricted=True))
    try:
        async with AsyncSession(engine, expire_on_commit=True) as session:
            if operation == "read":
                assert (
                    await files_v2.download_file(files[0].id, active_user, session, storage, return_content=True)
                    == "content"
                )
            elif operation == "read_batch":
                await files_v2.download_files_batch([row.id for row in files], active_user, session, storage)
            elif operation == "rename":
                result = await files_v2.edit_file_name(files[0].id, "renamed", active_user, session)
                assert result.name == "renamed"
            elif operation == "delete":
                await files_v2.delete_file(files[0].id, active_user, session, storage)
            elif operation == "delete_batch":
                await files_v2.delete_files_batch([row.id for row in files], active_user, session, storage)
            elif operation == "variable_write":
                result = await variable_routes.update_variable(
                    session=session,
                    variable_id=variable.id,
                    variable=VariableUpdate(id=variable.id, value="after"),
                    current_user=active_user,
                    provider_policy_attributes=None,
                )
                assert result.value == "after"
            elif operation == "variable_delete":
                await variable_routes.delete_variable(
                    session=session, variable_id=variable.id, current_user=active_user, _provider_policy_attributes=None
                )
            else:
                loaded = (
                    await session.get(Flow, flow.id)
                    if operation == "flow_read_direct"
                    else await files_v1.get_flow(flow.id, active_user, session)
                )
                if operation.startswith("flow_read"):
                    await files_v1.get_readable_flow(loaded, active_user, session)
                else:
                    await files_v1.delete_file("file.txt", loaded, active_user, storage)
            await session.commit()
    finally:
        set_current_auth_context(previous)
        await engine.dispose()


@pytest.mark.parametrize(
    ("old_type", "new_type", "new_name"),
    [
        (CREDENTIAL_TYPE, GENERIC_TYPE, "generic-name"),
        (GENERIC_TYPE, CREDENTIAL_TYPE, "secret-name"),
        (GENERIC_TYPE, GENERIC_TYPE, "OPENAI_API_KEY"),
    ],
)
async def test_restricted_key_cannot_reclassify_credentials(
    client,
    logged_in_headers,
    active_user,
    monkeypatch,
    old_type,
    new_type,
    new_name,
):
    row = Variable(user_id=active_user.id, name=f"scoped-{uuid4().hex}", value="unused", type=old_type)
    async with session_scope() as session:
        session.add(row)
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(
            client, logged_in_headers, resource_type="variable", resource_ids=[row.id], actions=["write"]
        )
        result = await client.patch(
            f"api/v1/variables/{row.id}", headers=headers, json={"id": str(row.id), "type": new_type, "name": new_name}
        )
        assert result.status_code == 403, result.text


async def test_credential_denial_releases_connection_before_auditing(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from fastapi import HTTPException
    from langflow.api.v1 import variable as routes
    from langflow.services.auth.context import AuthCredentialContext, set_current_auth_context
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'credential-audit.db'}",
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.2,
    )
    previous = get_current_auth_context()
    set_current_auth_context(AuthCredentialContext(method="api_key", api_key_restricted=True))
    decisions = []

    async def persist_audit(**decision):
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        decisions.append(decision)

    monkeypatch.setattr(routes, "audit_decision", persist_audit)
    try:
        async with AsyncSession(engine) as session:
            await session.execute(text("SELECT 1"))
            with pytest.raises(HTTPException) as denial:
                await routes._guard_credential_mutation(
                    SimpleNamespace(id=uuid4()),
                    routes.VariableAction.DELETE,
                    SimpleNamespace(id=uuid4(), type=CREDENTIAL_TYPE, name="secret"),
                    session=session,
                )
            assert denial.value.status_code == 403
        assert decisions[0]["details"]["reason"] == "restricted_api_key_credential_management"
    finally:
        set_current_auth_context(previous)
        await engine.dispose()


@pytest.mark.parametrize("path", ["download/{id}/example.png", "images/{id}/example.png", "list/{id}"])
async def test_legacy_flow_file_reads_apply_key_ceiling(
    client, logged_in_headers, active_user, monkeypatch, path, tmp_path
):
    flow = Flow(name="File-read ceiling", user_id=active_user.id, data={})
    async with session_scope() as session:
        session.add(flow)
    storage = get_storage_service()
    import anyio

    monkeypatch.setattr(storage, "data_dir", anyio.Path(tmp_path))
    await storage.save_file(flow_id=str(flow.id), file_name="example.png", data=b"synthetic")
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(client, logged_in_headers, resource_type="flow", resource_ids=[uuid4()])
        response = await client.get(f"api/v1/files/{path.format(id=flow.id)}", headers=headers)
        assert response.status_code in {403, 404}, response.text


@pytest.mark.parametrize("operation", ["read", "read_batch", "rename", "delete", "delete_batch", "delete_all"])
async def test_scoped_keys_cannot_access_legacy_mcp_credential_files(
    client,
    logged_in_headers,
    active_user,
    monkeypatch,
    operation,
    tmp_path,
):
    filename = f"_mcp_servers_{active_user.id}"
    row = File(user_id=active_user.id, name=filename, path=f"{active_user.id}/{filename}.json", size=2)
    async with session_scope() as session:
        session.add(row)
    import anyio

    monkeypatch.setattr(get_storage_service(), "data_dir", anyio.Path(tmp_path))
    await get_storage_service().save_file(flow_id=str(active_user.id), file_name=f"{filename}.json", data=b"{}")
    with exact_resource_plugin(monkeypatch):
        headers = await scoped_headers(
            client, logged_in_headers, resource_type="file", actions=["read", "write", "delete"]
        )
        path = f"api/v2/files/{row.id}"
        if operation == "read":
            response = await client.get(path, headers=headers)
        elif operation == "read_batch":
            response = await client.post("api/v2/files/batch/", headers=headers, json=[str(row.id)])
        elif operation == "rename":
            response = await client.put(path, headers=headers, params={"name": "new-name"})
        elif operation == "delete":
            response = await client.delete(path, headers=headers)
        elif operation == "delete_batch":
            response = await client.request("DELETE", "api/v2/files/batch/", headers=headers, json=[str(row.id)])
        else:
            response = await client.delete("api/v2/files/", headers=headers)
        assert response.status_code in {403, 404}, response.text

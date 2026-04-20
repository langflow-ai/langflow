from __future__ import annotations

import importlib
import io
import zipfile
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi import HTTPException, status
from lfx.services.adapters.deployment.exceptions import (
    AuthorizationError,
    CredentialResolutionError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    OperationNotSupportedError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    BaseFlowArtifact,
    ConfigItem,
    ConfigListParams,
    DeploymentConfig,
    DeploymentCreate,
    DeploymentListParams,
    DeploymentType,
    DeploymentUpdate,
    EnvVarValueSpec,
    ExecutionCreate,
    ExecutionCreateResult,
    ExecutionStatusResult,
    SnapshotItem,
    SnapshotListParams,
    SnapshotListResult,
)
from pydantic import ValidationError

try:
    import langflow.services.adapters.deployment.watsonx_orchestrate  # noqa: F401
except ModuleNotFoundError:
    pytest.skip(
        "Skipping Watsonx deployment tests: optional IBM SDK dependencies not available.",
        allow_module_level=True,
    )

tools_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.core.tools")
service_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.service")
update_core_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.core.update")
create_core_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.core.create")
shared_core_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.core.shared")
payloads_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.payloads")
client_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.client")
types_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.types")
deployment_context_module = importlib.import_module("langflow.services.adapters.deployment.context")
WatsonxOrchestrateDeploymentService = importlib.import_module(
    "langflow.services.adapters.deployment.watsonx_orchestrate"
).WatsonxOrchestrateDeploymentService
WxOCredentials = importlib.import_module(
    "langflow.services.adapters.deployment.watsonx_orchestrate.types"
).WxOCredentials

# Aliases for classes used in tests (module-level to satisfy N806).
ToolConnectionOps = update_core_module.ToolConnectionOps
OrderedUniqueStrs = shared_core_module.OrderedUniqueStrs
WatsonxDeploymentUpdatePayload = payloads_module.WatsonxDeploymentUpdatePayload
WatsonxRenameToolOperation = payloads_module.WatsonxRenameToolOperation
ListConfigsResponse = importlib.import_module(
    "ibm_watsonx_orchestrate_clients.connections.connections_client"
).ListConfigsResponse

TEST_WXO_LLM = "ibm/granite-3.3-8b"


def _reload_wxo_auth_modules():
    constants_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.constants")
    importlib.reload(constants_module)
    return importlib.reload(client_module)


def _tool_refs(*tool_ids: str) -> list[dict[str, str]]:
    """Build WatsonxToolRefBinding dicts for test data."""
    return [{"source_ref": f"fv-{tid}", "tool_id": tid} for tid in tool_ids]


def _tool_ref(tool_id: str) -> dict[str, str]:
    """Build a single WatsonxToolRefBinding dict for test data."""
    return {"source_ref": f"fv-{tool_id}", "tool_id": tool_id}


class DummySettingsService:
    def __init__(self):
        self.settings = SimpleNamespace()


class FakeAgentClient:
    def __init__(
        self,
        deployment: dict,
        listed_agents: list[dict] | None = None,
        get_payloads: dict[str, dict | list[dict]] | None = None,
        create_response: object | None = None,
        create_exception: Exception | None = None,
    ):
        self._deployment = deployment
        self._listed_agents = listed_agents or []
        self._get_payloads = get_payloads or {}
        self._create_response = create_response or SimpleNamespace(id="dep-created")
        self._create_exception = create_exception
        self.update_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []
        self.create_calls: list[dict] = []
        self.delete_calls: list[str] = []

    def get_draft_by_id(self, deployment_id: str):  # noqa: ARG002
        return self._deployment

    def get_drafts_by_ids(self, deployment_ids: list[str]):
        return [agent for agent in self._listed_agents if str(agent.get("id") or "").strip() in set(deployment_ids)]

    def get_drafts_by_names(self, agent_names: list[str]):
        return [agent for agent in self._listed_agents if str(agent.get("name") or "").strip() in set(agent_names)]

    def get_draft_by_name(self, agent_name: str):
        return [agent for agent in self._listed_agents if agent.get("name") == agent_name]

    def get(self):
        return self._listed_agents

    def update(self, deployment_id: str, payload: dict):
        self.update_calls.append((deployment_id, payload))

    def create(self, payload: dict):
        self.create_calls.append(payload)
        if self._create_exception is not None:
            raise self._create_exception
        return self._create_response

    def delete(self, deployment_id: str):
        self.delete_calls.append(deployment_id)

    def _post(self, path: str, data: dict):
        self.post_calls.append((path, data))
        return {
            "thread_id": "thread-1",
            "run_id": "run-1",
            "task_id": "task-1",
            "message_id": "message-1",
        }

    def _get(self, path: str, params: dict | None = None):
        if path == "/agents":
            ids = params.get("ids", []) if isinstance(params, dict) else []
            names = params.get("names", []) if isinstance(params, dict) else []
            id_set = {str(item) for item in ids}
            name_set = {str(item) for item in names}
            if id_set or name_set:
                return [
                    agent
                    for agent in self._listed_agents
                    if str(agent.get("id") or "").strip() in id_set or str(agent.get("name") or "").strip() in name_set
                ]
            return self._listed_agents
        return self._get_payloads.get(path, {})


class FakeToolClient:
    def __init__(self, tools: list[dict], existing_names: set[str] | None = None):
        self._tools_by_id = {str(tool.get("id")): dict(tool) for tool in tools if tool.get("id")}
        self._existing_names = existing_names or set()
        self.delete_calls: list[str] = []
        self.update_calls: list[tuple[str, dict]] = []
        self.create_calls: list[dict] = []

    def get_drafts_by_ids(self, tool_ids: list[str]):
        return [dict(self._tools_by_id[tool_id]) for tool_id in tool_ids if tool_id in self._tools_by_id]

    def get_draft_by_name(self, tool_name: str):
        if tool_name in self._existing_names:
            return [{"name": tool_name}]
        return []

    def get_drafts_by_names(self, names: list[str]):
        return [dict(tool) for tool in self._tools_by_id.values() if tool.get("name") in names]

    def update(self, tool_id: str, payload: dict):
        self.update_calls.append((tool_id, payload))
        current = self._tools_by_id.get(tool_id, {"id": tool_id})
        merged = dict(current)
        merged.update(payload)
        self._tools_by_id[tool_id] = merged

    def create(self, payload: dict):
        self.create_calls.append(payload)
        tool_id = f"created-tool-{len(self.create_calls)}"
        self._tools_by_id[tool_id] = {"id": tool_id, **payload}
        return {"id": tool_id}

    def delete(self, tool_id: str):
        self.delete_calls.append(tool_id)


class FakeConnectionsClient:
    def __init__(self, existing_app_id: str | None = None):
        self._connections_by_app_id: dict[str, str] = {}
        if existing_app_id:
            self._connections_by_app_id[existing_app_id] = "conn-1"
        self.delete_calls: list[str] = []
        self.delete_credentials_calls: list[tuple[str, object, bool]] = []
        self._list_entries: list[dict] = []
        self._draft_entries_by_id: list[object] = []
        self.create_calls: list[dict] = []
        self.create_config_calls: list[tuple[str, dict]] = []
        self.create_credentials_calls: list[tuple[str, object, bool, dict]] = []

    def get_draft_by_app_id(self, app_id: str):
        if app_id in self._connections_by_app_id:
            return SimpleNamespace(connection_id=self._connections_by_app_id[app_id])
        return None

    def get_config(self, app_id: str, env):  # noqa: ARG002
        from ibm_watsonx_orchestrate_core.types.connections import ConnectionSecurityScheme

        return SimpleNamespace(security_scheme=ConnectionSecurityScheme.KEY_VALUE)

    def get_credentials(self, app_id: str, env, *, use_app_credentials: bool):  # noqa: ARG002
        return {"runtime_credentials": {"TOKEN": "value"}}

    def delete_credentials(self, app_id: str, env, *, use_app_credentials: bool):
        self.delete_credentials_calls.append((app_id, env, use_app_credentials))

    def delete(self, app_id: str):
        self.delete_calls.append(app_id)
        self._connections_by_app_id.pop(app_id, None)

    def create(self, payload: dict):
        self.create_calls.append(payload)
        app_id = str(payload.get("app_id"))
        self._connections_by_app_id[app_id] = f"conn-{app_id}"

    def create_config(self, app_id: str, payload: dict):
        self.create_config_calls.append((app_id, payload))

    def create_credentials(self, app_id: str, env, *, use_app_credentials: bool, payload: dict):
        self.create_credentials_calls.append((app_id, env, use_app_credentials, payload))

    def list(self):
        return self._list_entries

    def get_drafts_by_ids(self, conn_ids: list[str]):
        requested = set(conn_ids)
        entries = []
        for entry in self._draft_entries_by_id:
            connection_id = str(getattr(entry, "connection_id", "") or "")
            if connection_id in requested:
                entries.append(entry)
        return entries


class FakeBaseClient:
    def __init__(
        self,
        *,
        post_response: dict | None = None,
        get_payloads: dict[str, dict] | None = None,
    ):
        self.post_response = post_response or {
            "thread_id": "thread-1",
            "run_id": "run-1",
            "task_id": "task-1",
            "message_id": "message-1",
        }
        self._get_payloads = get_payloads or {}
        self.post_calls: list[tuple[str, dict]] = []
        self.get_calls: list[str] = []

    def _post(self, path: str, data: dict):
        self.post_calls.append((path, data))
        return self.post_response

    def _get(self, path: str, params: dict | None = None):  # noqa: ARG002
        self.get_calls.append(path)
        return self._get_payloads.get(path, {})


class FakeWXOClients(SimpleNamespace):
    def __init__(self, *, agent=None, tool=None, connections=None):
        super().__init__(
            agent=agent or FakeAgentClient({"id": "dep-1", "tools": []}),
            tool=tool or FakeToolClient([]),
            connections=connections or FakeConnectionsClient(),
        )
        self.upload_tool_artifact_calls: list[str] = []

    def upload_tool_artifact(self, tool_id: str, files: dict[str, tuple[str, io.BytesIO, str, dict[str, str]]]):
        file_obj = files["file"][1]
        file_obj.read()
        self.upload_tool_artifact_calls.append(tool_id)
        return {"id": tool_id}


def _with_wxo_wrappers(ns):
    """Attach WxOClient SDK wrapper methods to a SimpleNamespace test double."""
    if hasattr(ns, "_base") and ns._base is not None:
        ns.get_agents_raw = lambda params=None: ns._base._get("/agents", params=params)
        ns.get_models_raw = lambda params=None: ns._base._get("/models", params=params)
        ns.get_tools_raw = lambda params=None: ns._base._get("/tools", params=params)
        ns.post_run = lambda *, data: ns._base._post("/runs", data)
        ns.get_run = lambda run_id: ns._base._get(f"/runs/{run_id}")
    return ns


def _attach_provider_clients(service: WatsonxOrchestrateDeploymentService, clients: object) -> None:
    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return clients

    service._get_provider_clients = mock_get_provider_clients


def _create_provider_spec(
    *,
    existing_tool_ids: list[str] | None = None,
    existing_app_ids: list[str] | None = None,
) -> dict:
    tool_ids = existing_tool_ids or ["tool-existing-1"]
    app_ids = existing_app_ids or ["app-existing-1"]
    return {
        "tools": {},
        "connections": {},
        "llm": TEST_WXO_LLM,
        "operations": [
            {
                "op": "bind",
                "tool": {"tool_id_with_ref": _tool_ref(tool_ids[0])},
                "app_ids": [app_ids[0]],
            }
        ],
    }


@pytest.mark.anyio
async def test_process_config_uses_raw_payload_but_overrides_name(monkeypatch):
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import process_config

    captured = {}

    async def mock_create_config(*, clients, config, user_id, db):  # noqa: ARG001
        captured["name"] = config.name
        captured["env_vars"] = config.environment_variables
        return config.name

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.core.config.create_config",
        mock_create_config,
    )

    app_id = await process_config(
        clients=SimpleNamespace(),
        user_id="user-1",
        db=object(),
        deployment_name="my_deployment",
        config=ConfigItem(
            raw_payload=DeploymentConfig(
                name="caller_supplied_name",
                description="from payload",
                environment_variables=None,
            )
        ),
    )

    assert app_id == "my_deployment"
    assert captured["name"] == "my_deployment"
    assert captured["env_vars"] is None


@pytest.mark.anyio
async def test_process_config_rejects_reference_id():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import process_config

    with pytest.raises(InvalidDeploymentOperationError, match="Config reference binding is not supported"):
        await process_config(
            clients=SimpleNamespace(),
            user_id="user-1",
            db=object(),
            deployment_name="my_deployment",
            config=ConfigItem(reference_id="existing-config"),
        )


@pytest.mark.anyio
async def test_create_rejects_legacy_top_level_config_section(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(InvalidDeploymentOperationError, match="Top-level 'snapshot' and 'config' create sections"):
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
                provider_data=_create_provider_spec(),
                config=ConfigItem(reference_id="existing-config"),
            ),
        )


@pytest.mark.anyio
async def test_create_rejects_missing_llm():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    provider_data = _create_provider_spec()
    provider_data.pop("llm", None)

    with pytest.raises(InvalidContentError, match=r"Missing required field 'llm'"):
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
                provider_data=provider_data,
            ),
        )


def test_create_payload_rejects_empty_work():
    with pytest.raises(
        ValidationError,
        match=r"At least one bind/attach_tool operation or tools\.raw_payloads entry must be provided for create",
    ):
        payloads_module.WatsonxDeploymentCreatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
            }
        )


@pytest.mark.anyio
async def test_resolve_runtime_credentials_supports_variable_and_raw_sources(monkeypatch):
    async def mock_resolve_variable_value(variable_name: str, *, user_id, db, **kwargs):  # noqa: ARG001
        return f"resolved::{variable_name}"

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.client.resolve_variable_value",
        mock_resolve_variable_value,
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.client import resolve_runtime_credentials

    runtime_credentials = await resolve_runtime_credentials(
        user_id="user-1",
        db=object(),
        environment_variables={
            "FROM_RAW": EnvVarValueSpec(source="raw", value="raw-token"),
            "FROM_VAR": EnvVarValueSpec(source="variable", value="OPENAI_API_KEY"),
        },
    )

    assert runtime_credentials.model_dump() == {
        "FROM_RAW": "raw-token",
        "FROM_VAR": "resolved::OPENAI_API_KEY",
    }


@pytest.mark.anyio
async def test_update_rejects_legacy_top_level_snapshot_or_config(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient([{"id": "tool-1", "binding": {"langflow": {"connections": {}}}}]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    with pytest.raises(InvalidDeploymentOperationError, match="no longer supported"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=DeploymentUpdate(snapshot={"add_ids": ["tool-1"]}),
            db=object(),
        )


@pytest.mark.anyio
async def test_update_rejects_legacy_top_level_config_section(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient([{"id": "tool-1", "binding": {"langflow": {"connections": {}}}}]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    with pytest.raises(InvalidDeploymentOperationError, match="no longer supported"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=DeploymentUpdate(config={"config_id": "cfg-legacy"}),
            db=object(),
        )


@pytest.mark.anyio
async def test_update_provider_data_binds_existing_tool_and_updates_agent_tools(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient(
        [
            {"id": "tool-1", "name": "tool-1", "binding": {"langflow": {"connections": {}}}},
            {"id": "tool-3", "name": "tool-3", "binding": {"langflow": {"connections": {}}}},
        ]
    )
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=FakeConnectionsClient(existing_app_id="cfg-new"),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        assert app_id == "cfg-new"
        return SimpleNamespace(connection_id="conn-new")

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(update_core_module, "validate_connection", mock_validate_connection)

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "tools": {},
                "connections": {},
                "llm": TEST_WXO_LLM,
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": _tool_ref("tool-3")},
                        "app_ids": ["cfg-new"],
                    }
                ],
            }
        ),
        db=object(),
    )

    assert result.provider_result is not None
    assert result.provider_result.created_app_ids == []
    assert result.provider_result.created_snapshot_ids == []
    assert result.provider_result.added_snapshot_ids == ["tool-3"]
    assert [tool_id for tool_id, _payload in fake_tool.update_calls] == ["tool-3"]
    _, updated_tool_payload = fake_tool.update_calls[0]
    assert updated_tool_payload["binding"]["langflow"]["connections"]["cfg-new"] == "conn-new"
    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload["tools"] == ["tool-1", "tool-3"]
    assert agent_payload["llm"] == TEST_WXO_LLM


@pytest.mark.anyio
async def test_update_provider_data_bind_unbind_and_rename_preserves_connection_deltas(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "name": "tool-1",
                "display_name": "tool-1",
                "binding": {
                    "langflow": {
                        "connections": {"cfg-keep": "conn-keep", "cfg-remove": "conn-remove"},
                    }
                },
            },
        ]
    )
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=FakeConnectionsClient(existing_app_id="cfg-add"),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        connection_id_by_app_id = {
            "cfg-add": "conn-add",
            "cfg-remove": "conn-remove",
        }
        assert app_id in connection_id_by_app_id
        return SimpleNamespace(connection_id=connection_id_by_app_id[app_id])

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(update_core_module, "validate_connection", mock_validate_connection)

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "tools": {},
                "connections": {},
                "llm": TEST_WXO_LLM,
                "operations": [
                    {"op": "bind", "tool": {"tool_id_with_ref": _tool_ref("tool-1")}, "app_ids": ["cfg-add"]},
                    {"op": "unbind", "tool": _tool_ref("tool-1"), "app_ids": ["cfg-remove"]},
                    {"op": "rename_tool", "tool": _tool_ref("tool-1"), "new_name": "renamed_tool"},
                ],
            }
        ),
        db=object(),
    )

    assert result.provider_result is not None
    assert [tool_id for tool_id, _payload in fake_tool.update_calls] == ["tool-1", "tool-1"]

    _, rename_payload = fake_tool.update_calls[1]
    assert rename_payload["name"] == "renamed_tool"
    assert rename_payload["display_name"] == "renamed_tool"
    assert rename_payload["binding"]["langflow"]["connections"] == {
        "cfg-keep": "conn-keep",
        "cfg-add": "conn-add",
    }

    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload["tools"] == ["tool-1"]
    assert agent_payload["llm"] == TEST_WXO_LLM


@pytest.mark.anyio
async def test_update_provider_data_llm_only_updates_agent(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return SimpleNamespace(agent=fake_agent)

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(provider_data={"llm": TEST_WXO_LLM}),
        db=object(),
    )

    assert result.id == "dep-1"
    assert len(fake_agent.update_calls) == 1
    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload == {"llm": TEST_WXO_LLM}


@pytest.mark.anyio
async def test_update_provider_data_accepts_missing_llm(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient([{"id": "tool-1", "name": "tool-1", "binding": {"langflow": {"connections": {}}}}])
    fake_connections = FakeConnectionsClient(existing_app_id="cfg-1")

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return SimpleNamespace(agent=fake_agent, tool=fake_tool, connections=fake_connections)

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "connections": {},
                "operations": [{"op": "bind", "tool": {"tool_id_with_ref": _tool_ref("tool-1")}, "app_ids": ["cfg-1"]}],
            }
        ),
        db=object(),
    )

    assert result.id == "dep-1"
    assert fake_agent.update_calls
    assert all("llm" not in payload for _, payload in fake_agent.update_calls)


def test_update_payload_rejects_connections_without_bind_or_unbind_operations():
    with pytest.raises(
        ValidationError,
        match="connections require at least one bind/unbind operation that references app_ids",
    ):
        payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "connections": {
                    "raw_payloads": [
                        {"app_id": "cfg-1", "environment_variables": {"K": {"source": "raw", "value": "v"}}}
                    ]
                },
                "operations": [],
            }
        )


def test_update_payload_rejects_existing_tool_bind_with_empty_app_ids():
    with pytest.raises(ValidationError):
        payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": _tool_ref("tool-existing")},
                        "app_ids": [],
                    }
                ],
            }
        )


def test_update_payload_accepts_attach_tool_operation():
    payload = payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "attach_tool",
                    "tool": _tool_ref("tool-existing"),
                }
            ],
        }
    )
    attach_op = payload.operations[0]
    assert isinstance(attach_op, payloads_module.WatsonxAttachToolOperation)
    assert attach_op.tool.tool_id == "tool-existing"


def test_update_payload_rejects_attach_and_bind_for_same_existing_tool():
    with pytest.raises(
        ValidationError,
        match="attach_tool cannot be combined with bind\\.tool\\.tool_id_with_ref",
    ):
        payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "operations": [
                    {"op": "attach_tool", "tool": _tool_ref("tool-existing")},
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": _tool_ref("tool-existing")},
                        "app_ids": ["cfg-1"],
                    },
                ],
            }
        )


def test_update_payload_rejects_remove_with_other_ops_for_same_tool():
    with pytest.raises(
        ValidationError,
        match="remove_tool cannot be combined with bind/attach_tool/unbind for the same tool_id",
    ):
        payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "operations": [
                    {"op": "remove_tool", "tool": _tool_ref("tool-existing")},
                    {
                        "op": "unbind",
                        "tool": _tool_ref("tool-existing"),
                        "app_ids": ["cfg-1"],
                    },
                ],
            }
        )


def test_update_payload_rejects_bind_unbind_overlapping_app_ids_for_same_tool():
    with pytest.raises(
        ValidationError,
        match="bind and unbind app_ids overlap for the same tool_id",
    ):
        payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": _tool_ref("tool-existing")},
                        "app_ids": ["cfg-1"],
                    },
                    {
                        "op": "unbind",
                        "tool": _tool_ref("tool-existing"),
                        "app_ids": ["cfg-1"],
                    },
                ],
            }
        )


def test_update_payload_rejects_duplicate_attach_tool_for_same_tool():
    with pytest.raises(
        ValidationError,
        match="Duplicate attach_tool operation for tool_id",
    ):
        payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "operations": [
                    {"op": "attach_tool", "tool": _tool_ref("tool-existing")},
                    {"op": "attach_tool", "tool": _tool_ref("tool-existing")},
                ],
            }
        )


def test_update_payload_rejects_duplicate_remove_tool_for_same_tool():
    with pytest.raises(
        ValidationError,
        match="Duplicate remove_tool operation for tool_id",
    ):
        payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "operations": [
                    {"op": "remove_tool", "tool": _tool_ref("tool-a")},
                    {"op": "remove_tool", "tool": _tool_ref("tool-a")},
                ],
            }
        )


def test_create_payload_rejects_existing_tool_bind_with_empty_app_ids():
    with pytest.raises(ValidationError):
        payloads_module.WatsonxDeploymentCreatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": _tool_ref("tool-existing")},
                        "app_ids": [],
                    }
                ],
            }
        )


def test_create_payload_accepts_attach_tool_operation():
    payload = payloads_module.WatsonxDeploymentCreatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "attach_tool",
                    "tool": _tool_ref("tool-existing"),
                }
            ],
        }
    )
    attach_op = payload.operations[0]
    assert isinstance(attach_op, payloads_module.WatsonxAttachToolOperation)
    assert attach_op.tool.tool_id == "tool-existing"


def test_create_payload_rejects_attach_and_bind_for_same_existing_tool():
    with pytest.raises(
        ValidationError,
        match="attach_tool cannot be combined with bind\\.tool\\.tool_id_with_ref",
    ):
        payloads_module.WatsonxDeploymentCreatePayload.model_validate(
            {
                "llm": TEST_WXO_LLM,
                "operations": [
                    {"op": "attach_tool", "tool": _tool_ref("tool-existing")},
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": _tool_ref("tool-existing")},
                        "app_ids": ["cfg-1"],
                    },
                ],
            }
        )


@pytest.mark.anyio
async def test_update_provider_data_put_tools_with_llm_updates_agent(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1", "tool-2"]})
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "put_tools": ["tool-a", "tool-b"],
                "llm": TEST_WXO_LLM,
            }
        ),
        db=object(),
    )

    assert result.id == "dep-1"
    assert len(fake_agent.update_calls) == 1
    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload["tools"] == ["tool-a", "tool-b"]
    assert agent_payload["llm"] == TEST_WXO_LLM


@pytest.mark.anyio
async def test_update_provider_data_creates_raw_tools_without_operations(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient([{"id": "tool-1", "name": "tool-1", "binding": {"langflow": {"connections": {}}}}])
    fake_connections = FakeConnectionsClient()
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=fake_connections,
    )
    captured: dict[str, object] = {}

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_create_and_upload(*, clients, tool_bindings):
        _ = clients
        captured["tool_bindings"] = tool_bindings
        return ["new-tool-raw-1"]

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(
        update_core_module,
        "create_and_upload_wxo_flow_tools_with_bindings",
        mock_create_and_upload,
    )

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "llm": TEST_WXO_LLM,
                "tools": {
                    "raw_payloads": [
                        {
                            "id": str(UUID("00000000-0000-0000-0000-000000000071")),
                            "name": "snapshot-new-raw-only",
                            "description": "desc",
                            "data": {"nodes": [], "edges": []},
                            "tags": [],
                            "provider_data": {"project_id": "project-1", "source_ref": "fv-raw-only-1"},
                        }
                    ]
                },
            }
        ),
        db=object(),
    )

    assert captured["tool_bindings"][0].connections == {}
    assert result.provider_result is not None
    assert result.provider_result.created_snapshot_ids == ["new-tool-raw-1"]
    assert result.provider_result.added_snapshot_ids == ["new-tool-raw-1"]
    assert fake_connections.create_calls == []
    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload["tools"] == ["tool-1", "new-tool-raw-1"]
    assert agent_payload["llm"] == TEST_WXO_LLM


@pytest.mark.anyio
async def test_update_provider_data_creates_raw_connection_and_raw_tool(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient([{"id": "tool-1", "name": "tool-1", "binding": {"langflow": {"connections": {}}}}])
    fake_connections = FakeConnectionsClient()
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=fake_connections,
    )
    captured: dict[str, object] = {}

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_create_config(*, clients, config, user_id, db):  # noqa: ARG001
        captured["created_app_id"] = config.name
        fake_connections._connections_by_app_id[config.name] = f"conn-{config.name}"
        return config.name

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id=f"conn-{app_id}")

    async def mock_create_and_upload(*, clients, tool_bindings):
        _ = clients
        first_binding = tool_bindings[0]
        captured["connections"] = first_binding.connections
        return ["new-tool-1"]

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(shared_core_module, "create_config", mock_create_config)
    monkeypatch.setattr(update_core_module, "validate_connection", mock_validate_connection)
    monkeypatch.setattr(
        update_core_module,
        "create_and_upload_wxo_flow_tools_with_bindings",
        mock_create_and_upload,
    )

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "tools": {
                    "raw_payloads": [
                        {
                            "id": str(UUID("00000000-0000-0000-0000-000000000011")),
                            "name": "snapshot-new-1",
                            "description": "desc",
                            "data": {"nodes": [], "edges": []},
                            "tags": [],
                            "provider_data": {"project_id": "project-1", "source_ref": "fv-update-1"},
                        }
                    ]
                },
                "connections": {
                    "raw_payloads": [
                        {
                            "app_id": "cfg",
                            "environment_variables": {"API_KEY": {"source": "raw", "value": "secret"}},
                        }
                    ]
                },
                "llm": TEST_WXO_LLM,
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"name_of_raw": "snapshot-new-1"},
                        "app_ids": ["cfg"],
                    }
                ],
            }
        ),
        db=object(),
    )

    assert captured["created_app_id"] == "cfg"
    assert captured["connections"] == {"cfg": "conn-cfg"}
    assert result.provider_result is not None
    assert result.provider_result.created_app_ids == ["cfg"]
    assert result.provider_result.created_snapshot_ids == ["new-tool-1"]
    assert result.provider_result.added_snapshot_ids == ["new-tool-1"]
    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload["tools"] == ["tool-1", "new-tool-1"]
    assert agent_payload["llm"] == TEST_WXO_LLM


@pytest.mark.anyio
async def test_update_provider_data_binds_existing_tool_using_provider_app_id_for_raw_connection(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient([{"id": "tool-1", "name": "tool-1", "binding": {"langflow": {"connections": {}}}}])
    fake_connections = FakeConnectionsClient()
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=fake_connections,
    )
    captured: dict[str, str] = {}

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_create_config(*, clients, config, user_id, db):  # noqa: ARG001
        captured["created_app_id"] = config.name
        fake_connections._connections_by_app_id[config.name] = f"conn-{config.name}"
        return config.name

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id=f"conn-{app_id}")

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(shared_core_module, "create_config", mock_create_config)
    monkeypatch.setattr(update_core_module, "validate_connection", mock_validate_connection)

    await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "tools": {},
                "connections": {
                    "raw_payloads": [
                        {
                            "app_id": "cfg",
                            "environment_variables": {"API_KEY": {"source": "raw", "value": "secret"}},
                        }
                    ]
                },
                "llm": TEST_WXO_LLM,
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": _tool_ref("tool-1")},
                        "app_ids": ["cfg"],
                    }
                ],
            }
        ),
        db=object(),
    )

    assert [tool_id for tool_id, _payload in fake_tool.update_calls] == ["tool-1"]
    _, updated_tool_payload = fake_tool.update_calls[0]
    assert updated_tool_payload["binding"]["langflow"]["connections"] == {"cfg": "conn-cfg"}
    assert captured["created_app_id"] == "cfg"


@pytest.mark.anyio
async def test_update_provider_data_mixed_operations_preserve_encounter_order(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1", "tool-2"]})
    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "name": "tool-1",
                "binding": {"langflow": {"connections": {"cfg-1": "conn-old-1", "cfg-2": "conn-old-2"}}},
            },
            {"id": "tool-2", "name": "tool-2", "binding": {"langflow": {"connections": {}}}},
            {"id": "tool-3", "name": "tool-3", "binding": {"langflow": {"connections": {}}}},
        ]
    )
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=FakeConnectionsClient(existing_app_id="cfg-1"),
    )
    validate_calls: list[str] = []

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        validate_calls.append(app_id)
        return SimpleNamespace(connection_id=f"conn-{app_id}")

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(update_core_module, "validate_connection", mock_validate_connection)

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "tools": {},
                "connections": {},
                "llm": TEST_WXO_LLM,
                "operations": [
                    {"op": "bind", "tool": {"tool_id_with_ref": _tool_ref("tool-3")}, "app_ids": ["cfg-2", "cfg-1"]},
                    {"op": "unbind", "tool": _tool_ref("tool-1"), "app_ids": ["cfg-1", "cfg-2"]},
                    {"op": "remove_tool", "tool": _tool_ref("tool-2")},
                ],
            }
        ),
        db=object(),
    )

    assert validate_calls == ["cfg-2", "cfg-1"]
    assert result.provider_result is not None
    assert result.provider_result.created_app_ids == []
    assert result.provider_result.created_snapshot_ids == []
    assert result.provider_result.added_snapshot_ids == ["tool-3"]

    # Existing tool updates are dispatched concurrently via asyncio.gather, so
    # completion order is non-deterministic.  Assert the set of updated tool ids
    # and look up each payload by tool_id.
    update_calls_by_id = dict(fake_tool.update_calls)
    assert set(update_calls_by_id) == {"tool-3", "tool-1"}

    tool3_payload = update_calls_by_id["tool-3"]
    assert list(tool3_payload["binding"]["langflow"]["connections"]) == ["cfg-2", "cfg-1"]
    assert tool3_payload["binding"]["langflow"]["connections"] == {"cfg-2": "conn-cfg-2", "cfg-1": "conn-cfg-1"}

    tool1_payload = update_calls_by_id["tool-1"]
    assert tool1_payload["binding"]["langflow"]["connections"] == {}

    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload["tools"] == ["tool-1", "tool-3"]
    assert agent_payload["llm"] == TEST_WXO_LLM


def test_ordered_unique_strs_preserves_encounter_order_and_safe_discard():
    ordered = update_core_module.OrderedUniqueStrs()
    ordered.extend(["b", "a", "b", "c"])
    ordered.add("a")
    ordered.add("d")
    ordered.discard("c")
    ordered.discard("missing")

    assert ordered.to_list() == ["b", "a", "d"]


def test_build_provider_update_plan_preserves_operation_encounter_order():
    provider_update = payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
        {
            "tools": {
                "raw_payloads": [
                    {
                        "id": str(UUID("00000000-0000-0000-0000-000000000041")),
                        "name": "snapshot-raw-1",
                        "description": "desc",
                        "data": {"nodes": [], "edges": []},
                        "tags": [],
                        "provider_data": {"project_id": "project-1", "source_ref": "fv-plan-1"},
                    }
                ],
            },
            "connections": {
                "raw_payloads": [
                    {"app_id": "cfg-raw-1", "environment_variables": {"API_KEY": {"source": "raw", "value": "x"}}},
                    {"app_id": "cfg-raw-2", "environment_variables": {"API_KEY": {"source": "raw", "value": "y"}}},
                ],
            },
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "bind",
                    "tool": {"tool_id_with_ref": _tool_ref("tool-c")},
                    "app_ids": ["cfg-2", "cfg-1", "cfg-2"],
                },
                {"op": "bind", "tool": {"tool_id_with_ref": _tool_ref("tool-a")}, "app_ids": ["cfg-1"]},
                {"op": "unbind", "tool": _tool_ref("tool-c"), "app_ids": ["cfg-3", "cfg-3"]},
                {"op": "remove_tool", "tool": _tool_ref("tool-b")},
                {"op": "bind", "tool": {"name_of_raw": "snapshot-raw-1"}, "app_ids": ["cfg-raw-2", "cfg-raw-1"]},
            ],
        }
    )
    plan = update_core_module.build_provider_update_plan(
        agent={"id": "dep-1", "tools": ["tool-a", "tool-b"]},
        provider_update=provider_update,
    )

    assert [ref.tool_id for ref in plan.added_existing_tool_refs] == ["tool-c"]
    assert plan.final_existing_tool_ids == ["tool-a", "tool-c"]
    assert plan.existing_app_ids == ["cfg-2", "cfg-1", "cfg-3"]
    assert [item.operation_app_id for item in plan.raw_connections_to_create] == ["cfg-raw-1", "cfg-raw-2"]
    assert [item.provider_app_id for item in plan.raw_connections_to_create] == ["cfg-raw-1", "cfg-raw-2"]
    assert len(plan.raw_tools_to_create) == 1
    assert plan.raw_tools_to_create[0].app_ids == ["cfg-raw-2", "cfg-raw-1"]

    delta = plan.existing_tool_deltas["tool-c"]
    assert delta.bind.to_list() == ["cfg-2", "cfg-1"]
    assert delta.unbind.to_list() == ["cfg-3"]
    assert [ref.tool_id for ref in plan.removed_existing_tool_refs] == ["tool-b"]


def test_build_provider_update_plan_creates_unbound_raw_tools_alongside_bound_raw_tools():
    provider_update = payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
        {
            "tools": {
                "raw_payloads": [
                    {
                        "id": str(UUID("00000000-0000-0000-0000-000000000051")),
                        "name": "snapshot-bound",
                        "description": "desc",
                        "data": {"nodes": [], "edges": []},
                        "tags": [],
                        "provider_data": {"project_id": "project-1", "source_ref": "fv-bound"},
                    },
                    {
                        "id": str(UUID("00000000-0000-0000-0000-000000000052")),
                        "name": "snapshot-unbound",
                        "description": "desc",
                        "data": {"nodes": [], "edges": []},
                        "tags": [],
                        "provider_data": {"project_id": "project-1", "source_ref": "fv-unbound"},
                    },
                ],
            },
            "connections": {
                "raw_payloads": [
                    {"app_id": "cfg", "environment_variables": {"API_KEY": {"source": "raw", "value": "x"}}},
                ],
            },
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "bind",
                    "tool": {"name_of_raw": "snapshot-bound"},
                    "app_ids": ["cfg"],
                }
            ],
        }
    )
    plan = update_core_module.build_provider_update_plan(
        agent={"id": "dep-1", "tools": []},
        provider_update=provider_update,
    )

    assert [item.raw_name for item in plan.raw_tools_to_create] == ["snapshot-bound", "snapshot-unbound"]
    assert plan.raw_tools_to_create[0].app_ids == ["cfg"]
    assert plan.raw_tools_to_create[1].app_ids == []


def test_build_provider_update_plan_put_tools_replaces_agent_tool_list():
    """put_tools standalone path seeds final_existing_tool_ids from the payload, not the agent."""
    provider_update = payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
        {"put_tools": ["tool-x", "tool-y", "tool-z"]}
    )
    plan = update_core_module.build_provider_update_plan(
        agent={"id": "dep-1", "tools": ["tool-a", "tool-b"]},
        provider_update=provider_update,
    )

    assert plan.final_existing_tool_ids == ["tool-x", "tool-y", "tool-z"]
    assert plan.added_existing_tool_refs == []
    assert plan.raw_tools_to_create == []
    assert plan.existing_tool_deltas == {}


def test_build_provider_update_plan_put_tools_deduplicates():
    """Duplicate IDs in put_tools are collapsed (validator + OrderedUniqueStrs)."""
    provider_update = payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
        {"put_tools": ["tool-a", "tool-b", "tool-a"]}
    )
    plan = update_core_module.build_provider_update_plan(
        agent={"id": "dep-1", "tools": []},
        provider_update=provider_update,
    )

    assert plan.final_existing_tool_ids == ["tool-a", "tool-b"]


def test_build_provider_update_plan_put_tools_empty_clears_all():
    """An empty put_tools list clears the agent's tool list entirely."""
    provider_update = payloads_module.WatsonxDeploymentUpdatePayload.model_validate({"put_tools": []})
    plan = update_core_module.build_provider_update_plan(
        agent={"id": "dep-1", "tools": ["tool-a", "tool-b"]},
        provider_update=provider_update,
    )

    assert plan.final_existing_tool_ids == []


def test_build_provider_update_plan_attaches_existing_tool_without_connection_deltas():
    provider_update = payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "attach_tool",
                    "tool": _tool_ref("tool-existing"),
                }
            ],
        }
    )
    plan = update_core_module.build_provider_update_plan(
        agent={"id": "dep-1", "tools": ["tool-a"]},
        provider_update=provider_update,
    )

    assert plan.final_existing_tool_ids == ["tool-a", "tool-existing"]
    assert [ref.tool_id for ref in plan.added_existing_tool_refs] == ["tool-existing"]
    assert plan.existing_tool_deltas == {}


def test_build_provider_create_plan_creates_unbound_raw_tools_without_bind_operations():
    provider_create = payloads_module.WatsonxDeploymentCreatePayload.model_validate(
        {
            "tools": {
                "raw_payloads": [
                    {
                        "id": str(UUID("00000000-0000-0000-0000-000000000071")),
                        "name": "snapshot-unbound",
                        "description": "desc",
                        "data": {"nodes": [], "edges": []},
                        "tags": [],
                        "provider_data": {"project_id": "project-1", "source_ref": "fv-create-unbound"},
                    }
                ]
            },
            "llm": TEST_WXO_LLM,
            "operations": [],
        }
    )
    plan = create_core_module.build_provider_create_plan(
        deployment_name="my deployment",
        provider_create=provider_create,
    )

    assert [item.raw_name for item in plan.raw_tools_to_create] == ["snapshot-unbound"]
    assert plan.raw_tools_to_create[0].app_ids == []
    assert plan.selected_operation_app_ids == []
    assert plan.existing_tool_ids == []


def test_build_provider_create_plan_attaches_existing_tool_without_connection_updates():
    provider_create = payloads_module.WatsonxDeploymentCreatePayload.model_validate(
        {
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "attach_tool",
                    "tool": _tool_ref("tool-existing"),
                }
            ],
        }
    )
    plan = create_core_module.build_provider_create_plan(
        deployment_name="my deployment",
        provider_create=provider_create,
    )

    assert plan.existing_tool_ids == ["tool-existing"]
    assert plan.existing_tool_bindings == {}


@pytest.mark.anyio
async def test_update_existing_tool_connection_deltas_uses_bind_order_in_errors():
    fake_tool = FakeToolClient([{"id": "tool-c", "name": "tool-c", "binding": {"langflow": {"connections": {}}}}])
    clients = SimpleNamespace(tool=fake_tool)
    delta = update_core_module.ToolConnectionOps()
    delta.bind.extend(["cfg-missing-first", "cfg-present"])

    with pytest.raises(InvalidContentError, match="cfg-missing-first"):
        await update_core_module._update_existing_tool_connection_deltas(
            clients=clients,
            existing_tool_deltas={"tool-c": delta},
            resolved_connections={"cfg-present": "conn-present"},
            operation_to_provider_app_id={},
            original_tools={},
        )


@pytest.mark.anyio
async def test_apply_provider_create_plan_binds_raw_tools_with_provider_app_ids(monkeypatch):
    provider_create = payloads_module.WatsonxDeploymentCreatePayload.model_validate(
        {
            "tools": {
                "raw_payloads": [
                    {
                        "id": str(UUID("00000000-0000-0000-0000-000000000081")),
                        "name": "snapshot-raw-1",
                        "description": "desc",
                        "data": {"nodes": [], "edges": []},
                        "tags": [],
                        "provider_data": {"project_id": "project-1", "source_ref": "fv-create-1"},
                    }
                ]
            },
            "connections": {
                "raw_payloads": [
                    {"app_id": "cfg", "environment_variables": {"API_KEY": {"source": "raw", "value": "x"}}}
                ]
            },
            "llm": TEST_WXO_LLM,
            "operations": [
                {"op": "bind", "tool": {"name_of_raw": "snapshot-raw-1"}, "app_ids": ["cfg"]},
            ],
        }
    )
    plan = create_core_module.build_provider_create_plan(
        deployment_name="my deployment",
        provider_create=provider_create,
    )

    fake_clients = FakeWXOClients(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )
    captured: dict[str, Any] = {}

    async def mock_create_and_upload(*, clients, tool_bindings):
        _ = clients
        first_binding = tool_bindings[0]
        captured["connections"] = first_binding.connections
        return ["created-tool-1"]

    monkeypatch.setattr(
        create_core_module,
        "create_and_upload_wxo_flow_tools_with_bindings",
        mock_create_and_upload,
    )

    result = await create_core_module.apply_provider_create_plan_with_rollback(
        clients=fake_clients,
        user_id="user-1",
        db=object(),
        deployment_spec=BaseDeploymentData(
            name="my deployment",
            description="desc",
            type=DeploymentType.AGENT,
        ),
        plan=plan,
    )

    assert fake_clients.connections.create_calls == [{"app_id": "cfg"}]
    assert captured["connections"] == {"cfg": "conn-cfg"}
    assert fake_clients.agent.create_calls
    assert fake_clients.agent.create_calls[0]["name"] == "my_deployment"
    assert fake_clients.agent.create_calls[0]["tools"] == ["created-tool-1"]
    assert fake_clients.agent.create_calls[0]["llm"] == TEST_WXO_LLM
    assert result.agent_id == "dep-created"
    assert result.app_ids == ["cfg"]
    assert [(binding.tool_id, binding.app_ids) for binding in result.tool_app_bindings] == [("created-tool-1", ["cfg"])]
    assert [(binding.source_ref, binding.tool_id) for binding in result.tools_with_refs] == [
        ("fv-create-1", "created-tool-1")
    ]


@pytest.mark.anyio
async def test_apply_provider_create_plan_rolls_back_mutated_existing_tools_with_writable_payload(monkeypatch):
    provider_create = payloads_module.WatsonxDeploymentCreatePayload.model_validate(
        {
            "tools": {},
            "connections": {},
            "llm": TEST_WXO_LLM,
            "operations": [{"op": "bind", "tool": {"tool_id_with_ref": _tool_ref("tool-1")}, "app_ids": ["cfg-1"]}],
        }
    )
    plan = create_core_module.build_provider_create_plan(
        deployment_name="my deployment",
        provider_create=provider_create,
    )
    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "name": "tool-1",
                "display_name": "Tool 1",
                "description": "desc",
                "binding": {"langflow": {"connections": {"old": "conn-old"}}},
                "created_at": "read-only-field",
            }
        ]
    )
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=fake_tool,
        connections=FakeConnectionsClient(existing_app_id="cfg-1"),
    )

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id="conn-new")

    async def mock_create_agent_deployment(
        *,
        clients,  # noqa: ARG001
        tool_ids,  # noqa: ARG001
        agent_name,  # noqa: ARG001
        agent_display_name,  # noqa: ARG001
        deployment_name,  # noqa: ARG001
        description,  # noqa: ARG001
        llm,  # noqa: ARG001
    ):
        msg = "create failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(create_core_module, "validate_connection", mock_validate_connection)
    monkeypatch.setattr(create_core_module, "create_agent_deployment", mock_create_agent_deployment)

    with pytest.raises(RuntimeError, match="create failed"):
        await create_core_module.apply_provider_create_plan_with_rollback(
            clients=fake_clients,
            user_id="user-1",
            db=object(),
            deployment_spec=BaseDeploymentData(
                name="my deployment",
                description="desc",
                type=DeploymentType.AGENT,
            ),
            plan=plan,
        )

    assert len(fake_tool.update_calls) == 2
    first_payload = fake_tool.update_calls[0][1]
    rollback_payload = fake_tool.update_calls[1][1]
    assert "id" not in first_payload
    assert "created_at" not in first_payload
    assert first_payload["binding"]["langflow"]["connections"]["cfg-1"] == "conn-new"
    assert rollback_payload["binding"]["langflow"]["connections"] == {"old": "conn-old"}


@pytest.mark.anyio
async def test_apply_provider_create_plan_rolls_back_successfully_created_raw_connections_on_partial_batch_failure(
    monkeypatch,
):
    provider_create = payloads_module.WatsonxDeploymentCreatePayload.model_validate(
        {
            "tools": {},
            "connections": {
                "raw_payloads": [
                    {"app_id": "cfg-a", "environment_variables": {"API_KEY": {"source": "raw", "value": "x"}}},
                    {"app_id": "cfg-b", "environment_variables": {"API_KEY": {"source": "raw", "value": "y"}}},
                ]
            },
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "bind",
                    "tool": {"tool_id_with_ref": _tool_ref("tool-existing-1")},
                    "app_ids": ["cfg-a", "cfg-b"],
                },
            ],
        }
    )
    plan = create_core_module.build_provider_create_plan(
        deployment_name="my deployment",
        provider_create=provider_create,
    )
    fake_clients = SimpleNamespace(connections=FakeConnectionsClient())
    captured: dict[str, Any] = {}

    async def mock_create_connection_with_conflict_mapping(*, clients, app_id, payload, user_id, db, error_prefix):  # noqa: ARG001
        if app_id.endswith("cfg-a"):
            return app_id
        msg = "boom-create-connection"
        raise RuntimeError(msg)

    async def mock_rollback_created_resources(*, clients, agent_id, tool_ids, app_ids=None):  # noqa: ARG001
        captured["rollback_app_ids"] = list(app_ids or [])

    monkeypatch.setattr(
        create_core_module,
        "create_connection_with_conflict_mapping",
        mock_create_connection_with_conflict_mapping,
    )
    monkeypatch.setattr(create_core_module, "rollback_created_resources", mock_rollback_created_resources)

    with pytest.raises(RuntimeError, match="boom-create-connection"):
        await create_core_module.apply_provider_create_plan_with_rollback(
            clients=fake_clients,
            user_id="user-1",
            db=object(),
            deployment_spec=BaseDeploymentData(
                name="my deployment",
                description="desc",
                type=DeploymentType.AGENT,
            ),
            plan=plan,
        )

    assert captured.get("rollback_app_ids") == ["cfg-a"]


@pytest.mark.anyio
async def test_apply_provider_create_plan_rolls_back_all_journaled_raw_connections_when_multiple_succeed_then_fail(
    monkeypatch,
):
    provider_create = payloads_module.WatsonxDeploymentCreatePayload.model_validate(
        {
            "tools": {},
            "connections": {
                "raw_payloads": [
                    {"app_id": "cfg-a", "environment_variables": {"API_KEY": {"source": "raw", "value": "x"}}},
                    {"app_id": "cfg-b", "environment_variables": {"API_KEY": {"source": "raw", "value": "y"}}},
                    {"app_id": "cfg-c", "environment_variables": {"API_KEY": {"source": "raw", "value": "z"}}},
                ]
            },
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "bind",
                    "tool": {"tool_id_with_ref": _tool_ref("tool-existing-1")},
                    "app_ids": ["cfg-a", "cfg-b", "cfg-c"],
                },
            ],
        }
    )
    plan = create_core_module.build_provider_create_plan(
        deployment_name="my deployment",
        provider_create=provider_create,
    )
    fake_clients = SimpleNamespace(connections=FakeConnectionsClient())
    captured: dict[str, Any] = {}

    async def mock_create_connection_with_conflict_mapping(*, clients, app_id, payload, user_id, db, error_prefix):  # noqa: ARG001
        if app_id.endswith("cfg-c"):
            msg = "boom-create-connection"
            raise RuntimeError(msg)
        return app_id

    async def mock_rollback_created_resources(*, clients, agent_id, tool_ids, app_ids=None):  # noqa: ARG001
        captured["rollback_app_ids"] = list(app_ids or [])

    monkeypatch.setattr(
        create_core_module,
        "create_connection_with_conflict_mapping",
        mock_create_connection_with_conflict_mapping,
    )
    monkeypatch.setattr(create_core_module, "rollback_created_resources", mock_rollback_created_resources)

    with pytest.raises(RuntimeError, match="boom-create-connection"):
        await create_core_module.apply_provider_create_plan_with_rollback(
            clients=fake_clients,
            user_id="user-1",
            db=object(),
            deployment_spec=BaseDeploymentData(
                name="my deployment",
                description="desc",
                type=DeploymentType.AGENT,
            ),
            plan=plan,
        )

    assert captured["rollback_app_ids"] == ["cfg-a", "cfg-b"]


@pytest.mark.anyio
async def test_apply_provider_update_plan_rolls_back_successfully_created_raw_connections_on_partial_batch_failure(
    monkeypatch,
):
    provider_update = payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
        {
            "tools": {},
            "connections": {
                "raw_payloads": [
                    {"app_id": "cfg-a", "environment_variables": {"API_KEY": {"source": "raw", "value": "x"}}},
                    {"app_id": "cfg-b", "environment_variables": {"API_KEY": {"source": "raw", "value": "y"}}},
                ]
            },
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "bind",
                    "tool": {"tool_id_with_ref": _tool_ref("tool-existing-1")},
                    "app_ids": ["cfg-a", "cfg-b"],
                },
            ],
        }
    )
    plan = update_core_module.build_provider_update_plan(
        agent={"id": "dep-1", "tools": ["tool-existing-1"]},
        provider_update=provider_update,
    )
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-existing-1"]}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )
    captured: dict[str, Any] = {}

    async def mock_create_connection_with_conflict_mapping(*, clients, app_id, payload, user_id, db, error_prefix):  # noqa: ARG001
        if app_id.endswith("cfg-a"):
            return app_id
        msg = "boom-update-connection"
        raise RuntimeError(msg)

    async def mock_rollback_update_resources(*, clients, created_tool_ids, created_app_id, original_tools):  # noqa: ARG001
        _ = (created_tool_ids, created_app_id, original_tools)

    async def mock_rollback_created_app_ids(*, clients, created_app_ids):  # noqa: ARG001
        captured["rolled_back_app_ids"] = list(created_app_ids)

    monkeypatch.setattr(
        update_core_module,
        "create_connection_with_conflict_mapping",
        mock_create_connection_with_conflict_mapping,
    )
    monkeypatch.setattr(update_core_module, "rollback_update_resources", mock_rollback_update_resources)
    monkeypatch.setattr(update_core_module, "rollback_created_app_ids", mock_rollback_created_app_ids)

    with pytest.raises(RuntimeError, match="boom-update-connection"):
        await update_core_module.apply_provider_update_plan_with_rollback(
            clients=fake_clients,
            user_id="user-1",
            db=object(),
            agent_id="dep-1",
            agent={"id": "dep-1", "tools": ["tool-existing-1"]},
            update_payload={},
            plan=plan,
        )

    assert captured["rolled_back_app_ids"] == ["cfg-a"]


@pytest.mark.anyio
async def test_apply_provider_update_plan_rolls_back_all_journaled_raw_connections_when_multiple_succeed_then_fail(
    monkeypatch,
):
    provider_update = payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
        {
            "tools": {},
            "connections": {
                "raw_payloads": [
                    {"app_id": "cfg-a", "environment_variables": {"API_KEY": {"source": "raw", "value": "x"}}},
                    {"app_id": "cfg-b", "environment_variables": {"API_KEY": {"source": "raw", "value": "y"}}},
                    {"app_id": "cfg-c", "environment_variables": {"API_KEY": {"source": "raw", "value": "z"}}},
                ]
            },
            "llm": TEST_WXO_LLM,
            "operations": [
                {
                    "op": "bind",
                    "tool": {"tool_id_with_ref": _tool_ref("tool-existing-1")},
                    "app_ids": ["cfg-a", "cfg-b", "cfg-c"],
                },
            ],
        }
    )
    plan = update_core_module.build_provider_update_plan(
        agent={"id": "dep-1", "tools": ["tool-existing-1"]},
        provider_update=provider_update,
    )
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-existing-1"]}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )
    captured: dict[str, Any] = {}

    async def mock_create_connection_with_conflict_mapping(*, clients, app_id, payload, user_id, db, error_prefix):  # noqa: ARG001
        if app_id.endswith("cfg-c"):
            msg = "boom-update-connection"
            raise RuntimeError(msg)
        return app_id

    async def mock_rollback_update_resources(*, clients, created_tool_ids, created_app_id, original_tools):  # noqa: ARG001
        _ = (created_tool_ids, created_app_id, original_tools)

    async def mock_rollback_created_app_ids(*, clients, created_app_ids):  # noqa: ARG001
        captured["rolled_back_app_ids"] = list(created_app_ids)

    monkeypatch.setattr(
        update_core_module,
        "create_connection_with_conflict_mapping",
        mock_create_connection_with_conflict_mapping,
    )
    monkeypatch.setattr(update_core_module, "rollback_update_resources", mock_rollback_update_resources)
    monkeypatch.setattr(update_core_module, "rollback_created_app_ids", mock_rollback_created_app_ids)

    with pytest.raises(RuntimeError, match="boom-update-connection"):
        await update_core_module.apply_provider_update_plan_with_rollback(
            clients=fake_clients,
            user_id="user-1",
            db=object(),
            agent_id="dep-1",
            agent={"id": "dep-1", "tools": ["tool-existing-1"]},
            update_payload={},
            plan=plan,
        )

    assert captured["rolled_back_app_ids"] == ["cfg-a", "cfg-b"]


@pytest.mark.anyio
async def test_create_provider_data_prefixes_tool_and_deployment_names_but_not_connection_app_ids(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = FakeWXOClients(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )
    captured: dict[str, Any] = {}

    async def mock_create_and_upload(*, clients, tool_bindings):
        _ = clients
        first_binding = tool_bindings[0]
        captured["connections"] = first_binding.connections
        return ["created-tool-1"]

    _attach_provider_clients(service, fake_clients)
    monkeypatch.setattr(
        create_core_module,
        "create_and_upload_wxo_flow_tools_with_bindings",
        mock_create_and_upload,
    )

    result = await service.create(
        user_id="user-1",
        payload=DeploymentCreate(
            spec=BaseDeploymentData(
                name="my deployment",
                description="desc",
                type=DeploymentType.AGENT,
            ),
            provider_data={
                "tools": {
                    "raw_payloads": [
                        {
                            "id": str(UUID("00000000-0000-0000-0000-000000000091")),
                            "name": "snapshot-new-1",
                            "description": "desc",
                            "data": {"nodes": [], "edges": []},
                            "tags": [],
                            "provider_data": {"project_id": "project-1", "source_ref": "fv-create-service-1"},
                        }
                    ]
                },
                "connections": {
                    "raw_payloads": [
                        {"app_id": "cfg", "environment_variables": {"API_KEY": {"source": "raw", "value": "x"}}}
                    ]
                },
                "llm": TEST_WXO_LLM,
                "operations": [
                    {"op": "bind", "tool": {"name_of_raw": "snapshot-new-1"}, "app_ids": ["cfg"]},
                ],
            },
        ),
        db=object(),
    )

    assert fake_clients.connections.create_calls == [{"app_id": "cfg"}]
    assert captured["connections"] == {"cfg": "conn-cfg"}
    assert fake_clients.agent.create_calls
    assert fake_clients.agent.create_calls[0]["name"] == "my_deployment"
    assert fake_clients.agent.create_calls[0]["display_name"] == "my deployment"
    assert fake_clients.agent.create_calls[0]["description"] == "desc"
    assert fake_clients.agent.create_calls[0]["tools"] == ["created-tool-1"]
    assert fake_clients.agent.create_calls[0]["llm"] == TEST_WXO_LLM
    assert result.config_id is None
    assert result.snapshot_ids == []
    assert result.provider_result is not None
    provider_result = (
        result.provider_result.model_dump() if hasattr(result.provider_result, "model_dump") else result.provider_result
    )
    assert provider_result["app_ids"] == ["cfg"]
    assert provider_result["tool_app_bindings"] == [{"tool_id": "created-tool-1", "app_ids": ["cfg"]}]
    assert provider_result["tools_with_refs"] == [{"source_ref": "fv-create-service-1", "tool_id": "created-tool-1"}]


@pytest.mark.anyio
async def test_list_deployments_filters_with_provider_draft_filters(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": []},
        listed_agents=[
            {"id": "dep-1", "name": "deployment-1", "tools": [], "environments": [{"name": "draft"}]},
            {"id": "dep-2", "name": "deployment-2", "tools": [], "environments": [{"name": "prod"}]},
            {"id": "dep-3", "name": "deployment-3", "tools": [], "environments": [{"name": "draft"}]},
        ],
    )
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_agent,
            agent=fake_agent,
            tool=FakeToolClient([]),
            connections=FakeConnectionsClient(),
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list(
        user_id="user-1",
        db=object(),
        params=DeploymentListParams(
            deployment_types=[DeploymentType.AGENT],
            provider_params={"ids": ["dep-2"], "names": ["deployment-3"], "environment": "draft"},
        ),
    )

    assert sorted(item.id for item in result.deployments) == ["dep-3"]


@pytest.mark.anyio
async def test_update_provider_data_maps_raw_connection_conflict_to_deployment_conflict(monkeypatch):
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient([{"id": "tool-1", "binding": {"langflow": {"connections": {}}}}]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_create_config(*, clients, config, user_id, db):  # noqa: ARG001
        response = SimpleNamespace(status_code=409, text='{"detail":"already exists"}')
        raise ClientAPIException(response=response)

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(shared_core_module, "create_config", mock_create_config)

    with pytest.raises(ResourceConflictError, match="already exists in the provider") as exc_info:
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=DeploymentUpdate(
                provider_data={
                    "tools": {
                        "raw_payloads": [
                            {
                                "id": str(UUID("00000000-0000-0000-0000-000000000012")),
                                "name": "snapshot-new-1",
                                "description": "desc",
                                "data": {"nodes": [], "edges": []},
                                "tags": [],
                                "provider_data": {"project_id": "project-1", "source_ref": "fv-conflict-1"},
                            }
                        ]
                    },
                    "connections": {
                        "raw_payloads": [
                            {
                                "app_id": "cfg",
                                "environment_variables": {"API_KEY": {"source": "raw", "value": "secret"}},
                            }
                        ]
                    },
                    "llm": TEST_WXO_LLM,
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"name_of_raw": "snapshot-new-1"},
                            "app_ids": ["cfg"],
                        }
                    ],
                }
            ),
            db=object(),
        )
    assert exc_info.value.resource == "connection"


@pytest.mark.anyio
async def test_create_provider_data_maps_raw_connection_conflict_to_deployment_conflict(monkeypatch):
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = FakeWXOClients(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )
    captured: dict[str, str] = {}

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_create_config(*, clients, config, user_id, db):  # noqa: ARG001
        captured["attempted_app_id"] = config.name
        response = SimpleNamespace(status_code=409, text='{"detail":"already exists"}')
        raise ClientAPIException(response=response)

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(shared_core_module, "create_config", mock_create_config)

    with pytest.raises(ResourceConflictError, match="already exists in the provider") as exc_info:
        await service.create(
            user_id="user-1",
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
                provider_data={
                    "tools": {
                        "raw_payloads": [
                            {
                                "id": str(UUID("00000000-0000-0000-0000-000000000013")),
                                "name": "snapshot-new-1",
                                "description": "desc",
                                "data": {"nodes": [], "edges": []},
                                "tags": [],
                                "provider_data": {"project_id": "project-1", "source_ref": "fv-create-conflict-1"},
                            }
                        ]
                    },
                    "connections": {
                        "raw_payloads": [
                            {
                                "app_id": "cfg",
                                "environment_variables": {"API_KEY": {"source": "raw", "value": "secret"}},
                            }
                        ]
                    },
                    "llm": TEST_WXO_LLM,
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"name_of_raw": "snapshot-new-1"},
                            "app_ids": ["cfg"],
                        }
                    ],
                },
            ),
            db=object(),
        )
    assert exc_info.value.resource == "connection"

    assert captured["attempted_app_id"] == "cfg"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider_data", "error_message"),
    [
        (
            {
                "tools": {},
                "connections": {
                    "raw_payloads": [
                        {
                            "app_id": "app-in-use",
                            "environment_variables": {"API_KEY": {"source": "raw", "value": "secret"}},
                        },
                        {
                            "app_id": "app-unused",
                            "environment_variables": {"API_KEY": {"source": "raw", "value": "secret"}},
                        },
                    ]
                },
                "llm": TEST_WXO_LLM,
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"tool_id_with_ref": _tool_ref("tool-1")},
                        "app_ids": ["app-in-use"],
                    }
                ],
            },
            "connections\\.raw_payloads contains app_id values not referenced by operations",
        ),
    ],
)
async def test_update_provider_data_validation_errors_raise_invalid_content(
    monkeypatch, provider_data: dict, error_message: str
):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient([{"id": "tool-1", "binding": {"langflow": {"connections": {}}}}]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(InvalidContentError, match=error_message):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=DeploymentUpdate(provider_data=provider_data),
            db=object(),
        )


@pytest.mark.anyio
async def test_update_provider_data_rolls_back_mutated_tools_with_writable_payload(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    class FailingAgentClient(FakeAgentClient):
        def update(self, deployment_id: str, payload: dict):
            self.update_calls.append((deployment_id, payload))
            msg = "agent update failed"
            raise RuntimeError(msg)

    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "name": "tool-1",
                "display_name": "Tool 1",
                "description": "desc",
                "binding": {"langflow": {"connections": {"old": "conn-old"}}},
                "created_at": "read-only-field",
            }
        ]
    )
    fake_clients = SimpleNamespace(
        agent=FailingAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=fake_tool,
        connections=FakeConnectionsClient(existing_app_id="cfg-1"),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id="conn-new")

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(update_core_module, "validate_connection", mock_validate_connection)

    with pytest.raises(DeploymentError, match="Please check server logs for details"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=DeploymentUpdate(
                spec=BaseDeploymentDataUpdate(description="trigger update"),
                provider_data={
                    "tools": {},
                    "connections": {},
                    "llm": TEST_WXO_LLM,
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"tool_id_with_ref": _tool_ref("tool-1")},
                            "app_ids": ["cfg-1"],
                        }
                    ],
                },
            ),
            db=object(),
        )

    assert len(fake_tool.update_calls) == 2
    first_payload = fake_tool.update_calls[0][1]
    rollback_payload = fake_tool.update_calls[1][1]
    assert "id" not in first_payload
    assert "created_at" not in first_payload
    assert first_payload["binding"]["langflow"]["connections"]["cfg-1"] == "conn-new"
    assert rollback_payload["binding"]["langflow"]["connections"] == {"old": "conn-old"}


@pytest.mark.anyio
async def test_update_provider_data_rolls_back_partially_created_raw_tools(monkeypatch):
    core_tools_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.core.tools")

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_connections = FakeConnectionsClient()
    fake_tool = FakeToolClient([])
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=fake_tool,
        connections=fake_connections,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_create_config(*, clients, config, user_id, db):  # noqa: ARG001
        fake_connections._connections_by_app_id[config.name] = f"conn-{config.name}"
        return config.name

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id=f"conn-{app_id}")

    async def mock_create_and_upload_with_bindings(*, clients, tool_bindings):
        _ = clients, tool_bindings
        raise core_tools_module.ToolUploadBatchError(
            created_tool_ids=["created-tool-1"],
            errors=[RuntimeError("upload failed")],
        )

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(shared_core_module, "create_config", mock_create_config)
    monkeypatch.setattr(update_core_module, "validate_connection", mock_validate_connection)
    monkeypatch.setattr(
        update_core_module,
        "create_and_upload_wxo_flow_tools_with_bindings",
        mock_create_and_upload_with_bindings,
    )

    with pytest.raises(DeploymentError, match="Please check server logs for details"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=DeploymentUpdate(
                provider_data={
                    "tools": {
                        "raw_payloads": [
                            {
                                "id": str(UUID("00000000-0000-0000-0000-000000000021")),
                                "name": "snapshot-new-1",
                                "description": "desc",
                                "data": {"nodes": [], "edges": []},
                                "tags": [],
                                "provider_data": {"project_id": "project-1", "source_ref": "fv-rollback-1"},
                            }
                        ]
                    },
                    "connections": {
                        "raw_payloads": [
                            {
                                "app_id": "cfg",
                                "environment_variables": {"API_KEY": {"source": "raw", "value": "secret"}},
                            }
                        ]
                    },
                    "llm": TEST_WXO_LLM,
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"name_of_raw": "snapshot-new-1"},
                            "app_ids": ["cfg"],
                        }
                    ],
                }
            ),
            db=object(),
        )

    assert fake_tool.delete_calls == ["created-tool-1"]
    assert fake_connections.delete_calls == ["cfg"]


@pytest.mark.anyio
async def test_create_provider_data_rolls_back_partially_created_raw_tools(monkeypatch):
    core_tools_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.core.tools")

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_connections = FakeConnectionsClient()
    fake_tool = FakeToolClient([])
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=fake_tool,
        connections=fake_connections,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_create_connection_with_conflict_mapping(*, clients, app_id, payload, user_id, db, error_prefix):  # noqa: ARG001
        fake_connections._connections_by_app_id[app_id] = f"conn-{app_id}"
        return app_id

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id=f"conn-{app_id}")

    async def mock_create_and_upload_with_bindings(*, clients, tool_bindings):
        _ = clients, tool_bindings
        msg = "upload failed"
        raise core_tools_module.ToolUploadBatchError(
            created_tool_ids=["created-tool-1"],
            errors=[RuntimeError(msg)],
        )

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(
        create_core_module,
        "create_connection_with_conflict_mapping",
        mock_create_connection_with_conflict_mapping,
    )
    monkeypatch.setattr(create_core_module, "validate_connection", mock_validate_connection)
    monkeypatch.setattr(
        create_core_module,
        "create_and_upload_wxo_flow_tools_with_bindings",
        mock_create_and_upload_with_bindings,
    )

    with pytest.raises(DeploymentError, match="Please check server logs for details"):
        await service.create(
            user_id="user-1",
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
                provider_data={
                    "tools": {
                        "raw_payloads": [
                            {
                                "id": str(UUID("00000000-0000-0000-0000-000000000023")),
                                "name": "snapshot-new-1",
                                "description": "desc",
                                "data": {"nodes": [], "edges": []},
                                "tags": [],
                                "provider_data": {"project_id": "project-1", "source_ref": "fv-create-rollback-1"},
                            }
                        ]
                    },
                    "connections": {
                        "raw_payloads": [
                            {
                                "app_id": "cfg",
                                "environment_variables": {"API_KEY": {"source": "raw", "value": "secret"}},
                            }
                        ]
                    },
                    "llm": TEST_WXO_LLM,
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"name_of_raw": "snapshot-new-1"},
                            "app_ids": ["cfg"],
                        }
                    ],
                },
            ),
            db=object(),
        )

    assert fake_tool.delete_calls == ["created-tool-1"]
    assert fake_connections.delete_calls == ["cfg"]


@pytest.mark.anyio
async def test_process_raw_flows_with_app_id_awaits_connection_validation(monkeypatch):
    from langflow.services.adapters.deployment.watsonx_orchestrate.core import tools as tools_core_module

    fake_clients = SimpleNamespace(
        tool=SimpleNamespace(),
        connections=SimpleNamespace(),
    )
    captured: dict[str, object] = {}

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id="conn-123")

    async def mock_create_and_upload_wxo_flow_tools(
        *,
        clients,
        flow_payloads,
        connections,
    ):
        captured["clients"] = clients
        captured["flow_payloads"] = flow_payloads
        captured["connections"] = connections
        return []

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.core.config.validate_connection",
        mock_validate_connection,
    )
    monkeypatch.setattr(
        tools_core_module,
        "create_and_upload_wxo_flow_tools",
        mock_create_and_upload_wxo_flow_tools,
    )

    result = await tools_core_module.process_raw_flows_with_app_id(
        clients=fake_clients,
        app_id="app-1",
        flows=[],
    )

    assert result == []
    assert captured["connections"] == {"app-1": "conn-123"}


@pytest.mark.anyio
async def test_process_raw_flows_with_app_id_returns_source_ref_bindings(monkeypatch):
    from langflow.services.adapters.deployment.watsonx_orchestrate.core import tools as tools_core_module

    fake_clients = SimpleNamespace(
        tool=SimpleNamespace(),
        connections=SimpleNamespace(),
    )

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id="conn-123")

    async def mock_create_and_upload_wxo_flow_tools(
        *,
        clients,  # noqa: ARG001
        flow_payloads,  # noqa: ARG001
        connections,  # noqa: ARG001
    ):
        return ["tool-1", "tool-2"]

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.core.config.validate_connection",
        mock_validate_connection,
    )
    monkeypatch.setattr(
        tools_core_module,
        "create_and_upload_wxo_flow_tools",
        mock_create_and_upload_wxo_flow_tools,
    )

    result = await tools_core_module.process_raw_flows_with_app_id(
        clients=fake_clients,
        app_id="app-1",
        flows=[
            BaseFlowArtifact[payloads_module.WatsonxFlowArtifactProviderData](
                id=UUID("00000000-0000-0000-0000-000000000001"),
                name="snapshot-one",
                description="desc",
                data={"nodes": [], "edges": []},
                tags=[],
                provider_data=payloads_module.WatsonxFlowArtifactProviderData(
                    project_id="project-1",
                    source_ref="fv-1",
                ),
            ),
            BaseFlowArtifact[payloads_module.WatsonxFlowArtifactProviderData](
                id=UUID("00000000-0000-0000-0000-000000000002"),
                name="snapshot-two",
                description="desc",
                data={"nodes": [], "edges": []},
                tags=[],
                provider_data=payloads_module.WatsonxFlowArtifactProviderData(
                    project_id="project-1",
                    source_ref="fv-2",
                ),
            ),
        ],
    )

    assert [
        {
            "source_ref": binding.source_ref,
            "tool_id": binding.tool_id,
        }
        for binding in result
    ] == [
        {
            "source_ref": "fv-1",
            "tool_id": "tool-1",
        },
        {
            "source_ref": "fv-2",
            "tool_id": "tool-2",
        },
    ]


@pytest.mark.anyio
async def test_process_raw_flows_with_app_id_accepts_typed_provider_data(monkeypatch):
    from langflow.services.adapters.deployment.watsonx_orchestrate.core import tools as tools_core_module

    fake_clients = SimpleNamespace(
        tool=SimpleNamespace(),
        connections=SimpleNamespace(),
    )

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id="conn-123")

    async def mock_create_and_upload_wxo_flow_tools(
        *,
        clients,  # noqa: ARG001
        flow_payloads,  # noqa: ARG001
        connections,  # noqa: ARG001
    ):
        return ["tool-1"]

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.core.config.validate_connection",
        mock_validate_connection,
    )
    monkeypatch.setattr(
        tools_core_module,
        "create_and_upload_wxo_flow_tools",
        mock_create_and_upload_wxo_flow_tools,
    )

    result = await tools_core_module.process_raw_flows_with_app_id(
        clients=fake_clients,
        app_id="app-1",
        flows=[
            BaseFlowArtifact[payloads_module.WatsonxFlowArtifactProviderData](
                id=UUID("00000000-0000-0000-0000-000000000001"),
                name="snapshot-one",
                description="desc",
                data={"nodes": [], "edges": []},
                tags=[],
                provider_data=payloads_module.WatsonxFlowArtifactProviderData(
                    project_id="project-1",
                    source_ref="fv-typed-1",
                ),
            ),
        ],
    )

    assert len(result) == 1
    assert result[0].source_ref == "fv-typed-1"
    assert result[0].tool_id == "tool-1"


@pytest.mark.anyio
async def test_process_raw_flows_with_app_id_rejects_plain_dict_provider_data(monkeypatch):
    from langflow.services.adapters.deployment.watsonx_orchestrate.core import tools as tools_core_module

    fake_clients = SimpleNamespace(
        tool=SimpleNamespace(),
        connections=SimpleNamespace(),
    )

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id="conn-123")

    async def mock_create_and_upload_wxo_flow_tools(
        *,
        clients,  # noqa: ARG001
        flow_payloads,  # noqa: ARG001
        connections,  # noqa: ARG001
    ):
        return ["tool-1"]

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.core.config.validate_connection",
        mock_validate_connection,
    )
    monkeypatch.setattr(
        tools_core_module,
        "create_and_upload_wxo_flow_tools",
        mock_create_and_upload_wxo_flow_tools,
    )

    with pytest.raises(
        InvalidContentError,
        match=r"Flow payload provider_data must be a WatsonxFlowArtifactProviderData model instance\.",
    ):
        await tools_core_module.process_raw_flows_with_app_id(
            clients=fake_clients,
            app_id="app-1",
            flows=[
                BaseFlowArtifact(
                    id=UUID("00000000-0000-0000-0000-000000000001"),
                    name="snapshot-one",
                    description="desc",
                    data={"nodes": [], "edges": []},
                    tags=[],
                    provider_data={"project_id": "project-1", "source_ref": "fv-dict-1"},
                ),
            ],
        )


def test_create_wxo_flow_tool_keeps_load_from_db_global_values_unprefixed(monkeypatch):
    captured_tool_definition = {}
    flow_payload = BaseFlowArtifact[payloads_module.WatsonxFlowArtifactProviderData](
        id="00000000-0000-0000-0000-000000000001",
        name="flow",
        description="desc",
        data={
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {
                                    "load_from_db": True,
                                    "value": "OPENAI_API_KEY",
                                },
                                "plain_value": {
                                    "load_from_db": False,
                                    "value": "DO_NOT_TOUCH",
                                },
                            }
                        }
                    }
                }
            ],
            "edges": [],
        },
        tags=[],
        provider_data=payloads_module.WatsonxFlowArtifactProviderData(
            project_id="project-123",
            source_ref="fv-flow-template-1",
        ),
    )

    fake_tool = SimpleNamespace(
        __tool_spec__=SimpleNamespace(
            model_dump=lambda **kwargs: {"name": "flow"},  # noqa: ARG005
        )
    )

    def mock_create_langflow_tool(*, tool_definition, connections, show_details):  # noqa: ARG001
        assert show_details is False
        captured_tool_definition.update(tool_definition)
        return fake_tool

    monkeypatch.setattr(tools_module, "create_langflow_tool", mock_create_langflow_tool)
    monkeypatch.setattr(
        tools_module,
        "build_langflow_artifact_bytes",
        lambda **kwargs: b"artifact",  # noqa: ARG005
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import create_wxo_flow_tool

    create_wxo_flow_tool(
        flow_payload=flow_payload,
        connections={},
    )

    template = captured_tool_definition["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] == "OPENAI_API_KEY"
    assert template["plain_value"]["value"] == "DO_NOT_TOUCH"


def test_create_wxo_flow_tool_excludes_provider_data_from_artifact(monkeypatch):
    """provider_data must not leak into the flow JSON zipped inside the artifact.

    WxO's tool runtime chokes on unexpected top-level keys like ``provider_data``
    in the flow definition, causing executions to hang indefinitely.
    """
    captured_flow_definition = {}

    flow_payload = BaseFlowArtifact[payloads_module.WatsonxFlowArtifactProviderData](
        id="00000000-0000-0000-0000-000000000001",
        name="flow",
        description="desc",
        data={
            "nodes": [
                {
                    "data": {
                        "type": "ChatInput",
                        "id": "ChatInput-1",
                        "node": {"template": {"_type": "CustomComponent"}},
                    }
                },
                {
                    "data": {
                        "type": "ChatOutput",
                        "id": "ChatOutput-1",
                        "node": {"template": {"_type": "CustomComponent"}},
                    }
                },
            ],
            "edges": [],
        },
        tags=[],
        provider_data=payloads_module.WatsonxFlowArtifactProviderData(
            project_id="project-123",
            source_ref="src-ref-1",
        ),
    )

    fake_tool = SimpleNamespace(
        __tool_spec__=SimpleNamespace(
            model_dump=lambda **kwargs: {"name": "flow"},  # noqa: ARG005
        )
    )

    def mock_create_langflow_tool(*, tool_definition, connections, show_details):  # noqa: ARG001
        assert show_details is False
        captured_flow_definition.update(tool_definition)
        return fake_tool

    monkeypatch.setattr(tools_module, "create_langflow_tool", mock_create_langflow_tool)
    monkeypatch.setattr(
        tools_module,
        "build_langflow_artifact_bytes",
        lambda **kwargs: b"artifact",  # noqa: ARG005
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import create_wxo_flow_tool

    create_wxo_flow_tool(
        flow_payload=flow_payload,
        connections={},
    )

    assert "provider_data" not in captured_flow_definition
    assert "data" in captured_flow_definition
    assert "name" in captured_flow_definition
    assert "description" in captured_flow_definition


def test_create_wxo_flow_tool_requires_provider_data_project_id():
    flow_payload = BaseFlowArtifact(
        id="00000000-0000-0000-0000-000000000001",
        name="flow",
        description="desc",
        data={"nodes": [], "edges": []},
        tags=[],
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import create_wxo_flow_tool

    with pytest.raises(
        InvalidContentError,
        match=r"Flow payload provider_data must be a WatsonxFlowArtifactProviderData model instance\.",
    ):
        create_wxo_flow_tool(
            flow_payload=flow_payload,
            connections={},
        )


def test_create_wxo_flow_tool_normalizes_name_for_raw_payload(monkeypatch):
    flow_payload = BaseFlowArtifact[payloads_module.WatsonxFlowArtifactProviderData](
        id="00000000-0000-0000-0000-000000000001",
        name="basicllmwxo",
        description="desc",
        data={"nodes": [], "edges": []},
        tags=[],
        provider_data=payloads_module.WatsonxFlowArtifactProviderData(
            project_id="project-123",
            source_ref="fv-prefix-1",
        ),
    )

    fake_tool = SimpleNamespace(
        __tool_spec__=SimpleNamespace(
            model_dump=lambda **kwargs: {"name": "basicllmwxo"},  # noqa: ARG005
        )
    )
    monkeypatch.setattr(
        tools_module,
        "create_langflow_tool",
        lambda **kwargs: fake_tool,  # noqa: ARG005
    )
    monkeypatch.setattr(
        tools_module,
        "build_langflow_artifact_bytes",
        lambda **kwargs: b"artifact",  # noqa: ARG005
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import create_wxo_flow_tool

    tool_payload, artifact_bytes = create_wxo_flow_tool(
        flow_payload=flow_payload,
        connections={},
    )

    assert tool_payload["name"] == "basicllmwxo"
    assert tool_payload["binding"]["langflow"]["project_id"] == "project-123"
    assert artifact_bytes == b"artifact"


@pytest.mark.anyio
async def test_rollback_create_result_cleans_up_agent_tools_and_apps(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace()
    captured: dict[str, object] = {}

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_rollback_created_resources(*, clients, agent_id, tool_ids, app_ids=None):
        captured["clients"] = clients
        captured["agent_id"] = agent_id
        captured["tool_ids"] = list(tool_ids)
        captured["app_ids"] = list(app_ids or [])

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(service_module, "rollback_created_resources", mock_rollback_created_resources)

    await service.rollback_create_result(
        user_id="user-1",
        deployment_id="dep-created",
        provider_result={
            "app_ids": ["cfg"],
            "tools_with_refs": [
                {"source_ref": "fv-1", "tool_id": "tool-1"},
                {"source_ref": "fv-2", "tool_id": "tool-2"},
            ],
        },
        db=object(),
    )

    assert captured == {
        "clients": fake_clients,
        "agent_id": "dep-created",
        "tool_ids": ["tool-1", "tool-2"],
        "app_ids": ["cfg"],
    }


@pytest.mark.anyio
async def test_create_execution_posts_runs_payload(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": []})
    fake_base = FakeBaseClient()
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_base,
            agent=fake_agent,
            tool=FakeToolClient([]),
            connections=FakeConnectionsClient(),
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.create_execution(
        user_id="user-1",
        db=object(),
        payload=ExecutionCreate(
            deployment_id="dep-1",
            provider_data={"input": "hello from test"},
        ),
    )

    assert result.deployment_id == "dep-1"
    assert result.execution_id == "run-1"
    assert result.provider_result["status"] == "accepted"
    assert result.provider_result["execution_id"] == "run-1"
    assert result.provider_result["thread_id"] == "thread-1"
    assert fake_base.post_calls
    path, payload = fake_base.post_calls[0]
    assert path == "/runs"
    assert payload["agent_id"] == "dep-1"
    assert payload["message"] == {"role": "user", "content": "hello from test"}


@pytest.mark.anyio
async def test_get_execution_returns_completed_output(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": []})
    fake_base = FakeBaseClient(
        get_payloads={
            "/runs/run-1": {
                "id": "run-1",
                "status": "completed",
                "agent_id": "dep-1",
                "completed_at": "2026-03-08T18:23:25.277362Z",
                "result": {"data": "Final assistant response"},
            }
        }
    )
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_base,
            agent=fake_agent,
            tool=FakeToolClient([]),
            connections=FakeConnectionsClient(),
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.get_execution(
        user_id="user-1",
        db=object(),
        execution_id="run-1",
    )

    assert result.execution_id == "run-1"
    assert result.provider_result["status"] == "completed"
    assert result.provider_result["agent_id"] == "dep-1"
    assert result.provider_result["execution_id"] == "run-1"
    assert result.provider_result["completed_at"] == "2026-03-08T18:23:25.277362Z"


@pytest.mark.anyio
async def test_get_execution_fetches_result_payload(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": []})
    fake_base = FakeBaseClient(
        get_payloads={
            "/runs/run-1": {
                "id": "run-1",
                "status": "completed",
                "agent_id": "dep-1",
                "result": {"output": "some result"},
            }
        }
    )
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_base,
            agent=fake_agent,
            tool=FakeToolClient([]),
            connections=FakeConnectionsClient(),
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.get_execution(
        user_id="user-1",
        db=object(),
        execution_id="run-1",
    )

    assert result.provider_result["status"] == "completed"
    assert result.provider_result["agent_id"] == "dep-1"
    assert result.provider_result["result"] == {"output": "some result"}


@pytest.mark.anyio
async def test_get_execution_requires_execution_id(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": []})
    fake_base = FakeBaseClient()
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_base,
            agent=fake_agent,
            tool=FakeToolClient([]),
            connections=FakeConnectionsClient(),
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(ValueError, match="execution_id"):
        await service.get_execution(
            user_id="user-1",
            db=object(),
            execution_id="",
        )


@pytest.mark.anyio
async def test_get_execution_handles_client_api_exception(monkeypatch):
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_base = FakeBaseClient()

    def failing_get(path: str, params=None):  # noqa: ARG001
        resp = SimpleNamespace(status_code=500, text='{"detail": "internal error"}')
        raise ClientAPIException(response=resp)

    fake_base._get = failing_get
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_base,
            agent=FakeAgentClient({"id": "dep-1", "tools": []}),
            tool=FakeToolClient([]),
            connections=FakeConnectionsClient(),
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError, match="getting a deployment execution"):
        await service.get_execution(
            user_id="user-1",
            db=object(),
            execution_id="run-1",
        )


@pytest.mark.anyio
async def test_list_configs_single_deployment_scope(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "name": "tool-one",
                "binding": {
                    "langflow": {
                        "connections": {
                            "cfg-1": "conn-1",
                        }
                    }
                },
                "created_at": "2026-03-08T18:23:25.277362Z",
            }
        ]
    )
    connections_client = FakeConnectionsClient()
    connections_client._draft_entries_by_id = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-1",
                "app_id": "cfg-1",
                "security_scheme": "key_value_creds",
                "environment": "live",
            }
        )
    ]
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(
        user_id="user-1",
        db=object(),
        params=ConfigListParams(deployment_ids=["dep-1"]),
    )

    assert result.configs == []


@pytest.mark.anyio
async def test_list_configs_deployment_scope_filters_to_key_value_creds(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1", "tool-2"]})
    fake_tool = FakeToolClient(
        [
            {"id": "tool-1", "name": "tool-one", "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}}},
            {"id": "tool-2", "name": "tool-two", "binding": {"langflow": {"connections": {"cfg-2": "conn-2"}}}},
        ]
    )
    connections_client = FakeConnectionsClient()
    connections_client._draft_entries_by_id = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-1",
                "app_id": "cfg-1",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        ),
        ListConfigsResponse.model_validate({"connection_id": "conn-2", "app_id": "cfg-2", "security_scheme": "oauth2"}),
    ]
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(
        user_id="user-1",
        db=object(),
        params=ConfigListParams(deployment_ids=["dep-1"]),
    )

    assert [config.id for config in result.configs] == ["conn-1"]
    assert [config.name for config in result.configs] == ["cfg-1"]
    assert [config.provider_data for config in result.configs] == [{"type": "key_value_creds", "environment": "draft"}]


@pytest.mark.anyio
async def test_list_configs_deployment_scope_warns_on_stale_tool_ids(monkeypatch, caplog):
    """Stale tool IDs can be deleted between reads; keep resolved configs and warn."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1", "deleted-tool"]})
    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "name": "tool-one",
                "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}},
            }
        ]
    )
    connections_client = FakeConnectionsClient()
    connections_client._draft_entries_by_id = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-1",
                "app_id": "cfg-1",
                "security_scheme": "key_value_creds",
                "environment": "live",
            }
        )
    ]
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    import logging

    with caplog.at_level(logging.WARNING):
        result = await service.list_configs(
            user_id="user-1",
            db=object(),
            params=ConfigListParams(deployment_ids=["dep-1"]),
        )

    assert result.configs == []
    assert "tool IDs not returned by provider" in caplog.text
    assert "deleted-tool" in caplog.text
    assert "dep-1" in caplog.text


@pytest.mark.anyio
async def test_list_configs_deployment_scope_fails_fast_when_type_enrichment_fails(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "name": "tool-one",
                "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}},
            }
        ]
    )
    connections_client = FakeConnectionsClient()
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    def get_drafts_by_ids_raises(conn_ids):  # noqa: ARG001
        msg = "provider timeout"
        raise RuntimeError(msg)

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(connections_client, "get_drafts_by_ids", get_drafts_by_ids_raises)

    with pytest.raises(DeploymentError, match="listing deployment configs"):
        await service.list_configs(
            user_id="user-1",
            db=object(),
            params=ConfigListParams(deployment_ids=["dep-1"]),
        )


@pytest.mark.anyio
async def test_list_configs_deployment_scope_accepts_schema_compatible_detailed_connection(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "name": "tool-one",
                "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}},
            }
        ]
    )
    connections_client = FakeConnectionsClient()
    connections_client._draft_entries_by_id = [
        SimpleNamespace(connection_id="conn-1", app_id="cfg-1", security_scheme="key_value_creds", environment="draft")
    ]
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(
        user_id="user-1",
        db=object(),
        params=ConfigListParams(deployment_ids=["dep-1"]),
    )
    assert len(result.configs) == 1
    assert result.configs[0].id == "conn-1"
    assert result.configs[0].name == "cfg-1"
    assert result.configs[0].provider_data == {"type": "key_value_creds", "environment": "draft"}


@pytest.mark.anyio
async def test_list_configs_deployment_scope_warns_when_referenced_connection_missing(monkeypatch, caplog):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "name": "tool-one",
                "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}},
            }
        ]
    )
    connections_client = FakeConnectionsClient()
    connections_client._draft_entries_by_id = []
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    import logging

    with caplog.at_level(logging.WARNING):
        result = await service.list_configs(
            user_id="user-1",
            db=object(),
            params=ConfigListParams(deployment_ids=["dep-1"]),
        )
    assert result.configs == []
    assert "connection IDs not returned by provider" in caplog.text
    assert "conn-1" in caplog.text


@pytest.mark.anyio
async def test_list_configs_tenant_scope_raises_on_provider_list_failure(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()

    def list_raises():
        msg = "provider list failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(connections_client, "list", list_raises)
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError, match="listing deployment configs"):
        await service.list_configs(user_id="user-1", db=object(), params=None)


@pytest.mark.anyio
async def test_list_configs_tenant_scope_handles_none_response(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._list_entries = None
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(user_id="user-1", db=object(), params=None)
    assert result.configs == []
    assert result.provider_result == {}


@pytest.mark.anyio
async def test_list_configs_deployment_scope_raises_on_agent_fetch_failure(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    def get_draft_by_id_raises(deployment_id):  # noqa: ARG001
        msg = "provider agent fetch failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(fake_agent, "get_draft_by_id", get_draft_by_id_raises)

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError, match="listing deployment configs"):
        await service.list_configs(
            user_id="user-1",
            db=object(),
            params=ConfigListParams(deployment_ids=["dep-1"]),
        )


@pytest.mark.anyio
async def test_list_configs_deployment_scope_raises_when_agent_not_found(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(None),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentNotFoundError, match="Deployment 'dep-1' not found"):
        await service.list_configs(
            user_id="user-1",
            db=object(),
            params=ConfigListParams(deployment_ids=["dep-1"]),
        )


@pytest.mark.anyio
async def test_list_configs_deployment_scope_raises_on_non_dict_agent_payload(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(["dep-1"]),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(InvalidContentError, match="unexpected deployment payload type"):
        await service.list_configs(
            user_id="user-1",
            db=object(),
            params=ConfigListParams(deployment_ids=["dep-1"]),
        )


@pytest.mark.anyio
async def test_list_configs_deployment_scope_trusts_non_list_tools_payload(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._draft_entries_by_id = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-1",
                "app_id": "cfg-1",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        )
    ]
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ("tool-1",)}),
        tool=FakeToolClient(
            [
                {
                    "id": "tool-1",
                    "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}},
                }
            ]
        ),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(
        user_id="user-1",
        db=object(),
        params=ConfigListParams(deployment_ids=["dep-1"]),
    )
    assert [config.id for config in result.configs] == ["conn-1"]
    assert [config.name for config in result.configs] == ["cfg-1"]


@pytest.mark.anyio
async def test_list_configs_deployment_scope_returns_early_when_no_tools(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(
        user_id="user-1",
        db=object(),
        params=ConfigListParams(deployment_ids=["dep-1"]),
    )
    assert result.configs == []
    assert result.provider_result == {"deployment_id": "dep-1", "tool_ids": []}


@pytest.mark.anyio
async def test_list_configs_deployment_scope_handles_none_tools_payload(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": None}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(
        user_id="user-1",
        db=object(),
        params=ConfigListParams(deployment_ids=["dep-1"]),
    )
    assert result.configs == []
    assert result.provider_result == {"deployment_id": "dep-1", "tool_ids": []}


@pytest.mark.anyio
async def test_list_configs_deployment_scope_raises_on_tool_fetch_failure(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_tool = FakeToolClient([])

    def get_drafts_by_ids_raises(tool_ids):  # noqa: ARG001
        msg = "provider tool fetch failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(fake_tool, "get_drafts_by_ids", get_drafts_by_ids_raises)
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=fake_tool,
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError, match="listing deployment configs"):
        await service.list_configs(
            user_id="user-1",
            db=object(),
            params=ConfigListParams(deployment_ids=["dep-1"]),
        )


@pytest.mark.anyio
async def test_list_configs_deployment_scope_uses_latest_binding_for_same_app(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._draft_entries_by_id = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-2",
                "app_id": "cfg-1",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        )
    ]
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1", "tool-2"]}),
        tool=FakeToolClient(
            [
                {"id": "tool-1", "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}}},
                {"id": "tool-2", "binding": {"langflow": {"connections": {"cfg-1": "conn-2"}}}},
            ]
        ),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(
        user_id="user-1",
        db=object(),
        params=ConfigListParams(deployment_ids=["dep-1"]),
    )
    assert len(result.configs) == 1
    assert result.configs[0].id == "conn-2"
    assert result.configs[0].name == "cfg-1"


@pytest.mark.anyio
async def test_list_configs_deployment_scope_skips_enrichment_when_no_connections(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_tool = FakeToolClient([{"id": "tool-1", "name": "tool-without-connections"}])
    connections_client = FakeConnectionsClient()

    def fail_if_called(conn_ids):  # noqa: ARG001
        msg = "connection enrichment should not be called"
        raise AssertionError(msg)

    monkeypatch.setattr(connections_client, "get_drafts_by_ids", fail_if_called)
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=fake_tool,
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(
        user_id="user-1",
        db=object(),
        params=ConfigListParams(deployment_ids=["dep-1"]),
    )
    assert result.configs == []


@pytest.mark.anyio
async def test_list_configs_deployment_scope_raises_on_malformed_detailed_connection(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_tool = FakeToolClient([{"id": "tool-1", "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}}}])
    connections_client = FakeConnectionsClient()
    monkeypatch.setattr(
        connections_client,
        "get_drafts_by_ids",
        lambda conn_ids: [SimpleNamespace(security_scheme="key_value_creds")],  # noqa: ARG005
    )
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=fake_tool,
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(AttributeError):
        await service.list_configs(
            user_id="user-1",
            db=object(),
            params=ConfigListParams(deployment_ids=["dep-1"]),
        )


@pytest.mark.anyio
async def test_list_configs_scopes_return_same_normalized_item_shape(monkeypatch):
    """Tenant-scope and deployment-scope must return the same ConfigListItem shape."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._list_entries = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-1",
                "app_id": "cfg-1",
                "name": "Config One",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        )
    ]
    connections_client._draft_entries_by_id = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-1",
                "app_id": "cfg-1",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        )
    ]
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient(
            [
                {
                    "id": "tool-1",
                    "name": "Tool One",
                    "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}},
                }
            ]
        ),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    tenant_result = await service.list_configs(user_id="user-1", db=object(), params=None)
    deployment_result = await service.list_configs(
        user_id="user-1",
        db=object(),
        params=ConfigListParams(deployment_ids=["dep-1"]),
    )

    expected = {"id": "conn-1", "name": "cfg-1", "provider_data": {"type": "key_value_creds", "environment": "draft"}}
    assert len(tenant_result.configs) == 1
    assert len(deployment_result.configs) == 1
    assert tenant_result.configs[0].model_dump(exclude_none=True) == expected
    assert deployment_result.configs[0].model_dump(exclude_none=True) == expected


@pytest.mark.anyio
async def test_list_snapshots_single_deployment_scope(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1", "tool-2"]}),
        tool=FakeToolClient(
            [
                {"id": "tool-1", "name": "Tool One"},
                {"id": "tool-2", "name": "Tool Two"},
            ]
        ),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_snapshots(
        user_id="user-1",
        db=object(),
        params=SnapshotListParams(deployment_ids=["dep-1"]),
    )

    assert [snapshot.id for snapshot in result.snapshots] == ["tool-1", "tool-2"]
    assert [snapshot.name for snapshot in result.snapshots] == ["Tool One", "Tool Two"]


@pytest.mark.anyio
async def test_list_snapshots_stale_tool_ids_returns_empty(monkeypatch):
    """When the agent references tool IDs that no longer exist, return no snapshots."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["deleted-tool-1", "deleted-tool-2"]}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_snapshots(
        user_id="user-1",
        db=object(),
        params=SnapshotListParams(deployment_ids=["dep-1"]),
    )

    assert result.snapshots == []


@pytest.mark.anyio
async def test_list_snapshots_partial_resolution_logs_stale_ids(monkeypatch, caplog):
    """When some tool IDs resolve and others don't, return only resolved ones and log the stale IDs."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1", "deleted-tool"]}),
        tool=FakeToolClient([{"id": "tool-1", "name": "Tool One"}]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    import logging

    with caplog.at_level(logging.WARNING):
        result = await service.list_snapshots(
            user_id="user-1",
            db=object(),
            params=SnapshotListParams(deployment_ids=["dep-1"]),
        )

    assert [snapshot.id for snapshot in result.snapshots] == ["tool-1"]
    assert "deleted-tool" in caplog.text
    assert "dep-1" in caplog.text


@pytest.mark.anyio
async def test_list_snapshots_single_deployment_scope_extracts_connections(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient(
            [
                {
                    "id": "tool-1",
                    "name": "Tool One",
                    "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}},
                }
            ]
        ),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_snapshots(
        user_id="user-1",
        db=object(),
        params=SnapshotListParams(deployment_ids=["dep-1"]),
    )

    assert [snapshot.id for snapshot in result.snapshots] == ["tool-1"]
    assert result.snapshots[0].provider_data == {"connections": {"cfg-1": "conn-1"}}


@pytest.mark.anyio
async def test_list_configs_without_deployment_id_lists_tenant_scope(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._list_entries = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-1",
                "app_id": "cfg-1",
                "name": "Config One",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        ),
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-2",
                "app_id": "cfg-2",
                "name": "Config Two",
                "security_scheme": "key_value_creds",
                "environment": "live",
            }
        ),
    ]
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(user_id="user-1", db=object(), params=None)
    assert [config.id for config in result.configs] == ["conn-1"]
    assert [config.name for config in result.configs] == ["cfg-1"]
    assert result.provider_result == {}


@pytest.mark.anyio
async def test_list_configs_tenant_scope_handles_sdk_models(monkeypatch):
    """SDK ConnectionsClient.list() returns ListConfigsResponse objects."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._list_entries = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-pydantic-1",
                "app_id": "cfg-pydantic-1",
                "name": "Pydantic One",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        ),
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-pydantic-2",
                "app_id": "cfg-pydantic-2",
                "name": "Pydantic Two",
                "security_scheme": "key_value_creds",
                "environment": "live",
            }
        ),
    ]
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(user_id="user-1", db=object(), params=None)
    assert [config.id for config in result.configs] == ["conn-pydantic-1"]
    assert [config.name for config in result.configs] == ["cfg-pydantic-1"]
    assert result.provider_result == {}


@pytest.mark.anyio
async def test_list_configs_tenant_scope_filters_to_key_value_creds(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._list_entries = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-oauth",
                "app_id": "cfg-oauth",
                "name": "Oauth Config",
                "security_scheme": "oauth2",
            }
        ),
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-auth",
                "app_id": "cfg-auth",
                "name": "Auth Config",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        ),
    ]
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(user_id="user-1", db=object(), params=None)
    assert len(result.configs) == 1
    assert result.configs[0].id == "conn-auth"
    assert result.configs[0].name == "cfg-auth"
    assert result.configs[0].provider_data == {"type": "key_value_creds", "environment": "draft"}


@pytest.mark.anyio
async def test_list_configs_tenant_scope_fails_fast_on_dict_entries(monkeypatch):
    """Tenant-scope list_configs raises when wxO returns unexpected entry types."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._list_entries = [
        {"connection_id": "dict-conn", "app_id": "dict-cfg", "name": "Dict Config"},
        ListConfigsResponse.model_validate({"connection_id": "model-conn", "app_id": "model-cfg", "name": "Model"}),
    ]
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(InvalidContentError, match="unexpected connection entry type: dict"):
        await service.list_configs(user_id="user-1", db=object(), params=None)


@pytest.mark.anyio
async def test_list_configs_tenant_scope_preserves_duplicates(monkeypatch):
    """Tenant-scope list_configs keeps duplicate wxO entries as returned."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._list_entries = [
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-dup",
                "app_id": "cfg-dup",
                "name": "First",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        ),
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-dup",
                "app_id": "cfg-dup",
                "name": "Second",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        ),
        ListConfigsResponse.model_validate(
            {
                "connection_id": "conn-unique",
                "app_id": "cfg-unique",
                "name": "Unique",
                "security_scheme": "key_value_creds",
                "environment": "draft",
            }
        ),
    ]
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_configs(user_id="user-1", db=object(), params=None)
    assert [config.id for config in result.configs] == ["conn-dup", "conn-dup", "conn-unique"]
    assert [config.name for config in result.configs] == ["cfg-dup", "cfg-dup", "cfg-unique"]


@pytest.mark.anyio
async def test_list_configs_tenant_scope_fails_fast_on_non_sdk_entries(monkeypatch):
    """Tenant-scope list_configs raises on the first non-SDK entry."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    connections_client = FakeConnectionsClient()
    connections_client._list_entries = [
        "just-a-string",
        42,
        {"connection_id": "dict-conn", "app_id": "dict-cfg"},
        ListConfigsResponse.model_validate({"connection_id": "valid-conn", "app_id": "valid-cfg", "name": "Valid"}),
        ListConfigsResponse.model_validate({"connection_id": "", "app_id": "missing-connection-id"}),
        ListConfigsResponse.model_validate({"connection_id": "missing-app-id", "app_id": ""}),
    ]
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=connections_client,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(InvalidContentError, match="unexpected connection entry type: str"):
        await service.list_configs(user_id="user-1", db=object(), params=None)


@pytest.mark.anyio
async def test_list_snapshots_without_deployment_id_lists_tenant_scope(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_base = FakeBaseClient(
        get_payloads={
            "/tools": [
                {"id": "tool-1", "name": "Tool One", "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}}},
                {"id": "tool-2"},
            ]
        }
    )
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_base,
            agent=FakeAgentClient({"id": "dep-1", "tools": []}),
            tool=FakeToolClient([]),
            connections=FakeConnectionsClient(),
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_snapshots(user_id="user-1", db=object(), params=None)
    assert [snapshot.id for snapshot in result.snapshots] == ["tool-1", "tool-2"]
    assert result.snapshots[0].provider_data == {"connections": {"cfg-1": "conn-1"}}
    assert result.snapshots[1].provider_data == {"connections": {}}
    assert result.provider_result == {}


@pytest.mark.anyio
async def test_list_snapshots_snapshot_ids_returns_verified_provider_data(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_verify_tools_by_ids(clients, snapshot_ids):  # noqa: ARG001
        return SnapshotListResult(
            snapshots=[
                SnapshotItem(
                    id="tool-1",
                    name="Tool One",
                    provider_data={"connections": {"cfg-1": "conn-1"}},
                )
            ]
        )

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(service_module, "verify_tools_by_ids", mock_verify_tools_by_ids)

    result = await service.list_snapshots(
        user_id="user-1",
        db=object(),
        params=SnapshotListParams(snapshot_ids=["tool-1"]),
    )

    assert [snapshot.id for snapshot in result.snapshots] == ["tool-1"]
    assert result.snapshots[0].provider_data == {"connections": {"cfg-1": "conn-1"}}


@pytest.mark.anyio
async def test_list_snapshots_snapshot_ids_trusts_verified_results_without_revalidation(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    async def mock_verify_tools_by_ids(clients, snapshot_ids):  # noqa: ARG001
        return SnapshotListResult(
            snapshots=[
                SnapshotItem(
                    id="tool-1",
                    name="Tool One",
                    provider_data={"unexpected": "value"},
                )
            ]
        )

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(service_module, "verify_tools_by_ids", mock_verify_tools_by_ids)

    result = await service.list_snapshots(
        user_id="user-1",
        db=object(),
        params=SnapshotListParams(snapshot_ids=["tool-1"]),
    )

    assert result.snapshots[0].provider_data == {"unexpected": "value"}


def test_snapshot_list_params_snapshot_names_strips_whitespace():
    params = SnapshotListParams(snapshot_names=["  my_tool  ", "other "])
    assert params.snapshot_names == ["my_tool", "other"]


def test_snapshot_list_params_snapshot_names_rejects_empty_strings():
    with pytest.raises(ValidationError):
        SnapshotListParams(snapshot_names=[""])


def test_snapshot_list_params_snapshot_names_rejects_whitespace_only():
    with pytest.raises(ValidationError):
        SnapshotListParams(snapshot_names=["  "])


def test_snapshot_list_params_snapshot_names_rejects_empty_list():
    with pytest.raises(ValidationError):
        SnapshotListParams(snapshot_names=[])


def test_snapshot_list_params_snapshot_names_none_is_valid():
    params = SnapshotListParams(snapshot_names=None)
    assert params.snapshot_names is None


@pytest.mark.anyio
async def test_list_snapshots_snapshot_names_returns_matching_tools(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient(
            [
                {"id": "tool-1", "name": "my_tool", "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}}},
                {"id": "tool-2", "name": "other_tool"},
            ]
        ),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_snapshots(
        user_id="user-1",
        db=object(),
        params=SnapshotListParams(snapshot_names=["my_tool"]),
    )

    assert len(result.snapshots) == 1
    assert result.snapshots[0].id == "tool-1"
    assert result.snapshots[0].name == "my_tool"
    assert result.snapshots[0].provider_data == {"connections": {"cfg-1": "conn-1"}}


@pytest.mark.anyio
async def test_list_snapshots_snapshot_names_returns_empty_when_no_match(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient(
            [
                {"id": "tool-1", "name": "existing_tool"},
            ]
        ),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_snapshots(
        user_id="user-1",
        db=object(),
        params=SnapshotListParams(snapshot_names=["nonexistent_tool"]),
    )

    assert len(result.snapshots) == 0


@pytest.mark.anyio
async def test_list_snapshots_snapshot_names_ignored_when_deployment_ids_present(monkeypatch):
    """When deployment_ids present, snapshot_names should be ignored and deployment-scoped path used."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient(
            [
                {"id": "tool-1", "name": "agent_tool", "binding": {"langflow": {"connections": {}}}},
                {"id": "tool-2", "name": "my_tool"},
            ]
        ),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_snapshots(
        user_id="user-1",
        db=object(),
        params=SnapshotListParams(deployment_ids=["dep-1"], snapshot_names=["my_tool"]),
    )

    # Should return agent's tools (deployment-scoped), not name-filtered results
    assert len(result.snapshots) == 1
    assert result.snapshots[0].id == "tool-1"
    assert result.snapshots[0].name == "agent_tool"


@pytest.mark.anyio
async def test_list_snapshots_snapshot_names_wraps_provider_error(monkeypatch):
    """get_drafts_by_names failure is wrapped via raise_as_deployment_error."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_tool = FakeToolClient([])

    def get_drafts_by_names_raises(names):  # noqa: ARG001
        msg = "provider timeout"
        raise RuntimeError(msg)

    monkeypatch.setattr(fake_tool, "get_drafts_by_names", get_drafts_by_names_raises)

    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=fake_tool,
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError, match="listing"):
        await service.list_snapshots(
            user_id="user-1",
            db=object(),
            params=SnapshotListParams(snapshot_names=["my_tool"]),
        )


@pytest.mark.anyio
async def test_verify_tools_by_ids_returns_only_connections_provider_data():
    fake_clients = SimpleNamespace(
        tool=FakeToolClient(
            [
                {
                    "id": "tool-1",
                    "name": "Tool One",
                    "binding": {"langflow": {"connections": {"cfg-1": "conn-1"}}},
                    "extra": "ignored",
                },
                {
                    "id": "tool-2",
                    "name": "Tool Two",
                    "binding": {"langflow": {"connections": {}}},
                    "extra": "ignored",
                },
            ]
        )
    )

    result = await tools_module.verify_tools_by_ids(fake_clients, ["tool-1", "tool-2"])

    assert [snapshot.id for snapshot in result.snapshots] == ["tool-1", "tool-2"]
    assert result.snapshots[0].provider_data == {"connections": {"cfg-1": "conn-1"}}
    assert result.snapshots[1].provider_data == {"connections": {}}


@pytest.mark.anyio
async def test_verify_tools_by_ids_tolerates_malformed_connections_payload():
    fake_clients = SimpleNamespace(
        tool=FakeToolClient(
            [
                {
                    "id": "tool-1",
                    "name": "Tool One",
                    "binding": {"langflow": {"connections": ["not-a-dict"]}},
                }
            ]
        )
    )

    result = await tools_module.verify_tools_by_ids(fake_clients, ["tool-1"])

    assert len(result.snapshots) == 1
    assert result.snapshots[0].id == "tool-1"
    assert result.snapshots[0].provider_data == {"connections": {}}


@pytest.mark.anyio
async def test_verify_tools_by_ids_tolerates_malformed_connection_values():
    fake_clients = SimpleNamespace(
        tool=FakeToolClient(
            [
                {
                    "id": "tool-1",
                    "name": "Tool One",
                    "binding": {"langflow": {"connections": {"cfg-1": "   "}}},
                }
            ]
        )
    )

    result = await tools_module.verify_tools_by_ids(fake_clients, ["tool-1"])

    assert len(result.snapshots) == 1
    assert result.snapshots[0].id == "tool-1"
    assert result.snapshots[0].provider_data == {"connections": {}}


@pytest.mark.anyio
async def test_verify_tools_by_ids_rejects_mixed_connections_payload():
    fake_clients = SimpleNamespace(
        tool=FakeToolClient(
            [
                {
                    "id": "tool-1",
                    "name": "Tool One",
                    "binding": {
                        "langflow": {
                            "connections": {
                                "cfg-1": "conn-1",
                                "cfg-2": "   ",
                                "   ": "conn-3",
                                "cfg-4": 123,
                            }
                        }
                    },
                }
            ]
        )
    )

    result = await tools_module.verify_tools_by_ids(fake_clients, ["tool-1"])

    assert len(result.snapshots) == 1
    assert result.snapshots[0].id == "tool-1"
    assert result.snapshots[0].provider_data == {"connections": {}}


# ---------------------------------------------------------------------------
# Retry / backoff tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_retry_with_backoff_succeeds_on_first_try():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import retry_with_backoff

    call_count = 0

    async def op():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await retry_with_backoff(op, max_attempts=3)
    assert result == "ok"
    assert call_count == 1


@pytest.mark.anyio
async def test_retry_with_backoff_forwards_args_and_kwargs():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import retry_with_backoff

    received: list[tuple[str, str]] = []

    async def op(prefix: str, *, suffix: str) -> str:
        received.append((prefix, suffix))
        return f"{prefix}-{suffix}"

    result = await retry_with_backoff(op, 3, "left", suffix="right")
    assert result == "left-right"
    assert received == [("left", "right")]


@pytest.mark.anyio
async def test_retry_create_with_to_thread_forwards_kwargs():
    import asyncio

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import retry_create

    def sync_add(a: int, *, b: int) -> int:
        return a + b

    result = await retry_create(asyncio.to_thread, sync_add, 2, b=5)
    assert result == 7


@pytest.mark.anyio
async def test_retry_with_backoff_retries_then_succeeds():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import retry_with_backoff

    call_count = 0

    async def op():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            msg = "transient"
            raise RuntimeError(msg)
        return "ok"

    result = await retry_with_backoff(op, max_attempts=3)
    assert result == "ok"
    assert call_count == 3


@pytest.mark.anyio
async def test_retry_with_backoff_gives_up_after_max_attempts():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import retry_with_backoff

    call_count = 0

    async def op():
        nonlocal call_count
        call_count += 1
        msg = "always fails"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="always fails"):
        await retry_with_backoff(op, max_attempts=3)
    assert call_count == 3


@pytest.mark.anyio
async def test_retry_with_backoff_respects_should_retry_predicate():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import retry_with_backoff

    call_count = 0

    async def op():
        nonlocal call_count
        call_count += 1
        msg = "non-retryable"
        raise ValueError(msg)

    with pytest.raises(ValueError, match="non-retryable"):
        await retry_with_backoff(
            op,
            max_attempts=5,
            should_retry=lambda exc: not isinstance(exc, ValueError),
        )
    assert call_count == 1


def test_is_retryable_create_exception_non_retryable_status_codes():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import is_retryable_create_exception

    non_retryable = {400, 401, 403, 404, 409, 422}
    for code in non_retryable:
        exc = HTTPException(status_code=code)
        assert is_retryable_create_exception(exc) is False, f"status {code} should not be retryable"


def test_is_retryable_create_exception_retryable_status_codes():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import is_retryable_create_exception

    for code in (500, 502, 503, 429):
        exc = HTTPException(status_code=code)
        assert is_retryable_create_exception(exc) is True, f"status {code} should be retryable"


def test_is_retryable_create_exception_domain_exceptions_not_retryable():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import is_retryable_create_exception

    assert is_retryable_create_exception(ResourceConflictError()) is False
    assert is_retryable_create_exception(InvalidContentError()) is False
    assert is_retryable_create_exception(InvalidDeploymentOperationError()) is False


def test_is_retryable_create_exception_generic_exception_is_retryable():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import is_retryable_create_exception

    assert is_retryable_create_exception(RuntimeError("boom")) is True


@pytest.mark.anyio
async def test_rollback_created_resources_deletes_all(monkeypatch):
    from langflow.services.adapters.deployment.watsonx_orchestrate.core import retry as retry_module

    deleted = {"agents": [], "tools": [], "configs": []}

    async def fake_delete_agent(clients, *, agent_id):  # noqa: ARG001
        deleted["agents"].append(agent_id)

    async def fake_delete_tool(clients, *, tool_id):  # noqa: ARG001
        deleted["tools"].append(tool_id)

    async def fake_delete_config(clients, *, app_id):  # noqa: ARG001
        deleted["configs"].append(app_id)

    monkeypatch.setattr(retry_module, "delete_agent_if_exists", fake_delete_agent)
    monkeypatch.setattr(retry_module, "delete_tool_if_exists", fake_delete_tool)
    monkeypatch.setattr(retry_module, "delete_config_if_exists", fake_delete_config)

    fake_clients = SimpleNamespace()
    await retry_module.rollback_created_resources(
        clients=fake_clients,
        agent_id="agent-1",
        tool_ids=["tool-1", "tool-2"],
        app_ids=["app-1"],
    )

    assert deleted["agents"] == ["agent-1"]
    assert deleted["tools"] == ["tool-2", "tool-1"]
    assert deleted["configs"] == ["app-1"]


@pytest.mark.anyio
async def test_rollback_continues_after_individual_failures(monkeypatch):
    from langflow.services.adapters.deployment.watsonx_orchestrate.core import retry as retry_module

    deleted = {"configs": []}

    async def fail_delete_agent(clients, *, agent_id):  # noqa: ARG001
        msg = "agent delete failed"
        raise RuntimeError(msg)

    async def fail_delete_tool(clients, *, tool_id):  # noqa: ARG001
        msg = "tool delete failed"
        raise RuntimeError(msg)

    async def fake_delete_config(clients, *, app_id):  # noqa: ARG001
        deleted["configs"].append(app_id)

    monkeypatch.setattr(retry_module, "delete_agent_if_exists", fail_delete_agent)
    monkeypatch.setattr(retry_module, "delete_tool_if_exists", fail_delete_tool)
    monkeypatch.setattr(retry_module, "delete_config_if_exists", fake_delete_config)
    monkeypatch.setattr(retry_module, "ROLLBACK_MAX_RETRIES", 1)

    fake_clients = SimpleNamespace()
    await retry_module.rollback_created_resources(
        clients=fake_clients,
        agent_id="agent-1",
        tool_ids=["tool-1"],
        app_ids=["app-1"],
    )

    assert deleted["configs"] == ["app-1"]


@pytest.mark.anyio
async def test_rollback_update_resources_restores_then_deletes(monkeypatch):
    from langflow.services.adapters.deployment.watsonx_orchestrate.core import retry as retry_module

    restored: list[tuple[str, dict]] = []
    deleted = {"tools": [], "configs": []}

    fake_clients = SimpleNamespace(
        tool=SimpleNamespace(update=lambda tool_id, payload: restored.append((tool_id, payload))),
    )

    async def fake_delete_tool(clients, *, tool_id):  # noqa: ARG001
        deleted["tools"].append(tool_id)

    async def fake_delete_config(clients, *, app_id):  # noqa: ARG001
        deleted["configs"].append(app_id)

    monkeypatch.setattr(retry_module, "delete_tool_if_exists", fake_delete_tool)
    monkeypatch.setattr(retry_module, "delete_config_if_exists", fake_delete_config)

    await retry_module.rollback_update_resources(
        clients=fake_clients,
        created_tool_ids=["tool-new-1", "tool-new-2"],
        created_app_id="cfg-new",
        original_tools={
            "tool-old-1": {"name": "t1"},
            "tool-old-2": {"name": "t2"},
        },
    )

    assert [tool_id for tool_id, _payload in restored] == ["tool-old-2", "tool-old-1"]
    assert deleted["tools"] == ["tool-new-2", "tool-new-1"]
    assert deleted["configs"] == ["cfg-new"]


# ---------------------------------------------------------------------------
# Service method tests: get, delete, get_status, update happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_deployment_returns_agent(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(
            {"id": "dep-1", "name": "my_agent", "description": "desc"},
        ),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.get(user_id="user-1", deployment_id="dep-1", db=object())
    assert result.id == "dep-1"
    assert result.name == "my_agent"


@pytest.mark.anyio
async def test_get_deployment_not_found_raises(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(None),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentNotFoundError, match="not found"):
        await service.get(user_id="user-1", deployment_id="dep-1", db=object())


@pytest.mark.anyio
async def test_get_deployment_handles_client_api_exception(monkeypatch):
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    class FailingAgentClient(FakeAgentClient):
        def get_draft_by_id(self, deployment_id: str):  # noqa: ARG002
            resp = SimpleNamespace(status_code=500, text='{"detail": "internal error"}')
            raise ClientAPIException(response=resp)

    fake_clients = SimpleNamespace(
        agent=FailingAgentClient(None),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError, match="getting a deployment"):
        await service.get(user_id="user-1", deployment_id="dep-1", db=object())


@pytest.mark.anyio
async def test_delete_deployment_calls_agent_delete(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": []})
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.delete(user_id="user-1", deployment_id="dep-1", db=object())
    assert result.id == "dep-1"
    assert fake_agent.delete_calls == ["dep-1"]


@pytest.mark.anyio
async def test_delete_deployment_not_found_raises(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    class FailingAgentClient(FakeAgentClient):
        def delete(self, deployment_id: str):  # noqa: ARG002
            resp = SimpleNamespace(status_code=status.HTTP_404_NOT_FOUND, text="not found")
            from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

            raise ClientAPIException(response=resp)

    fake_clients = SimpleNamespace(
        agent=FailingAgentClient({"id": "dep-1", "tools": []}),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentNotFoundError, match="not found"):
        await service.delete(user_id="user-1", deployment_id="dep-1", db=object())


@pytest.mark.anyio
async def test_delete_only_deletes_agent_not_tools_or_configs(monkeypatch):
    """Delete only removes the agent — tools and connections are left untouched."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": ["tool-1", "tool-2"]},
    )
    fake_tool = FakeToolClient(
        [
            {
                "id": "tool-1",
                "binding": {"langflow": {"connections": {"app-1": {}}}},
            },
            {
                "id": "tool-2",
                "binding": {"langflow": {"connections": {"app-2": {}}}},
            },
        ]
    )
    fake_conn = FakeConnectionsClient()

    fake_clients = FakeWXOClients(
        agent=fake_agent,
        tool=fake_tool,
        connections=fake_conn,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.delete(user_id="user-1", deployment_id="dep-1", db=object())
    assert result.id == "dep-1"
    assert fake_agent.delete_calls == ["dep-1"]
    assert fake_tool.delete_calls == []
    assert fake_conn.delete_calls == []


@pytest.mark.anyio
async def test_get_status_connected(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(
            {"id": "dep-1", "environments": [{"name": "draft", "id": "env-1"}]},
        ),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.get_status(user_id="user-1", deployment_id="dep-1", db=object())
    assert result.id == "dep-1"
    assert result.provider_data["status"] == "connected"
    assert result.provider_data["environments"] == ["draft"]


@pytest.mark.anyio
async def test_get_status_not_found(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(None),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentNotFoundError, match="dep-1"):
        await service.get_status(user_id="user-1", deployment_id="dep-1", db=object())


@pytest.mark.anyio
async def test_update_deployment_name_and_description(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]})
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=FakeToolClient([{"id": "tool-1"}]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    update_data = DeploymentUpdate(
        spec=BaseDeploymentDataUpdate(name="new name", description="new desc"),
    )

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=update_data,
        db=object(),
    )
    assert result.id == "dep-1"
    assert len(fake_agent.update_calls) == 1
    agent_id, payload = fake_agent.update_calls[0]
    assert agent_id == "dep-1"
    assert payload["name"] == "new_name"
    assert payload["display_name"] == "new name"
    assert payload["description"] == "new desc"


@pytest.mark.anyio
async def test_update_deployment_not_found_raises(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(None),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    update_data = DeploymentUpdate(spec=BaseDeploymentDataUpdate(name="x"))

    with pytest.raises(DeploymentNotFoundError, match="not found"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=update_data,
            db=object(),
        )


@pytest.mark.anyio
async def test_list_deployments_without_params(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": []},
        listed_agents=[
            {"id": "dep-1", "name": "agent-1", "tools": [], "environments": [{"name": "draft"}]},
        ],
    )
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_agent,
            agent=fake_agent,
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list(user_id="user-1", db=object(), params=None)
    assert len(result.deployments) == 1
    assert result.deployments[0].id == "dep-1"


@pytest.mark.anyio
async def test_list_conflict_does_not_force_agent_resource_hint(monkeypatch):
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    class FailingListAgentClient(FakeAgentClient):
        def _get(self, path: str, params: dict | None = None):  # noqa: ARG002
            if path == "/agents":
                raise ClientAPIException(
                    response=SimpleNamespace(status_code=409, text='{"detail":"resource already exists"}')
                )
            return {}

    fake_agent = FailingListAgentClient({"id": "dep-1", "tools": []})
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_agent,
            agent=fake_agent,
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(ResourceConflictError) as exc_info:
        await service.list(user_id="user-1", db=object(), params=None)

    assert exc_info.value.resource is None
    assert exc_info.value.resource_name is None


@pytest.mark.anyio
async def test_list_types_returns_supported_types():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    result = await service.list_types(user_id="user-1", db=object())
    assert DeploymentType.AGENT in result.deployment_types
    assert len(result.deployment_types) == 1


@pytest.mark.anyio
async def test_list_llms_returns_normalized_model_names(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": []},
        get_payloads={
            "/models": [
                {"model_name": "granite-3.1-8b"},
                {"model_name": "granite-3.3-8b"},
                {"model_name": "granite-3.1-8b"},
            ]
        },
    )
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_agent,
            agent=fake_agent,
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.list_llms(user_id="user-1", db=object())

    assert result.provider_result == {
        "models": [
            {"model_name": "groq/openai/gpt-oss-120b"},
            {"model_name": "bedrock/openai.gpt-oss-120b-1:0"},
            {"model_name": "granite-3.1-8b"},
            {"model_name": "granite-3.3-8b"},
            {"model_name": "granite-3.1-8b"},
        ]
    }


@pytest.mark.anyio
async def test_list_llms_invalid_payload_raises_deployment_error(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": []},
        get_payloads={"/models": [{"id": "missing-model-name"}]},
    )
    fake_clients = _with_wxo_wrappers(
        SimpleNamespace(
            _base=fake_agent,
            agent=fake_agent,
        )
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError, match="listing deployment LLMs"):
        await service.list_llms(user_id="user-1", db=object())


@pytest.mark.anyio
async def test_get_status_handles_client_api_exception(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    class FailingAgentClient(FakeAgentClient):
        def get_draft_by_id(self, deployment_id: str):  # noqa: ARG002
            resp = SimpleNamespace(status_code=500, text='{"detail": "internal error"}')
            from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

            raise ClientAPIException(response=resp)

    fake_clients = SimpleNamespace(
        agent=FailingAgentClient(None),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError, match="getting a deployment health"):
        await service.get_status(user_id="user-1", deployment_id="dep-1", db=object())


@pytest.mark.anyio
async def test_update_spec_only_description_sends_update(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": []})
    fake_clients = SimpleNamespace(
        agent=fake_agent,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(spec=BaseDeploymentDataUpdate(description="only desc")),
        db=object(),
    )
    assert result.id == "dep-1"
    assert len(fake_agent.update_calls) == 1
    _, payload = fake_agent.update_calls[0]
    assert payload == {"description": "only desc"}
    assert "name" not in payload


# ---------------------------------------------------------------------------
# Client authentication tests
# ---------------------------------------------------------------------------


def test_get_authenticator_ibm_cloud():
    from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_authenticator

    auth = get_authenticator("https://api.region-foobar.cloud.ibm.com", "test-key")
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

    assert isinstance(auth, IAMAuthenticator)


def test_get_authenticator_mcsp():
    from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_authenticator

    auth = get_authenticator("https://api.wxo.ibm.com", "test-key")
    from ibm_cloud_sdk_core.authenticators import MCSPAuthenticator

    assert isinstance(auth, MCSPAuthenticator)


def test_get_authenticator_unknown_url():
    from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_authenticator
    from lfx.services.adapters.deployment.exceptions import AuthSchemeError

    with pytest.raises(AuthSchemeError, match="Could not determine"):
        get_authenticator("https://example.com", "test-key")


def test_get_authenticator_sets_http_timeout_on_iam():
    from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_authenticator

    auth = get_authenticator("https://api.region-foobar.cloud.ibm.com", "test-key")
    assert auth.token_manager.http_config == {"timeout": (10, 30)}


def test_get_authenticator_sets_http_timeout_on_mcsp():
    from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_authenticator

    auth = get_authenticator("https://api.wxo.ibm.com", "test-key")
    assert auth.token_manager.http_config == {"timeout": (10, 30)}


def test_get_authenticator_uses_default_iam_urls_when_unset(monkeypatch):
    try:
        with monkeypatch.context() as context:
            context.delenv("IBM_IAM_MCSP_DEV_URL_OVERRIDE", raising=False)
            context.delenv("IBM_IAM_DEV_URL_OVERRIDE", raising=False)
            reloaded_client_module = _reload_wxo_auth_modules()

            iam_auth = reloaded_client_module.get_authenticator("https://api.region-foobar.cloud.ibm.com", "test-key")
            mcsp_auth = reloaded_client_module.get_authenticator("https://api.wxo.ibm.com", "test-key")

            assert iam_auth.token_manager.url == "https://iam.cloud.ibm.com"
            assert mcsp_auth.token_manager.url == "https://iam.platform.saas.ibm.com"
    finally:
        _reload_wxo_auth_modules()


@pytest.mark.parametrize("env_value", ["", "   "])
def test_get_authenticator_empty_or_whitespace_env_var_falls_through_to_default(monkeypatch, env_value):
    try:
        with monkeypatch.context() as context:
            context.setenv("IBM_IAM_MCSP_DEV_URL_OVERRIDE", env_value)
            context.setenv("IBM_IAM_DEV_URL_OVERRIDE", env_value)
            reloaded_client_module = _reload_wxo_auth_modules()

            iam_auth = reloaded_client_module.get_authenticator("https://api.region-foobar.cloud.ibm.com", "test-key")
            mcsp_auth = reloaded_client_module.get_authenticator("https://api.wxo.ibm.com", "test-key")

            assert iam_auth.token_manager.url == "https://iam.cloud.ibm.com"
            assert mcsp_auth.token_manager.url == "https://iam.platform.saas.ibm.com"
    finally:
        _reload_wxo_auth_modules()


def test_get_authenticator_uses_override_iam_urls(monkeypatch):
    custom_mcsp_url = "  https://iam.platform.saas.ibm.com/custom-mcsp  "
    custom_iam_url = "  https://iam.cloud.ibm.com/custom-iam  "

    try:
        with monkeypatch.context() as context:
            context.setenv("IBM_IAM_MCSP_DEV_URL_OVERRIDE", custom_mcsp_url)
            context.setenv("IBM_IAM_DEV_URL_OVERRIDE", custom_iam_url)
            reloaded_client_module = _reload_wxo_auth_modules()

            iam_auth = reloaded_client_module.get_authenticator("https://api.region-foobar.cloud.ibm.com", "test-key")
            mcsp_auth = reloaded_client_module.get_authenticator("https://api.wxo.ibm.com", "test-key")

            assert iam_auth.token_manager.url == custom_iam_url.strip()
            assert mcsp_auth.token_manager.url == custom_mcsp_url.strip()
    finally:
        _reload_wxo_auth_modules()


@pytest.mark.anyio
async def test_get_provider_clients_uses_request_scoped_context_memoization(monkeypatch):
    resolve_calls = 0

    async def mock_resolve_wxo_client_credentials(*, user_id, db, provider_id):  # noqa: ARG001
        nonlocal resolve_calls
        resolve_calls += 1
        return WxOCredentials(
            instance_url="https://api.region-foobar.cloud.ibm.com/",
            authenticator=object(),
        )

    monkeypatch.setattr(client_module, "resolve_wxo_client_credentials", mock_resolve_wxo_client_credentials)
    client_module.clear_provider_clients_request_context()

    provider_context = deployment_context_module.DeploymentAdapterContext(provider_id=UUID(int=1))
    with deployment_context_module.DeploymentProviderIDContext.scope(provider_context):
        first = await client_module.get_provider_clients(user_id="user-1", db=object())
        second = await client_module.get_provider_clients(user_id="user-1", db=object())

    assert first is second
    assert resolve_calls == 1


@pytest.mark.anyio
async def test_get_provider_clients_rejects_mixed_provider_contexts(monkeypatch):
    resolve_calls = 0

    async def mock_resolve_wxo_client_credentials(*, user_id, db, provider_id):  # noqa: ARG001
        nonlocal resolve_calls
        resolve_calls += 1
        return WxOCredentials(
            instance_url="https://api.region-foobar.cloud.ibm.com/",
            authenticator=object(),
        )

    monkeypatch.setattr(client_module, "resolve_wxo_client_credentials", mock_resolve_wxo_client_credentials)
    client_module.clear_provider_clients_request_context()

    with deployment_context_module.DeploymentProviderIDContext.scope(
        deployment_context_module.DeploymentAdapterContext(provider_id=UUID(int=1))
    ):
        await client_module.get_provider_clients(user_id="user-1", db=object())
    with (
        deployment_context_module.DeploymentProviderIDContext.scope(
            deployment_context_module.DeploymentAdapterContext(provider_id=UUID(int=2))
        ),
        pytest.raises(CredentialResolutionError, match="different deployment provider context"),
    ):
        await client_module.get_provider_clients(user_id="user-1", db=object())

    assert resolve_calls == 1


@pytest.mark.anyio
async def test_resolve_wxo_client_credentials_reads_provider_url_from_account(monkeypatch):
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount

    provider_account = DeploymentProviderAccount(
        id=UUID("00000000-0000-0000-0000-000000000099"),
        user_id=UUID("00000000-0000-0000-0000-000000000100"),
        name="prod",
        provider_tenant_id="tenant-1",
        provider_key="watsonx-orchestrate",
        provider_url="https://api.us-south.wxo.cloud.ibm.com/instances/tenant-1",
        api_key="encrypted-api-key",  # pragma: allowlist secret
    )

    async def mock_get_provider_account_by_id(*args, **kwargs):  # noqa: ARG001
        return provider_account

    monkeypatch.setattr(client_module, "get_provider_account_by_id", mock_get_provider_account_by_id)
    monkeypatch.setattr(
        client_module.auth_utils,
        "decrypt_api_key",
        lambda _encrypted_api_key: "decrypted-api-key",  # pragma: allowlist secret
    )

    credentials = await client_module.resolve_wxo_client_credentials(
        user_id="user-1",
        db=object(),
        provider_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    assert credentials.instance_url == provider_account.provider_url
    assert credentials.authenticator is not None


def test_wxo_client_initializes_subclients_eagerly(monkeypatch):
    init_counts = {"tool": 0, "connections": 0, "agent": 0, "base": 0}

    class FakeToolClient:
        def __init__(self, base_url: str, authenticator):  # noqa: ARG002
            init_counts["tool"] += 1
            self.base_url = base_url

    class FakeConnectionsClient:
        def __init__(self, base_url: str, authenticator):  # noqa: ARG002
            init_counts["connections"] += 1
            self.base_url = base_url

    class FakeAgentClient:
        def __init__(self, base_url: str, authenticator):  # noqa: ARG002
            init_counts["agent"] += 1
            self.base_url = base_url

    class FakeBaseWXOClient:
        def __init__(self, base_url: str, authenticator):  # noqa: ARG002
            init_counts["base"] += 1
            self.base_url = base_url

    monkeypatch.setattr(types_module, "ToolClient", FakeToolClient)
    monkeypatch.setattr(types_module, "ConnectionsClient", FakeConnectionsClient)
    monkeypatch.setattr(types_module, "AgentClient", FakeAgentClient)
    monkeypatch.setattr(types_module, "BaseWXOClient", FakeBaseWXOClient)

    wxo_client = types_module.WxOClient(
        instance_url="https://api.region-foobar.cloud.ibm.com",
        authenticator=object(),
    )
    # All sub-clients should be created eagerly at construction
    assert init_counts == {"tool": 1, "connections": 1, "agent": 1, "base": 1}

    # Subsequent access does not re-create
    _ = wxo_client.agent
    assert init_counts["agent"] == 1


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


def test_normalize_wxo_name():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import normalize_wxo_name

    assert normalize_wxo_name("Hello World!") == "Hello_World"
    assert normalize_wxo_name("test-name-123") == "test_name_123"
    assert normalize_wxo_name("  spaces  ") == "__spaces__"
    assert normalize_wxo_name("") == ""


def test_validate_wxo_name_valid():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import validate_wxo_name

    assert validate_wxo_name("my_deployment") == "my_deployment"
    assert validate_wxo_name("My Deployment!") == "My_Deployment"


def test_validate_wxo_name_empty():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import validate_wxo_name

    with pytest.raises(InvalidContentError, match="alphanumeric"):
        validate_wxo_name("!!!")


def test_validate_wxo_name_starts_with_digit():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import validate_wxo_name

    with pytest.raises(InvalidContentError, match="start with a letter"):
        validate_wxo_name("123abc")


@pytest.mark.anyio
async def test_create_and_upload_wxo_flow_tools_with_bindings_journals_created_ids_on_upload_failure(monkeypatch):
    created_calls: list[dict] = []

    def mock_create_tool(payload: dict):
        created_calls.append(payload)
        return {"id": f"tool-{len(created_calls)}"}

    def mock_upload_tool_artifact(tool_id: str, files: dict):  # noqa: ARG001
        if tool_id == "tool-1":
            raise InvalidContentError(message="artifact upload failed")
        return {"status": "ok"}

    fake_clients = SimpleNamespace(
        tool=SimpleNamespace(create=mock_create_tool),
        upload_tool_artifact=mock_upload_tool_artifact,
    )

    def _mock_create_wxo_flow_tool(*, flow_payload, connections):  # noqa: ARG001
        return (
            {"name": flow_payload.name, "description": flow_payload.description},
            b"artifact",
        )

    monkeypatch.setattr(tools_module, "create_wxo_flow_tool", _mock_create_wxo_flow_tool)

    bindings = [
        tools_module.FlowToolBindingSpec(
            flow_payload=BaseFlowArtifact(
                id=UUID("00000000-0000-0000-0000-000000000031"),
                name="snapshot-one",
                description="desc",
                data={"nodes": [], "edges": []},
                tags=[],
                provider_data={"project_id": "project-1", "source_ref": "fv-binding-1"},
            ),
            connections={"cfg-1": "conn-1"},
        ),
        tools_module.FlowToolBindingSpec(
            flow_payload=BaseFlowArtifact(
                id=UUID("00000000-0000-0000-0000-000000000032"),
                name="snapshot-two",
                description="desc",
                data={"nodes": [], "edges": []},
                tags=[],
                provider_data={"project_id": "project-1", "source_ref": "fv-binding-2"},
            ),
            connections={"cfg-1": "conn-1"},
        ),
    ]

    with pytest.raises(tools_module.ToolUploadBatchError) as exc:
        await tools_module.create_and_upload_wxo_flow_tools_with_bindings(
            clients=fake_clients,
            tool_bindings=bindings,
        )

    assert set(exc.value.created_tool_ids) == {"tool-1", "tool-2"}
    assert len(created_calls) == 2


@pytest.mark.anyio
async def test_upload_wxo_flow_tool_maps_tool_conflict_with_structured_resource():
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    def mock_create_tool(payload: dict):  # noqa: ARG001
        raise ClientAPIException(
            response=SimpleNamespace(
                status_code=409,
                text='{"detail":"Tool with name \'Simple_Agent\' already exists for this tenant."}',
            )
        )

    fake_clients = SimpleNamespace(
        tool=SimpleNamespace(create=mock_create_tool),
        upload_tool_artifact=lambda tool_id, files: {"id": tool_id},  # noqa: ARG005
    )

    with pytest.raises(ResourceConflictError) as exc_info:
        await tools_module.upload_wxo_flow_tool(
            clients=fake_clients,
            tool_payload={"name": "Simple_Agent"},
            artifact_bytes=b"artifact",
        )

    assert exc_info.value.resource == "tool"
    assert exc_info.value.resource_name == "Simple_Agent"


@pytest.mark.anyio
async def test_create_agent_deployment_maps_agent_conflict_with_structured_resource():
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    def mock_create_agent(payload: dict):  # noqa: ARG001
        raise ClientAPIException(
            response=SimpleNamespace(
                status_code=409,
                text='{"detail":"Agent with name \'my_agent\' already exists for this tenant."}',
            )
        )

    fake_clients = SimpleNamespace(agent=SimpleNamespace(create=mock_create_agent))

    with pytest.raises(ResourceConflictError) as exc_info:
        await create_core_module.create_agent_deployment(
            clients=fake_clients,
            tool_ids=["tool-1"],
            agent_name="my_agent",
            agent_display_name="My Agent",
            deployment_name="my deployment",
            description="desc",
            llm=TEST_WXO_LLM,
        )

    assert exc_info.value.resource == "agent"
    assert exc_info.value.resource_name == "my_agent"


def test_extract_error_detail_json_string():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_error_detail

    assert extract_error_detail('{"detail": "something went wrong"}') == "something went wrong"


def test_extract_error_detail_json_list():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_error_detail

    assert extract_error_detail('{"detail": [{"msg": "field required"}]}') == "field required"


def test_extract_error_detail_json_dict():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_error_detail

    result = extract_error_detail('{"detail": {"msg": "invalid"}}')
    assert result == "invalid"


def test_extract_error_detail_non_json():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_error_detail

    assert extract_error_detail("plain text error") == "plain text error"


def test_extract_error_detail_with_null_detail_falls_back_to_body():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_error_detail

    assert extract_error_detail('{"detail": null}') == '{"detail": null}'


def test_extract_error_detail_uses_message_field_when_detail_missing():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_error_detail

    payload = '{"statusCode":409,"message":"The connection ID already exists.","details":"duplicate"}'
    assert extract_error_detail(payload) == "The connection ID already exists."


def test_dedupe_list():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import dedupe_list

    assert dedupe_list(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert dedupe_list([]) == []


def test_raise_as_deployment_error_wraps_service_error_by_default():
    from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import raise_as_deployment_error

    original = InvalidContentError(message="invalid payload")

    with pytest.raises(DeploymentError, match="Please check server logs for details"):
        raise_as_deployment_error(
            original,
            error_prefix=ErrorPrefix.LIST,
            log_msg="unexpected list failure",
        )


def test_raise_as_deployment_error_reraises_allowed_service_error():
    from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import raise_as_deployment_error

    original = InvalidContentError(message="invalid payload")

    with pytest.raises(InvalidContentError, match="invalid payload"):
        raise_as_deployment_error(
            original,
            error_prefix=ErrorPrefix.LIST,
            log_msg="unexpected list failure",
            pass_through=(InvalidContentError,),
        )


def test_raise_as_deployment_error_client_api_falls_back_to_raw_body():
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
    from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import raise_as_deployment_error

    resp = SimpleNamespace(status_code=500, text='{"error":"boom"}')
    exc = ClientAPIException(response=resp)

    with pytest.raises(DeploymentError, match="error details: boom"):
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.LIST_CONFIGS,
            log_msg="unexpected config list failure",
        )


def test_raise_as_deployment_error_http_exception_uses_detail():
    from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import raise_as_deployment_error

    exc = HTTPException(status_code=400, detail="bad request")

    with pytest.raises(DeploymentError, match="error details: bad request"):
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.HEALTH,
            log_msg="unexpected health check failure",
        )


def test_raise_as_deployment_error_maps_not_found():
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
    from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import raise_as_deployment_error

    resp = SimpleNamespace(status_code=500, text='{"detail":"Agent \'abc\' not found"}')
    exc = ClientAPIException(response=resp)

    with pytest.raises(ResourceNotFoundError, match="not found"):
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.UPDATE,
            log_msg="unexpected update failure",
        )


def test_raise_as_deployment_error_maps_conflict():
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
    from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import raise_as_deployment_error

    resp = SimpleNamespace(status_code=500, text='{"detail":"resource already exists"}')
    exc = ClientAPIException(response=resp)

    with pytest.raises(ResourceConflictError, match="already exists"):
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.UPDATE,
            log_msg="unexpected update conflict",
            resource="agent",
            resource_name="my-agent",
        )


def test_raise_as_deployment_error_maps_unprocessable_content():
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
    from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import raise_as_deployment_error

    resp = SimpleNamespace(status_code=422, text='{"detail":"unprocessable"}')
    exc = ClientAPIException(response=resp)

    with pytest.raises(InvalidContentError, match="unprocessable"):
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.UPDATE,
            log_msg="unexpected update validation failure",
        )


def test_raise_as_deployment_error_maps_forbidden_to_authorization_error():
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
    from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import raise_as_deployment_error

    resp = SimpleNamespace(status_code=403, text='{"detail":"forbidden"}')
    exc = ClientAPIException(response=resp)

    with pytest.raises(AuthorizationError, match="forbidden"):
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.UPDATE,
            log_msg="unexpected update authorization failure",
        )


def test_build_agent_payload_from_values_structure():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import build_agent_payload_from_values

    payload = build_agent_payload_from_values(
        agent_name="agent_name",
        agent_display_name="Agent Name",
        deployment_name="test",
        description="test description",
        tool_ids=["tool-1", "tool-2"],
        llm=TEST_WXO_LLM,
    )
    assert payload["name"] == "agent_name"
    assert payload["display_name"] == "Agent Name"
    assert payload["description"] == "test description"
    assert payload["tools"] == ["tool-1", "tool-2"]
    assert payload["llm"] == TEST_WXO_LLM


def test_extract_agent_tool_ids():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_agent_tool_ids

    assert extract_agent_tool_ids({"tools": ["t1", "t2", None, ""]}) == ["t1", "t2"]
    assert extract_agent_tool_ids({}) == []


# ---------------------------------------------------------------------------
# Config helper unit tests (core/config.py standalone functions)
# ---------------------------------------------------------------------------


def test_normalize_optional_text_strips_and_returns_none_for_empty():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import normalize_optional_text

    assert normalize_optional_text(None) is None
    assert normalize_optional_text("") is None
    assert normalize_optional_text("  ") is None
    assert normalize_optional_text("hello") == "hello"
    assert normalize_optional_text("  spaced  ") == "spaced"


def test_normalize_optional_text_rejects_non_str():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import normalize_optional_text

    with pytest.raises(TypeError, match=r"expected str \| None"):
        normalize_optional_text(("value",))
    with pytest.raises(TypeError, match=r"expected str \| None"):
        normalize_optional_text(42)


def test_normalize_optional_text_handles_str_enum():
    from enum import Enum

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import normalize_optional_text

    class FakeEnum(str, Enum):
        KEY_VALUE = "key_value_creds"

    assert normalize_optional_text(FakeEnum.KEY_VALUE) == "key_value_creds"


def test_build_config_list_item_valid():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import build_config_list_item
    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import WatsonxConfigItemProviderData
    from lfx.services.adapters.payload import PayloadSlot

    slot = PayloadSlot(WatsonxConfigItemProviderData)
    item = build_config_list_item(
        config_item_data_slot=slot,
        connection_id="conn-1",
        app_id="app-1",
        config_type="key_value_creds",
        environment="draft",
    )
    assert item.id == "conn-1"
    assert item.name == "app-1"
    assert isinstance(item.provider_data, dict)
    assert item.provider_data["type"] == "key_value_creds"
    assert item.provider_data["environment"] == "draft"


def test_build_config_list_item_missing_environment_for_key_value_creds():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import build_config_list_item
    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import WatsonxConfigItemProviderData
    from lfx.services.adapters.payload import PayloadSlot

    slot = PayloadSlot(WatsonxConfigItemProviderData)
    with pytest.raises(InvalidContentError, match="key_value_creds connection without a required environment"):
        build_config_list_item(
            config_item_data_slot=slot,
            connection_id="conn-1",
            app_id="app-1",
            config_type="key_value_creds",
            environment=None,
        )


def test_build_config_list_item_invalid_payload():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import build_config_list_item
    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import WatsonxConfigItemProviderData
    from lfx.services.adapters.payload import PayloadSlot

    slot = PayloadSlot(WatsonxConfigItemProviderData)
    with pytest.raises(InvalidContentError, match="invalid config item provider_data payload"):
        build_config_list_item(
            config_item_data_slot=slot,
            connection_id="conn-1",
            app_id="app-1",
            config_type="unknown_type",
            environment=None,
        )


def test_warn_if_expected_ids_missing_logs_warning(caplog):
    import logging

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import warn_if_expected_ids_missing

    with caplog.at_level(logging.WARNING):
        warn_if_expected_ids_missing(
            deployment_id="dep-1",
            resource_name="tool",
            expected_ids=["t1", "t2", "t3"],
            resolved_ids={"t1"},
        )
    assert "t2" in caplog.text
    assert "t3" in caplog.text


def test_warn_if_expected_ids_missing_no_warning_when_all_resolved(caplog):
    import logging

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import warn_if_expected_ids_missing

    with caplog.at_level(logging.WARNING):
        warn_if_expected_ids_missing(
            deployment_id="dep-1",
            resource_name="tool",
            expected_ids=["t1", "t2"],
            resolved_ids={"t1", "t2"},
        )
    assert "list_configs" not in caplog.text


# ---------------------------------------------------------------------------
# Execution helper tests
# ---------------------------------------------------------------------------


def test_resolve_execution_message_string():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import resolve_execution_message

    result = resolve_execution_message("hello")
    assert result == {"role": "user", "content": "hello"}


def test_resolve_execution_message_dict_with_role_content():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import resolve_execution_message

    msg = {"role": "assistant", "content": "hi"}
    assert resolve_execution_message(msg) == msg


def test_resolve_execution_message_dict_with_nested_message():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import resolve_execution_message

    msg = {"message": {"role": "user", "content": "nested"}}
    assert resolve_execution_message(msg) == {"role": "user", "content": "nested"}


def test_resolve_execution_message_empty_string_raises():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import resolve_execution_message

    with pytest.raises(ValueError, match="must not be empty"):
        resolve_execution_message("   ")


def test_resolve_execution_message_none_raises():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import resolve_execution_message

    with pytest.raises(ValueError, match="requires input content"):
        resolve_execution_message(None)


def test_create_agent_run_result_empty_raises():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    with pytest.raises(DeploymentError, match="empty response"):
        create_agent_run_result(None)
    with pytest.raises(DeploymentError, match="empty response"):
        create_agent_run_result({})


def test_create_agent_run_result_with_run_id():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    result = create_agent_run_result({"status": "running", "run_id": "r-1"})
    assert result == {"status": "running", "execution_id": "r-1"}


def test_create_agent_run_result_extracts_thread_id():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    result = create_agent_run_result({"status": "running", "run_id": "r-1", "thread_id": "t-1"})
    assert result["thread_id"] == "t-1"


def test_create_agent_run_result_omits_thread_id_when_absent():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    result = create_agent_run_result({"status": "running", "run_id": "r-1"})
    assert "thread_id" not in result


# ---------------------------------------------------------------------------
# Status helper tests
# ---------------------------------------------------------------------------


def test_get_agent_environments_dedupes_preserving_order():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import get_agent_environments

    agent = {
        "environments": [
            {"name": "draft"},
            {"name": "draft"},
            {"name": "live"},
            {"name": "future-env"},
        ]
    }
    assert get_agent_environments(agent) == ["draft", "live", "future-env"]


def test_get_agent_environments_returns_empty_list_when_provider_returns_empty():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import get_agent_environments

    assert get_agent_environments({"environments": []}) == []


def test_get_agent_environments_raises_when_environments_key_missing():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import get_agent_environments

    with pytest.raises(KeyError):
        get_agent_environments({})


def test_get_agent_environments_raises_when_env_entry_missing_name():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import get_agent_environments

    with pytest.raises(KeyError):
        get_agent_environments({"environments": [{"not_name": "draft"}]})


# ---------------------------------------------------------------------------
# Artifact build tests
# ---------------------------------------------------------------------------


def test_build_langflow_artifact_bytes_structure():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
        build_langflow_artifact_bytes,
    )

    flow_definition = {"nodes": [{"id": "n1"}], "edges": []}
    tool = SimpleNamespace(
        __tool_spec__=SimpleNamespace(name="test_tool"),
        requirements=["lfx>=0.3.0"],
    )

    artifact_bytes = build_langflow_artifact_bytes(
        tool=tool,
        flow_definition=flow_definition,
    )

    assert isinstance(artifact_bytes, bytes)

    with zipfile.ZipFile(io.BytesIO(artifact_bytes), "r") as zf:
        names = zf.namelist()
        assert "test_tool.json" in names
        assert "requirements.txt" in names
        assert "bundle-format" in names


# ---------------------------------------------------------------------------
# WxOCredentials repr masking
# ---------------------------------------------------------------------------


def test_wxo_credentials_repr_does_not_expose_authenticator_data():
    class _FakeAuthenticator:
        pass

    creds = WxOCredentials(instance_url="https://example.com", authenticator=_FakeAuthenticator())
    repr_str = repr(creds)
    assert repr_str == "WxOCredentials(instance_url='https://example.com', authenticator=_FakeAuthenticator)"


# ---------------------------------------------------------------------------
# NotImplementedError stubs
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_redeploy_raises_operation_not_supported():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    with pytest.raises(OperationNotSupportedError, match="Redeployment is not supported"):
        await service.redeploy(user_id="user-1", deployment_id="dep-1", db=object())


@pytest.mark.anyio
async def test_duplicate_raises_operation_not_supported():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    with pytest.raises(OperationNotSupportedError, match="duplication is not supported"):
        await service.duplicate(user_id="user-1", deployment_id="dep-1", db=object())


@pytest.mark.anyio
async def test_teardown_succeeds():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    await service.teardown()


# ---------------------------------------------------------------------------
# Tests for review fixes
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_agent_run_empty_response_raises(monkeypatch):
    """get_agent_run raises DeploymentError when provider returns empty payload."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import get_agent_run

    async def fake_to_thread(fn, *args, **kwargs):  # noqa: ARG001
        return None

    import asyncio

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    fake_client = SimpleNamespace(get_run=lambda _run_id: None)
    with pytest.raises(DeploymentError, match="empty response"):
        await get_agent_run(fake_client, run_id="run-123")


def test_retry_rollback_uses_retryable_filter():
    """retry_rollback should use is_retryable_create_exception to skip non-retryable errors.

    Validates that the filter correctly identifies non-retryable HTTP status codes
    (via HTTPException, which is checked by is_retryable_create_exception).
    """
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import is_retryable_create_exception

    # Non-retryable status codes should not be retried
    for code in [400, 401, 403, 404, 409, 422]:
        assert not is_retryable_create_exception(HTTPException(status_code=code)), (
            f"HTTPException with status {code} should NOT be retryable"
        )

    # Retryable status codes should be retried
    for code in [500, 502, 503, 504]:
        assert is_retryable_create_exception(HTTPException(status_code=code)), (
            f"HTTPException with status {code} should be retryable"
        )

    # Domain exceptions that are non-retryable
    from lfx.services.adapters.deployment.exceptions import InvalidContentError, ResourceConflictError

    assert not is_retryable_create_exception(ResourceConflictError())
    assert not is_retryable_create_exception(InvalidContentError())

    # Generic exceptions are retryable (e.g. transient network errors)
    assert is_retryable_create_exception(RuntimeError("transient"))


@pytest.mark.anyio
async def test_credential_resolution_catches_arbitrary_exceptions(monkeypatch):
    """resolve_wxo_client_credentials wraps unexpected exceptions as CredentialResolutionError."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.client import resolve_wxo_client_credentials
    from lfx.services.adapters.deployment.exceptions import CredentialResolutionError

    class FakeSQLAlchemyError(Exception):
        pass

    async def mock_get_provider(*args, **kwargs):  # noqa: ARG001
        error_message = "connection refused"
        raise FakeSQLAlchemyError(error_message)

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.client.get_provider_account_by_id",
        mock_get_provider,
    )

    with pytest.raises(CredentialResolutionError, match="unexpected error"):
        await resolve_wxo_client_credentials(
            user_id="user-1",
            db=object(),
            provider_id=UUID("00000000-0000-0000-0000-000000000001"),
        )


def test_wxo_client_eagerly_constructs_sub_clients():
    """WxOClient eagerly builds tool/connections/agent from instance_url and authenticator."""
    types_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.types")
    wxo_client_cls = types_module.WxOClient
    from ibm_cloud_sdk_core.authenticators import NoAuthAuthenticator

    client = wxo_client_cls(instance_url="https://test.example.com", authenticator=NoAuthAuthenticator())

    # Sub-clients should be eagerly created at construction
    assert client.tool is not None
    assert client.connections is not None
    assert client.agent is not None
    assert client.base is not None


def test_wxo_client_is_frozen():
    """WxOClient is frozen and rejects post-construction mutation."""
    types_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.types")
    wxo_client_cls = types_module.WxOClient
    from ibm_cloud_sdk_core.authenticators import NoAuthAuthenticator

    client = wxo_client_cls(instance_url="https://test.example.com", authenticator=NoAuthAuthenticator())
    with pytest.raises(AttributeError):
        client.instance_url = "https://evil.example.com"


def test_wxo_client_strips_trailing_slash():
    """WxOClient normalizes instance_url by stripping trailing slashes."""
    types_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.types")
    wxo_client_cls = types_module.WxOClient
    from ibm_cloud_sdk_core.authenticators import NoAuthAuthenticator

    client = wxo_client_cls(instance_url="https://test.example.com/", authenticator=NoAuthAuthenticator())
    assert client.instance_url == "https://test.example.com"


def test_wxo_client_rejects_empty_url():
    """WxOClient rejects empty instance_url at construction."""
    types_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.types")
    wxo_client_cls = types_module.WxOClient
    from ibm_cloud_sdk_core.authenticators import NoAuthAuthenticator

    with pytest.raises(ValueError, match="non-empty"):
        wxo_client_cls(instance_url="", authenticator=NoAuthAuthenticator())


def test_wxo_credentials_is_frozen():
    """WxOCredentials is frozen and rejects post-construction mutation."""
    from ibm_cloud_sdk_core.authenticators import NoAuthAuthenticator

    creds = WxOCredentials(instance_url="https://test.example.com", authenticator=NoAuthAuthenticator())
    with pytest.raises(AttributeError):
        creds.instance_url = "https://evil.example.com"


def test_wxo_credentials_rejects_empty_url():
    """WxOCredentials rejects empty instance_url at construction."""
    from ibm_cloud_sdk_core.authenticators import NoAuthAuthenticator

    with pytest.raises(ValueError, match="non-empty"):
        WxOCredentials(instance_url="", authenticator=NoAuthAuthenticator())


def test_raise_for_status_separates_status_codes_from_string_heuristics():
    """Status code dispatch and string heuristic dispatch are now separate cascading checks.

    Previously, status_code == 404 and 'not found' in detail were combined with `or`,
    meaning ANY status code with 'not found' text would raise DeploymentNotFoundError.
    Now, the 404 status code check is standalone, and 'not found' string heuristic only
    fires as a fallback for unmapped status codes.
    """
    from lfx.services.adapters.deployment.exceptions import ResourceNotFoundError, raise_as_deployment_error

    # status_code=404 raises ResourceNotFoundError regardless of detail text
    with pytest.raises(ResourceNotFoundError):
        raise_as_deployment_error(status_code=404, detail="anything", message_prefix="test")

    # status_code=409 raises ResourceConflictError regardless of detail text
    with pytest.raises(ResourceConflictError):
        raise_as_deployment_error(status_code=409, detail="anything", message_prefix="test")

    # String heuristics still work as fallback for unmapped/None status codes
    with pytest.raises(ResourceNotFoundError):
        raise_as_deployment_error(status_code=None, detail="agent not found", message_prefix="test")
    with pytest.raises(ResourceConflictError):
        raise_as_deployment_error(status_code=None, detail="resource already exists", message_prefix="test")


# ---------------------------------------------------------------------------
# Test Coverage Gap #1: create — 409 conflict via ClientAPIException
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_maps_409_conflict_to_deployment_conflict_error():
    """Create raises ResourceConflictError when the provider agent create returns a 409."""
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    clients = FakeWXOClients(
        agent=FakeAgentClient(
            {"id": "dep-1", "tools": []},
            create_exception=ClientAPIException(
                response=SimpleNamespace(status_code=409, text='{"detail":"already exists"}')
            ),
        ),
        tool=FakeToolClient([{"id": "tool-existing-1", "binding": {"langflow": {}}}]),
        connections=FakeConnectionsClient(existing_app_id="app-existing-1"),
    )
    _attach_provider_clients(service, clients)

    with pytest.raises(ResourceConflictError, match="already exist"):
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my_deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
                provider_data=_create_provider_spec(),
            ),
        )


@pytest.mark.anyio
async def test_create_tool_conflict_detail_is_not_misclassified_as_agent(monkeypatch):
    """Service-layer catch does not carry resource hints — resource stays None.

    This proves the conflict is not misclassified as 'agent'.  The inner-layer test
    ``test_upload_wxo_flow_tool_maps_tool_conflict_with_structured_resource``
    covers the path where ``resource='tool'`` is correctly attached.
    """
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    _attach_provider_clients(service, FakeWXOClients())

    async def mock_apply_provider_create_plan_with_rollback(**kwargs):  # noqa: ARG001
        raise ClientAPIException(
            response=SimpleNamespace(
                status_code=409,
                text='{"detail":"Tool with name \'Simple_Agent\' already exists for this tenant."}',
            )
        )

    monkeypatch.setattr(
        service_module,
        "apply_provider_create_plan_with_rollback",
        mock_apply_provider_create_plan_with_rollback,
    )

    with pytest.raises(ResourceConflictError) as exc_info:
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="ahhahahaqwerg",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
                provider_data=_create_provider_spec(),
            ),
        )

    assert exc_info.value.resource is None
    assert exc_info.value.resource_name is None


@pytest.mark.anyio
async def test_create_maps_422_to_invalid_content_error():
    """Create raises InvalidContentError when the provider agent create returns a 422."""
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    clients = FakeWXOClients(
        agent=FakeAgentClient(
            {"id": "dep-1", "tools": []},
            create_exception=ClientAPIException(
                response=SimpleNamespace(status_code=422, text='{"detail":"validation error"}')
            ),
        ),
        tool=FakeToolClient([{"id": "tool-existing-1", "binding": {"langflow": {}}}]),
        connections=FakeConnectionsClient(existing_app_id="app-existing-1"),
    )
    _attach_provider_clients(service, clients)

    with pytest.raises(InvalidContentError, match="validation error"):
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my_deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
                provider_data=_create_provider_spec(),
            ),
        )


# ---------------------------------------------------------------------------
# Test Coverage Gap #2: create — unsupported deployment type rejection
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_rejects_unsupported_deployment_type(monkeypatch):
    """Create raises DeploymentSupportError for non-AGENT deployment types."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    # Simulate a deployment type that is not in SUPPORTED_ADAPTER_DEPLOYMENT_TYPES
    # by creating a spec with AGENT type but monkeypatching the check.
    spec = BaseDeploymentData(
        name="my_deployment",
        description="desc",
        type=DeploymentType.AGENT,
    )
    # Override the type to a fake unsupported value after construction
    monkeypatch.setattr(spec, "type", SimpleNamespace(value="unsupported_type"))

    with pytest.raises(DeploymentSupportError, match="not supported"):
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(spec=spec),
        )


# ---------------------------------------------------------------------------
# Test Coverage Gap #3: update — empty provider_data + no spec → InvalidContentError
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_rejects_empty_provider_data_with_no_spec_changes(monkeypatch):
    """Update raises InvalidContentError when provider_data is None and spec produces no update fields."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient([{"id": "tool-1", "binding": {}}]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    # Construct a payload that bypasses Pydantic validation to reach the guard
    payload = DeploymentUpdate.model_construct(
        spec=None,
        snapshot=None,
        config=None,
        provider_data=None,
    )

    with pytest.raises(InvalidContentError, match="provider_data is required"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=payload,
            db=object(),
        )


# ---------------------------------------------------------------------------
# Test Coverage Gap #4: extract_langflow_artifact_from_zip — all error paths
# ---------------------------------------------------------------------------


def test_extract_langflow_artifact_from_zip_success():
    """extract_langflow_artifact_from_zip returns parsed JSON from a valid zip."""
    import json

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
        extract_langflow_artifact_from_zip,
    )

    flow_data = {"name": "test_flow", "nodes": []}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("flow.json", json.dumps(flow_data))
    result = extract_langflow_artifact_from_zip(buf.getvalue(), snapshot_id="snap-1")
    assert result == flow_data


def test_extract_langflow_artifact_from_zip_no_json():
    """extract_langflow_artifact_from_zip raises InvalidContentError when no JSON in zip."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
        extract_langflow_artifact_from_zip,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "hello")
    with pytest.raises(InvalidContentError, match="does not include a flow JSON"):
        extract_langflow_artifact_from_zip(buf.getvalue(), snapshot_id="snap-1")


def test_extract_langflow_artifact_from_zip_bad_zip():
    """extract_langflow_artifact_from_zip raises InvalidContentError for invalid zip data."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
        extract_langflow_artifact_from_zip,
    )

    with pytest.raises(InvalidContentError, match="not a valid zip"):
        extract_langflow_artifact_from_zip(b"not a zip file", snapshot_id="snap-1")


def test_extract_langflow_artifact_from_zip_invalid_utf8():
    """extract_langflow_artifact_from_zip raises InvalidContentError for non-UTF-8 content."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
        extract_langflow_artifact_from_zip,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("flow.json", b"\xff\xfe invalid utf-8")
    with pytest.raises(InvalidContentError, match="not valid UTF-8"):
        extract_langflow_artifact_from_zip(buf.getvalue(), snapshot_id="snap-1")


def test_extract_langflow_artifact_from_zip_invalid_json():
    """extract_langflow_artifact_from_zip raises InvalidContentError for malformed JSON."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
        extract_langflow_artifact_from_zip,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("flow.json", "not valid json {{{")
    with pytest.raises(InvalidContentError, match="invalid JSON"):
        extract_langflow_artifact_from_zip(buf.getvalue(), snapshot_id="snap-1")


# ---------------------------------------------------------------------------
# Test Coverage Gap #5: validate_connection — all negative paths
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_validate_connection_missing_connection():
    """validate_connection raises InvalidContentError when connection not found."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection

    connections_client = FakeConnectionsClient()  # no existing connections

    with pytest.raises(InvalidContentError, match="not found"):
        await validate_connection(connections_client, app_id="missing_app")


@pytest.mark.anyio
async def test_validate_connection_missing_config(monkeypatch):
    """validate_connection raises InvalidContentError when config not found."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection

    connections_client = FakeConnectionsClient(existing_app_id="my_app")

    def get_config_none(app_id, env):  # noqa: ARG001
        return None

    monkeypatch.setattr(connections_client, "get_config", get_config_none)

    with pytest.raises(InvalidContentError, match="missing draft config"):
        await validate_connection(connections_client, app_id="my_app")


@pytest.mark.anyio
async def test_validate_connection_wrong_security_scheme(monkeypatch):
    """validate_connection raises InvalidContentError for non-key-value security scheme."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection

    connections_client = FakeConnectionsClient(existing_app_id="my_app")

    def get_config_wrong_scheme(app_id, env):  # noqa: ARG001
        return SimpleNamespace(security_scheme="oauth2")

    monkeypatch.setattr(connections_client, "get_config", get_config_wrong_scheme)

    with pytest.raises(InvalidContentError, match="key-value credentials"):
        await validate_connection(connections_client, app_id="my_app")


@pytest.mark.anyio
async def test_validate_connection_missing_credentials(monkeypatch):
    """validate_connection raises InvalidContentError when credentials are missing."""
    from ibm_watsonx_orchestrate_core.types.connections import ConnectionSecurityScheme
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection

    connections_client = FakeConnectionsClient(existing_app_id="my_app")

    def get_config_ok(app_id, env):  # noqa: ARG001
        return SimpleNamespace(security_scheme=ConnectionSecurityScheme.KEY_VALUE)

    def get_credentials_none(app_id, env, *, use_app_credentials):  # noqa: ARG001
        return None

    monkeypatch.setattr(connections_client, "get_config", get_config_ok)
    monkeypatch.setattr(connections_client, "get_credentials", get_credentials_none)

    with pytest.raises(InvalidContentError, match="missing draft runtime credentials"):
        await validate_connection(connections_client, app_id="my_app")


# ---------------------------------------------------------------------------
# Additional coverage: create_agent_run_result raises on missing run_id
# ---------------------------------------------------------------------------


def test_create_agent_run_result_raises_on_missing_run_id():
    """create_agent_run_result raises DeploymentError when response has no execution identifier."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    with pytest.raises(DeploymentError, match="did not return an execution identifier"):
        create_agent_run_result({"status": "accepted"})


def test_create_agent_run_result_extracts_run_id():
    """create_agent_run_result translates WXO run_id to execution_id."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    result = create_agent_run_result({"status": "accepted", "run_id": "run-123"})
    assert result["execution_id"] == "run-123"
    assert result["status"] == "accepted"


def test_create_agent_run_result_falls_back_to_id_field():
    """create_agent_run_result uses 'id' field when 'run_id' is absent."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    result = create_agent_run_result({"status": "running", "id": "id-456"})
    assert result["execution_id"] == "id-456"


# ---------------------------------------------------------------------------
# Additional coverage: require_single_deployment_id — multiple IDs
# ---------------------------------------------------------------------------


def test_require_single_deployment_id_rejects_multiple_ids():
    """require_single_deployment_id raises InvalidContentError for multiple IDs."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import require_single_deployment_id

    params = ConfigListParams(deployment_ids=["id-1", "id-2"])
    with pytest.raises(InvalidContentError, match="exactly one deployment_id"):
        require_single_deployment_id(params, resource_label="config")


# ---------------------------------------------------------------------------
# Additional coverage: exception chain preserved (from exc, not from None)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_preserves_exception_chain_on_unexpected_error():
    """Create preserves exception chain with 'from exc' instead of 'from None'."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    original_error = RuntimeError("unexpected db error")
    clients = FakeWXOClients(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}, create_exception=original_error),
        tool=FakeToolClient([{"id": "tool-existing-1", "binding": {"langflow": {}}}]),
        connections=FakeConnectionsClient(existing_app_id="app-existing-1"),
    )
    _attach_provider_clients(service, clients)

    with pytest.raises(DeploymentError, match="Please check server logs for details") as exc_info:
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my_deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
                provider_data=_create_provider_spec(),
            ),
        )

    inner = exc_info.value.__cause__
    assert isinstance(inner, DeploymentError)
    assert inner.__cause__ is original_error


@pytest.mark.anyio
async def test_delete_preserves_exception_chain_on_unexpected_error(monkeypatch):
    """Delete preserves exception chain with 'from exc' instead of 'from None'."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    original_error = RuntimeError("unexpected error")

    fake_agent = FakeAgentClient({"id": "dep-1", "tools": []})
    fake_agent.delete = lambda _deployment_id: (_ for _ in ()).throw(original_error)

    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError) as exc_info:
        await service.delete(
            user_id="user-1",
            deployment_id="dep-1",
            db=object(),
        )

    assert exc_info.value.__cause__ is original_error


# ---------------------------------------------------------------------------
# Additional coverage: _ensure_dict logs warning on non-dict replacement
# ---------------------------------------------------------------------------


def test_ensure_dict_logs_warning_on_non_dict():
    """_ensure_dict logs a warning when replacing a non-dict value."""
    from unittest.mock import patch

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import _ensure_dict

    parent = {"binding": "not a dict"}
    with patch("langflow.services.adapters.deployment.watsonx_orchestrate.core.tools.logger") as mock_logger:
        result = _ensure_dict(parent, "binding")
    assert result == {}
    assert parent["binding"] == {}
    mock_logger.warning.assert_called_once()
    call_args = mock_logger.warning.call_args
    assert "Expected dict" in call_args[0][0]
    assert call_args[0][2] == "str"


# ---------------------------------------------------------------------------
# get_agent_run — happy path: id → execution_id + passthrough fields
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_agent_run_translates_run_id_to_execution_id(monkeypatch):
    """get_agent_run maps WXO id to execution_id and passes through other fields."""
    import asyncio as _asyncio

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import get_agent_run

    wxo_payload = {
        "id": "r-42",
        "status": "completed",
        "agent_id": "agent-1",
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:01:00Z",
        "result": {"output": "hello"},
    }

    async def fake_to_thread(fn, *args, **kwargs):  # noqa: ARG001
        return wxo_payload

    monkeypatch.setattr(_asyncio, "to_thread", fake_to_thread)

    fake_client = SimpleNamespace(get_run=lambda _run_id: wxo_payload)
    result = await get_agent_run(fake_client, run_id="r-42")

    assert result["execution_id"] == "r-42"
    assert "run_id" not in result
    assert result["status"] == "completed"
    assert result["agent_id"] == "agent-1"
    assert result["started_at"] == "2026-01-01T00:00:00Z"
    assert result["completed_at"] == "2026-01-01T00:01:00Z"
    assert result["result"] == {"output": "hello"}


@pytest.mark.anyio
async def test_get_agent_run_passes_through_error_fields(monkeypatch):
    """get_agent_run forwards failed_at, cancelled_at, and last_error."""
    import asyncio as _asyncio

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import get_agent_run

    wxo_payload = {
        "id": "r-fail",
        "status": "failed",
        "failed_at": "2026-01-01T00:02:00Z",
        "last_error": "timeout exceeded",
    }

    async def fake_to_thread(fn, *args, **kwargs):  # noqa: ARG001
        return wxo_payload

    monkeypatch.setattr(_asyncio, "to_thread", fake_to_thread)

    fake_client = SimpleNamespace(get_run=lambda _run_id: wxo_payload)
    result = await get_agent_run(fake_client, run_id="r-fail")

    assert result["execution_id"] == "r-fail"
    assert result["status"] == "failed"
    assert result["failed_at"] == "2026-01-01T00:02:00Z"
    assert result["last_error"] == "timeout exceeded"


# ---------------------------------------------------------------------------
# get_agent_run — WXO payload omits id
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_agent_run_falls_back_to_param_run_id(monkeypatch):
    """get_agent_run uses the run_id parameter when WXO payload omits id."""
    import asyncio as _asyncio

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import get_agent_run

    wxo_payload = {"status": "in_progress", "agent_id": "agent-1"}

    async def fake_to_thread(fn, *args, **kwargs):  # noqa: ARG001
        return wxo_payload

    monkeypatch.setattr(_asyncio, "to_thread", fake_to_thread)

    fake_client = SimpleNamespace(get_run=lambda _run_id: wxo_payload)
    result = await get_agent_run(fake_client, run_id="r-99")

    assert result["execution_id"] == "r-99"
    assert result["status"] == "in_progress"
    assert result["agent_id"] == "agent-1"


# ---------------------------------------------------------------------------
# build_orchestrate_run_payload — simplified MVP payload
# ---------------------------------------------------------------------------


def test_build_orchestrate_run_payload_uses_message_directly():
    """build_orchestrate_run_payload passes message from provider_data when present."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import build_orchestrate_run_payload

    message = {"role": "user", "content": "direct message"}
    result = build_orchestrate_run_payload(
        provider_data={"message": message, "agent_id": "a-1"},
        deployment_id="dep-fallback",
    )
    assert result["message"] is message
    assert result["agent_id"] == "a-1"
    assert len(result) == 2


def test_build_orchestrate_run_payload_falls_back_to_deployment_id():
    """build_orchestrate_run_payload uses deployment_id when agent_id is absent."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import build_orchestrate_run_payload

    result = build_orchestrate_run_payload(
        provider_data={"input": "hello"},
        deployment_id="dep-fallback",
    )
    assert result["agent_id"] == "dep-fallback"
    assert result["message"] == {"role": "user", "content": "hello"}
    assert len(result) == 2


def test_build_orchestrate_run_payload_excludes_extra_fields():
    """build_orchestrate_run_payload does not forward extra fields besides thread_id."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import build_orchestrate_run_payload

    result = build_orchestrate_run_payload(
        provider_data={
            "input": "hi",
            "thread_id": "t-1",
            "llm_params": {"model": "gpt-4"},
            "guardrails": True,
            "stream": True,
        },
        deployment_id="dep-1",
    )
    assert result["thread_id"] == "t-1"
    assert "llm_params" not in result
    assert "guardrails" not in result
    assert "stream" not in result
    assert len(result) == 3


def test_build_orchestrate_run_payload_omits_thread_id_when_absent():
    """build_orchestrate_run_payload does not include thread_id when not provided."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import build_orchestrate_run_payload

    result = build_orchestrate_run_payload(
        provider_data={"input": "hi"},
        deployment_id="dep-1",
    )
    assert "thread_id" not in result
    assert len(result) == 2


# ---------------------------------------------------------------------------
# WatsonxAgentExecutionResultData — adapter schema explicit fields
# ---------------------------------------------------------------------------


def test_adapter_execution_schema_parses_all_explicit_fields():
    """WatsonxAgentExecutionResultData parses all execution response fields."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import WatsonxAgentExecutionResultData

    data = {
        "execution_id": "e-1",
        "agent_id": "a-1",
        "status": "completed",
        "result": {"output": "answer"},
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:01:00Z",
        "failed_at": None,
        "cancelled_at": None,
        "last_error": None,
    }
    parsed = WatsonxAgentExecutionResultData.model_validate(data)
    assert parsed.execution_id == "e-1"
    assert parsed.agent_id == "a-1"
    assert parsed.status == "completed"
    assert parsed.result == {"output": "answer"}
    assert parsed.started_at == "2026-01-01T00:00:00Z"
    assert parsed.completed_at == "2026-01-01T00:01:00Z"


def test_adapter_execution_schema_has_no_run_id_field():
    """WatsonxAgentExecutionResultData does not expose run_id as a named field."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import WatsonxAgentExecutionResultData

    assert "run_id" not in WatsonxAgentExecutionResultData.model_fields


# ---------------------------------------------------------------------------
# WatsonxApiAgentExecution{Create,Status}ResultData — API schema explicit fields
# ---------------------------------------------------------------------------


def test_api_execution_create_schema_parses_all_explicit_fields():
    """WatsonxApiAgentExecutionCreateResultData parses all execution response fields."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
        WatsonxApiAgentExecutionCreateResultData,
    )

    data = {
        "id": "e-1",
        "agent_id": "a-1",
        "status": "accepted",
        "result": None,
        "started_at": "2026-01-01T00:00:00Z",
    }
    parsed = WatsonxApiAgentExecutionCreateResultData.model_validate(data)
    assert parsed.id == "e-1"
    assert parsed.agent_id == "a-1"
    assert parsed.status == "accepted"
    assert parsed.started_at == "2026-01-01T00:00:00Z"


def test_api_execution_status_schema_parses_all_explicit_fields():
    """WatsonxApiAgentExecutionStatusResultData parses all execution response fields."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
        WatsonxApiAgentExecutionStatusResultData,
    )

    data = {
        "id": "e-1",
        "agent_id": "a-1",
        "status": "failed",
        "result": None,
        "started_at": "2026-01-01T00:00:00Z",
        "failed_at": "2026-01-01T00:00:05Z",
        "last_error": "something broke",
    }
    parsed = WatsonxApiAgentExecutionStatusResultData.model_validate(data)
    assert parsed.id == "e-1"
    assert parsed.agent_id == "a-1"
    assert parsed.status == "failed"
    assert parsed.failed_at == "2026-01-01T00:00:05Z"
    assert parsed.last_error == "something broke"


def test_api_execution_schemas_have_no_run_id_field():
    """Neither create nor status schema exposes run_id as a named field."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
        WatsonxApiAgentExecutionCreateResultData,
        WatsonxApiAgentExecutionStatusResultData,
    )

    assert "run_id" not in WatsonxApiAgentExecutionCreateResultData.model_fields
    assert "run_id" not in WatsonxApiAgentExecutionStatusResultData.model_fields


def test_api_execution_schemas_omit_langflow_owned_fields():
    """deployment_id (Langflow DB UUID) belongs on the top-level response, not in provider_data."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
        WatsonxApiAgentExecutionCreateResultData,
        WatsonxApiAgentExecutionStatusResultData,
    )

    for schema in (WatsonxApiAgentExecutionCreateResultData, WatsonxApiAgentExecutionStatusResultData):
        assert "deployment_id" not in schema.model_fields
        assert "id" in schema.model_fields
        assert not hasattr(schema, "resolved_deployment_id")


def test_api_execution_schema_normalizes_id_fields():
    """Both create and status schemas strip whitespace and blanks from ID fields."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import (
        WatsonxApiAgentExecutionCreateResultData,
        WatsonxApiAgentExecutionStatusResultData,
    )

    for schema in (WatsonxApiAgentExecutionCreateResultData, WatsonxApiAgentExecutionStatusResultData):
        parsed = schema.model_validate(
            {
                "id": "  e-1  ",
                "agent_id": "  a-1  ",
            }
        )
        assert parsed.id == "e-1"
        assert parsed.agent_id == "a-1"

        parsed_blank = schema.model_validate(
            {
                "id": "  ",
                "agent_id": "",
            }
        )
        assert parsed_blank.id is None
        assert parsed_blank.agent_id is None


# ---------------------------------------------------------------------------
# Mapper shapers: shape_execution_create_result / shape_execution_status_result
# ---------------------------------------------------------------------------


def test_shape_execution_create_result_maps_all_fields():
    """shape_execution_create_result maps adapter fields to API response."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.mapper import WatsonxOrchestrateDeploymentMapper

    mapper = WatsonxOrchestrateDeploymentMapper()
    deployment_id = UUID("00000000-0000-0000-0000-000000000001")

    adapter_result = ExecutionCreateResult(
        execution_id="e-1",
        deployment_id="agent-1",
        provider_result={
            "execution_id": "e-1",
            "agent_id": "agent-1",
            "status": "accepted",
            "started_at": "2026-01-01T00:00:00Z",
        },
    )

    response = mapper.shape_execution_create_result(adapter_result, deployment_id=deployment_id)
    assert response.deployment_id == deployment_id
    assert response.provider_data["id"] == "e-1"
    assert response.provider_data["status"] == "accepted"
    assert response.provider_data["started_at"] == "2026-01-01T00:00:00Z"
    assert response.provider_data["agent_id"] == "agent-1"
    assert "deployment_id" not in response.provider_data
    assert "execution_id" not in response.provider_data


def test_shape_execution_status_result_maps_all_fields():
    """shape_execution_status_result maps adapter fields to API response."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.mapper import WatsonxOrchestrateDeploymentMapper

    mapper = WatsonxOrchestrateDeploymentMapper()
    deployment_id = UUID("00000000-0000-0000-0000-000000000002")

    adapter_result = ExecutionStatusResult(
        execution_id="e-2",
        deployment_id="agent-2",
        provider_result={
            "execution_id": "e-2",
            "agent_id": "agent-2",
            "status": "completed",
            "result": {"output": "done"},
            "completed_at": "2026-01-01T00:01:00Z",
        },
    )

    response = mapper.shape_execution_status_result(adapter_result, deployment_id=deployment_id)
    assert response.deployment_id == deployment_id
    assert response.provider_data["id"] == "e-2"
    assert response.provider_data["status"] == "completed"
    assert response.provider_data["result"] == {"output": "done"}
    assert response.provider_data["completed_at"] == "2026-01-01T00:01:00Z"
    assert "deployment_id" not in response.provider_data
    assert "execution_id" not in response.provider_data


def test_shape_execution_status_result_none_execution_id():
    """When adapter has no execution_id, provider_data includes it as None."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.mapper import WatsonxOrchestrateDeploymentMapper

    mapper = WatsonxOrchestrateDeploymentMapper()
    deployment_id = UUID("00000000-0000-0000-0000-000000000003")

    adapter_result = ExecutionStatusResult(
        execution_id=None,
        deployment_id="agent-3",
        provider_result={
            "agent_id": "agent-3",
            "status": "in_progress",
        },
    )

    response = mapper.shape_execution_status_result(
        adapter_result,
        deployment_id=deployment_id,
    )
    assert response.provider_data["id"] is None
    assert response.provider_data["status"] == "in_progress"


# ---------------------------------------------------------------------------
# verify_credentials
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_verify_credentials_success(monkeypatch):
    """verify_credentials returns VerifyCredentialsResult on valid credentials."""
    from lfx.services.adapters.deployment.schema import VerifyCredentials, VerifyCredentialsResult

    class FakeTokenManager:
        def get_token(self):
            return "fake-token"

    class FakeAuthenticator:
        token_manager = FakeTokenManager()

    monkeypatch.setattr(
        service_module,
        "get_authenticator",
        lambda **_kwargs: FakeAuthenticator(),
    )
    monkeypatch.setattr(service_module, "fetch_models_adapter", lambda *_args, **_kwargs: {})

    svc = WatsonxOrchestrateDeploymentService(settings_service=DummySettingsService())
    payload = VerifyCredentials(
        base_url="https://api.us-south.wxo.cloud.ibm.com",
        provider_data={"api_key": "valid-key"},  # pragma: allowlist secret
    )
    result = await svc.verify_credentials(user_id="u1", payload=payload)
    assert isinstance(result, VerifyCredentialsResult)


@pytest.mark.anyio
async def test_verify_credentials_invalid_key_raises(monkeypatch):
    """verify_credentials raises AuthenticationError when provider rejects credentials."""
    from ibm_cloud_sdk_core import ApiException
    from lfx.services.adapters.deployment.exceptions import AuthenticationError
    from lfx.services.adapters.deployment.schema import VerifyCredentials

    class FakeTokenManager:
        def get_token(self):
            raise ApiException(401, message="invalid api key")

    class FailingAuthenticator:
        token_manager = FakeTokenManager()

    monkeypatch.setattr(
        service_module,
        "get_authenticator",
        lambda **_kwargs: FailingAuthenticator(),
    )

    svc = WatsonxOrchestrateDeploymentService(settings_service=DummySettingsService())
    payload = VerifyCredentials(
        base_url="https://api.us-south.wxo.cloud.ibm.com",
        provider_data={"api_key": "bad-key"},  # pragma: allowlist secret
    )
    with pytest.raises(AuthenticationError, match="Credential verification"):
        await svc.verify_credentials(user_id="u1", payload=payload)


@pytest.mark.anyio
async def test_verify_credentials_instance_probe_forbidden(monkeypatch):
    """403 from wxO models probe maps to AuthorizationError (wrong instance for key)."""
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
    from lfx.services.adapters.deployment.exceptions import AuthorizationError
    from lfx.services.adapters.deployment.schema import VerifyCredentials
    from requests import Response

    class FakeTokenManager:
        def get_token(self):
            return "fake-token"

    class FakeAuthenticator:
        token_manager = FakeTokenManager()

    monkeypatch.setattr(
        service_module,
        "get_authenticator",
        lambda **_kwargs: FakeAuthenticator(),
    )

    def _fail_fetch_models(*_args, **_kwargs):
        response = Response()
        response.status_code = 403
        raise ClientAPIException(response=response)

    monkeypatch.setattr(service_module, "fetch_models_adapter", _fail_fetch_models)

    svc = WatsonxOrchestrateDeploymentService(settings_service=DummySettingsService())
    payload = VerifyCredentials(
        base_url="https://api.us-south.wxo.cloud.ibm.com",
        provider_data={"api_key": "valid-key"},  # pragma: allowlist secret
    )
    with pytest.raises(AuthorizationError, match="Credential verification"):
        await svc.verify_credentials(user_id="u1", payload=payload)


@pytest.mark.anyio
async def test_verify_credentials_malformed_key_from_authenticator_constructor_raises():
    """verify_credentials raises InvalidContentError when authenticator creation fails validation."""
    from lfx.services.adapters.deployment.exceptions import InvalidContentError
    from lfx.services.adapters.deployment.schema import VerifyCredentials

    svc = WatsonxOrchestrateDeploymentService(settings_service=DummySettingsService())
    payload = VerifyCredentials(
        base_url="https://api.us-south.wxo.cloud.ibm.com",
        provider_data={"api_key": "{bad-key}"},  # pragma: allowlist secret
    )

    with pytest.raises(InvalidContentError, match="malformed"):
        await svc.verify_credentials(user_id="u1", payload=payload)


@pytest.mark.anyio
async def test_verify_credentials_missing_provider_data_raises():
    """verify_credentials raises when provider_data is missing."""
    from lfx.services.adapters.deployment.schema import VerifyCredentials
    from lfx.services.adapters.payload import AdapterPayloadMissingError

    svc = WatsonxOrchestrateDeploymentService(settings_service=DummySettingsService())
    payload = VerifyCredentials(
        base_url="https://api.us-south.wxo.cloud.ibm.com",
        provider_data=None,
    )
    with pytest.raises(AdapterPayloadMissingError):
        await svc.verify_credentials(user_id="u1", payload=payload)


@pytest.mark.anyio
async def test_verify_credentials_bad_auth_scheme_raises():
    """verify_credentials raises AuthSchemeError for unrecognised URLs."""
    from lfx.services.adapters.deployment.exceptions import AuthSchemeError
    from lfx.services.adapters.deployment.schema import VerifyCredentials

    svc = WatsonxOrchestrateDeploymentService(settings_service=DummySettingsService())
    payload = VerifyCredentials(
        base_url="https://unknown-provider.example.com",
        provider_data={"api_key": "some-key"},  # pragma: allowlist secret
    )
    with pytest.raises(AuthSchemeError):
        await svc.verify_credentials(user_id="u1", payload=payload)


@pytest.mark.anyio
async def test_verify_credentials_authenticator_construction_unexpected_error(monkeypatch):
    """verify_credentials raises DeploymentError when get_authenticator() throws unexpectedly."""
    from lfx.services.adapters.deployment.exceptions import DeploymentError
    from lfx.services.adapters.deployment.schema import VerifyCredentials

    def _exploding_authenticator(**_kwargs):
        msg = "something unexpected"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        service_module,
        "get_authenticator",
        _exploding_authenticator,
    )

    svc = WatsonxOrchestrateDeploymentService(settings_service=DummySettingsService())
    payload = VerifyCredentials(
        base_url="https://api.us-south.wxo.cloud.ibm.com",
        provider_data={"api_key": "some-key"},  # pragma: allowlist secret
    )
    with pytest.raises(DeploymentError, match="failed unexpectedly"):
        await svc.verify_credentials(user_id="u1", payload=payload)


@pytest.mark.anyio
async def test_verify_credentials_forbidden_key_raises(monkeypatch):
    """verify_credentials raises AuthorizationError when provider returns 403."""
    from ibm_cloud_sdk_core import ApiException
    from lfx.services.adapters.deployment.exceptions import AuthorizationError
    from lfx.services.adapters.deployment.schema import VerifyCredentials

    class FakeTokenManager:
        def get_token(self):
            raise ApiException(403, message="forbidden")

    class ForbiddenAuthenticator:
        token_manager = FakeTokenManager()

    monkeypatch.setattr(
        service_module,
        "get_authenticator",
        lambda **_kwargs: ForbiddenAuthenticator(),
    )

    svc = WatsonxOrchestrateDeploymentService(settings_service=DummySettingsService())
    payload = VerifyCredentials(
        base_url="https://api.us-south.wxo.cloud.ibm.com",
        provider_data={"api_key": "some-key"},  # pragma: allowlist secret
    )
    with pytest.raises(AuthorizationError, match="Credential verification"):
        await svc.verify_credentials(user_id="u1", payload=payload)


@pytest.mark.anyio
async def test_verify_credentials_provider_unreachable(monkeypatch):
    """verify_credentials raises DeploymentError on network failure."""
    from lfx.services.adapters.deployment.exceptions import DeploymentError
    from lfx.services.adapters.deployment.schema import VerifyCredentials

    class FakeTokenManager:
        def get_token(self):
            msg = "connection refused"
            raise ConnectionError(msg)

    class UnreachableAuthenticator:
        token_manager = FakeTokenManager()

    monkeypatch.setattr(
        service_module,
        "get_authenticator",
        lambda **_kwargs: UnreachableAuthenticator(),
    )

    svc = WatsonxOrchestrateDeploymentService(settings_service=DummySettingsService())
    payload = VerifyCredentials(
        base_url="https://api.us-south.wxo.cloud.ibm.com",
        provider_data={"api_key": "some-key"},  # pragma: allowlist secret
    )
    with pytest.raises(DeploymentError, match="failed unexpectedly"):
        await svc.verify_credentials(user_id="u1", payload=payload)


# ---------------------------------------------------------------------------
# Ownership checks: binding.langflow verification
# ---------------------------------------------------------------------------


def _make_langflow_tool(tool_id: str, *, connections: dict[str, str] | None = None) -> dict[str, Any]:
    """Build a tool dict that looks Langflow-managed (has binding.langflow)."""
    return {
        "id": tool_id,
        "name": f"tool_{tool_id}",
        "binding": {
            "langflow": {
                "project_id": "proj-1",
                "connections": connections or {},
            }
        },
    }


def _make_external_tool(tool_id: str) -> dict[str, Any]:
    """Build a tool dict that is NOT Langflow-managed (no binding.langflow)."""
    return {
        "id": tool_id,
        "name": f"external_{tool_id}",
        "binding": {"some_other_platform": {}},
    }


def _make_unbound_tool(tool_id: str) -> dict[str, Any]:
    """Build a tool dict with no binding at all."""
    return {"id": tool_id, "name": f"bare_{tool_id}"}


@pytest.mark.anyio
async def test_update_connection_deltas_rejects_non_langflow_tool():
    """_update_existing_tool_connection_deltas must refuse to modify tools without binding.langflow."""
    _update_deltas = update_core_module._update_existing_tool_connection_deltas

    external_tool = _make_external_tool("ext-1")
    clients = FakeWXOClients(tool=FakeToolClient([external_tool]))

    ops = ToolConnectionOps(bind=OrderedUniqueStrs.from_values(["app-1"]))
    with pytest.raises(InvalidContentError, match="does not have a Langflow binding"):
        await _update_deltas(
            clients=clients,
            existing_tool_deltas={"ext-1": ops},
            resolved_connections={"app-1": "conn-1"},
            operation_to_provider_app_id={"app-1": "app-1"},
            original_tools={},
        )


@pytest.mark.anyio
async def test_update_connection_deltas_accepts_langflow_tool():
    """_update_existing_tool_connection_deltas succeeds for tools with binding.langflow."""
    _update_deltas = update_core_module._update_existing_tool_connection_deltas

    lf_tool = _make_langflow_tool("lf-1")
    clients = FakeWXOClients(tool=FakeToolClient([lf_tool]))

    ops = ToolConnectionOps(bind=OrderedUniqueStrs.from_values(["app-1"]))
    original_tools: dict[str, dict] = {}
    await _update_deltas(
        clients=clients,
        existing_tool_deltas={"lf-1": ops},
        resolved_connections={"app-1": "conn-1"},
        operation_to_provider_app_id={"app-1": "app-1"},
        original_tools=original_tools,
    )
    assert "lf-1" in original_tools
    assert clients.tool.update_calls


@pytest.mark.anyio
async def test_bind_existing_tools_for_create_rejects_non_langflow_tool():
    """_bind_existing_tools_for_create must refuse to modify tools without binding.langflow."""
    _bind_existing = create_core_module._bind_existing_tools_for_create

    external_tool = _make_external_tool("ext-1")
    clients = FakeWXOClients(tool=FakeToolClient([external_tool]))

    with pytest.raises(InvalidContentError, match="does not have a Langflow binding"):
        await _bind_existing(
            clients=clients,
            existing_tool_bindings={"ext-1": ["app-1"]},
            operation_to_provider_app_id={"app-1": "app-1"},
            resolved_connections={"app-1": "conn-1"},
            original_tools={},
        )


@pytest.mark.anyio
async def test_bind_existing_tools_for_create_accepts_langflow_tool():
    """_bind_existing_tools_for_create succeeds for tools with binding.langflow."""
    _bind_existing = create_core_module._bind_existing_tools_for_create

    lf_tool = _make_langflow_tool("lf-1")
    clients = FakeWXOClients(tool=FakeToolClient([lf_tool]))

    original_tools: dict[str, dict] = {}
    await _bind_existing(
        clients=clients,
        existing_tool_bindings={"lf-1": ["app-1"]},
        operation_to_provider_app_id={"app-1": "app-1"},
        resolved_connections={"app-1": "conn-1"},
        original_tools=original_tools,
    )
    assert "lf-1" in original_tools
    assert clients.tool.update_calls


@pytest.mark.anyio
async def test_update_existing_tool_connection_bindings_rejects_non_langflow_tool():
    """update_existing_tool_connection_bindings must refuse to modify tools without binding.langflow."""
    _update_bindings = tools_module.update_existing_tool_connection_bindings

    external_tool = _make_external_tool("ext-1")
    clients = FakeWXOClients(tool=FakeToolClient([external_tool]))

    with pytest.raises(InvalidContentError, match="does not have a Langflow binding"):
        await _update_bindings(
            clients=clients,
            existing_target_tool_ids=["ext-1"],
            resolved_connections={"app-1": "conn-1"},
            original_tools={},
        )


@pytest.mark.anyio
async def test_update_existing_tool_connection_bindings_rejects_unbound_tool():
    """update_existing_tool_connection_bindings must refuse tools with no binding at all."""
    _update_bindings = tools_module.update_existing_tool_connection_bindings

    bare_tool = _make_unbound_tool("bare-1")
    clients = FakeWXOClients(tool=FakeToolClient([bare_tool]))

    with pytest.raises(InvalidContentError, match="does not have a Langflow binding"):
        await _update_bindings(
            clients=clients,
            existing_target_tool_ids=["bare-1"],
            resolved_connections={"app-1": "conn-1"},
            original_tools={},
        )


# ---------------------------------------------------------------------------
# Tool rename safety
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_apply_tool_renames_succeeds_for_langflow_tool():
    """_apply_tool_renames renames a Langflow-owned tool on the agent."""
    _apply_renames = update_core_module._apply_tool_renames

    lf_tool = _make_langflow_tool("lf-1")
    clients = FakeWXOClients(tool=FakeToolClient([lf_tool]))

    original_tools: dict[str, dict] = {}
    await _apply_renames(
        clients=clients,
        agent_tool_ids=["lf-1"],
        tool_renames={"lf-1": "new_name"},
        original_tools=original_tools,
    )
    assert clients.tool.update_calls
    tool_id, payload = clients.tool.update_calls[0]
    assert tool_id == "lf-1"
    assert payload["name"] == "new_name"
    assert payload["display_name"] == "new_name"
    assert "lf-1" in original_tools


@pytest.mark.anyio
async def test_apply_tool_renames_rejects_non_langflow_tool():
    """_apply_tool_renames must refuse to rename tools without binding.langflow."""
    _apply_renames = update_core_module._apply_tool_renames

    external_tool = _make_external_tool("ext-1")
    clients = FakeWXOClients(tool=FakeToolClient([external_tool]))

    with pytest.raises(InvalidContentError, match="does not have a Langflow binding"):
        await _apply_renames(
            clients=clients,
            agent_tool_ids=["ext-1"],
            tool_renames={"ext-1": "stolen_name"},
            original_tools={},
        )
    assert not clients.tool.update_calls


@pytest.mark.anyio
async def test_apply_tool_renames_rejects_tool_not_on_agent():
    """_apply_tool_renames must refuse to rename tools not attached to the agent."""
    _apply_renames = update_core_module._apply_tool_renames

    lf_tool = _make_langflow_tool("lf-1")
    clients = FakeWXOClients(tool=FakeToolClient([lf_tool]))

    with pytest.raises(InvalidContentError, match="not attached to this agent"):
        await _apply_renames(
            clients=clients,
            agent_tool_ids=["other-tool"],
            tool_renames={"lf-1": "new_name"},
            original_tools={},
        )
    assert not clients.tool.update_calls


@pytest.mark.anyio
async def test_apply_tool_renames_rejects_missing_tool():
    """_apply_tool_renames must fail if tool doesn't exist on provider."""
    _apply_renames = update_core_module._apply_tool_renames

    clients = FakeWXOClients(tool=FakeToolClient([]))

    with pytest.raises(InvalidContentError, match="not found in provider"):
        await _apply_renames(
            clients=clients,
            agent_tool_ids=["ghost-1"],
            tool_renames={"ghost-1": "new_name"},
            original_tools={},
        )


@pytest.mark.anyio
async def test_apply_tool_renames_captures_original_for_rollback():
    """_apply_tool_renames must capture original payload before renaming for rollback."""
    _apply_renames = update_core_module._apply_tool_renames

    lf_tool = _make_langflow_tool("lf-1")
    lf_tool["name"] = "original_name"
    lf_tool["display_name"] = "original_name"
    clients = FakeWXOClients(tool=FakeToolClient([lf_tool]))

    original_tools: dict[str, dict] = {}
    await _apply_renames(
        clients=clients,
        agent_tool_ids=["lf-1"],
        tool_renames={"lf-1": "new_name"},
        original_tools=original_tools,
    )
    assert original_tools["lf-1"]["name"] == "original_name"


@pytest.mark.anyio
async def test_apply_tool_renames_preserves_latest_connections_when_original_already_captured():
    """Rename should keep connection updates already applied earlier in the transaction."""
    _apply_renames = update_core_module._apply_tool_renames

    lf_tool = _make_langflow_tool("lf-1", connections={"app-1": "conn-1", "app-2": "conn-2"})
    lf_tool["name"] = "current_name"
    lf_tool["display_name"] = "current_name"
    clients = FakeWXOClients(tool=FakeToolClient([lf_tool]))

    # Simulate pre-captured rollback payload from a prior connection-delta step.
    original_tools: dict[str, dict] = {
        "lf-1": {
            "id": "lf-1",
            "name": "pre_delta_name",
            "display_name": "pre_delta_name",
            "binding": {"langflow": {"project_id": "proj-1", "connections": {"app-1": "conn-1"}}},
        }
    }
    await _apply_renames(
        clients=clients,
        agent_tool_ids=["lf-1"],
        tool_renames={"lf-1": "new_name"},
        original_tools=original_tools,
    )

    _, payload = clients.tool.update_calls[0]
    assert payload["name"] == "new_name"
    assert payload["display_name"] == "new_name"
    assert payload["binding"]["langflow"]["connections"] == {"app-1": "conn-1", "app-2": "conn-2"}
    # Pre-captured rollback state must remain unchanged.
    assert original_tools["lf-1"]["name"] == "pre_delta_name"
    assert original_tools["lf-1"]["binding"]["langflow"]["connections"] == {"app-1": "conn-1"}


@pytest.mark.anyio
async def test_apply_tool_renames_preserves_latest_connections_for_add_and_remove_delta():
    """Rename should preserve the latest provider connections after mixed add/remove updates."""
    _apply_renames = update_core_module._apply_tool_renames

    # Simulate post-delta provider state (one app removed, one app added).
    lf_tool = _make_langflow_tool("lf-1", connections={"cfg-keep": "conn-keep", "cfg-add": "conn-add"})
    lf_tool["name"] = "current_name"
    lf_tool["display_name"] = "current_name"
    clients = FakeWXOClients(tool=FakeToolClient([lf_tool]))

    # Simulate pre-delta rollback snapshot captured earlier.
    original_tools: dict[str, dict] = {
        "lf-1": {
            "id": "lf-1",
            "name": "pre_delta_name",
            "display_name": "pre_delta_name",
            "binding": {
                "langflow": {
                    "project_id": "proj-1",
                    "connections": {"cfg-keep": "conn-keep", "cfg-remove": "conn-remove"},
                }
            },
        }
    }
    await _apply_renames(
        clients=clients,
        agent_tool_ids=["lf-1"],
        tool_renames={"lf-1": "renamed_tool"},
        original_tools=original_tools,
    )

    _, payload = clients.tool.update_calls[0]
    assert payload["name"] == "renamed_tool"
    assert payload["display_name"] == "renamed_tool"
    assert payload["binding"]["langflow"]["connections"] == {"cfg-keep": "conn-keep", "cfg-add": "conn-add"}
    # Rollback snapshot remains pre-delta.
    assert original_tools["lf-1"]["binding"]["langflow"]["connections"] == {
        "cfg-keep": "conn-keep",
        "cfg-remove": "conn-remove",
    }


# ---------------------------------------------------------------------------
# Tool name validation
# ---------------------------------------------------------------------------


def test_validate_tool_name_accepts_valid_name():
    """_validate_tool_name accepts a name that normalizes to a valid wxO identifier."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.mapper import _validate_tool_name

    assert _validate_tool_name("My Flow") == "My_Flow"
    assert _validate_tool_name("hello_world") == "hello_world"
    assert _validate_tool_name("flow-with-dashes") == "flow_with_dashes"


def test_validate_tool_name_rejects_empty():
    """_validate_tool_name rejects names that normalize to empty string."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.mapper import _validate_tool_name

    with pytest.raises(HTTPException) as exc_info:
        _validate_tool_name("!@#$%")
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_validate_tool_name_rejects_leading_digit():
    """_validate_tool_name rejects names that start with a digit after normalization."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.mapper import _validate_tool_name

    with pytest.raises(HTTPException) as exc_info:
        _validate_tool_name("123flow")
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_validate_tool_name_is_idempotent():
    """Running _validate_tool_name twice produces the same result."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.mapper import _validate_tool_name

    first = _validate_tool_name("My Flow!")
    second = _validate_tool_name(first)
    assert first == second


# ---------------------------------------------------------------------------
# Rename operation in plan builder
# ---------------------------------------------------------------------------


def test_build_update_plan_includes_rename():
    """build_provider_update_plan collects rename_tool operations into tool_renames."""
    build_plan = update_core_module.build_provider_update_plan

    agent = {"id": "agent-1", "tools": ["tool-1"]}
    payload = WatsonxDeploymentUpdatePayload(
        llm=TEST_WXO_LLM,
        operations=[
            {
                "op": "rename_tool",
                "tool": {"source_ref": "fv-1", "tool_id": "tool-1"},
                "new_name": "better_name",
            },
        ],
    )
    plan = build_plan(agent=agent, provider_update=payload)
    assert plan.tool_renames == {"tool-1": "better_name"}


def test_build_update_plan_without_renames_has_empty_dict():
    """build_provider_update_plan returns empty tool_renames when no renames present."""
    build_plan = update_core_module.build_provider_update_plan

    agent = {"id": "agent-1", "tools": ["tool-1"]}
    payload = WatsonxDeploymentUpdatePayload(
        llm=TEST_WXO_LLM,
        operations=[
            {
                "op": "remove_tool",
                "tool": {"source_ref": "fv-1", "tool_id": "tool-1"},
            },
        ],
    )
    plan = build_plan(agent=agent, provider_update=payload)
    assert plan.tool_renames == {}


# ---------------------------------------------------------------------------
# WXO_LFX_REQUIREMENT_OVERRIDE
# ---------------------------------------------------------------------------


def test_resolve_lfx_requirement_uses_override(monkeypatch):
    """_resolve_lfx_requirement returns the env var value when set."""
    _resolve = tools_module._resolve_lfx_requirement

    monkeypatch.setenv("WXO_LFX_REQUIREMENT_OVERRIDE", "lfx-nightly==0.4.0.dev32")
    assert _resolve() == "lfx-nightly==0.4.0.dev32"


def test_resolve_lfx_requirement_ignores_blank_override(monkeypatch):
    """_resolve_lfx_requirement ignores empty/whitespace-only override."""
    _resolve = tools_module._resolve_lfx_requirement

    monkeypatch.setenv("WXO_LFX_REQUIREMENT_OVERRIDE", "   ")
    # Should not return blank — should fall through to installed version or raise
    result = _resolve()
    assert result.strip()
    assert result != "   "


# ---------------------------------------------------------------------------
# Rename operation API payload parsing
# ---------------------------------------------------------------------------


def test_rename_tool_api_payload_parses():
    """WatsonxApiRenameToolOperation parses correctly."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import WatsonxApiRenameToolOperation

    op = WatsonxApiRenameToolOperation(
        op="rename_tool",
        flow_version_id="00000000-0000-0000-0000-000000000001",
        tool_name="new_tool_name",
    )
    assert op.op == "rename_tool"
    assert op.tool_name == "new_tool_name"


def test_rename_tool_api_payload_rejects_empty_name():
    """WatsonxApiRenameToolOperation rejects empty tool_name."""
    from langflow.api.v1.mappers.deployments.watsonx_orchestrate.payloads import WatsonxApiRenameToolOperation

    with pytest.raises(ValidationError):
        WatsonxApiRenameToolOperation(
            op="rename_tool",
            flow_version_id="00000000-0000-0000-0000-000000000001",
            tool_name="",
        )


def test_rename_tool_provider_payload_parses():
    """WatsonxRenameToolOperation parses correctly at provider level."""
    op = WatsonxRenameToolOperation(
        op="rename_tool",
        tool={"source_ref": "fv-1", "tool_id": "tool-1"},
        new_name="better_name",
    )
    assert op.new_name == "better_name"
    assert op.tool.tool_id == "tool-1"


# ---------------------------------------------------------------------------
# DeploymentFlowVersionListItem carries provider tool_name under provider_data
# ---------------------------------------------------------------------------


def test_flow_version_list_item_includes_tool_name_in_provider_data():
    """DeploymentFlowVersionListItem serializes provider tool_name under provider_data."""
    from langflow.api.v1.schemas.deployments import DeploymentFlowVersionListItem

    item = DeploymentFlowVersionListItem(
        id="00000000-0000-0000-0000-000000000001",
        flow_id="00000000-0000-0000-0000-000000000002",
        flow_name="My Flow",
        version_number=1,
        provider_data={"tool_name": "my_custom_tool"},
    )
    data = item.model_dump()
    assert data["provider_data"]["tool_name"] == "my_custom_tool"


def test_flow_version_list_item_provider_data_defaults_to_none():
    """DeploymentFlowVersionListItem defaults provider_data to None."""
    from langflow.api.v1.schemas.deployments import DeploymentFlowVersionListItem

    item = DeploymentFlowVersionListItem(
        id="00000000-0000-0000-0000-000000000001",
        flow_id="00000000-0000-0000-0000-000000000002",
        version_number=1,
    )
    assert item.provider_data is None

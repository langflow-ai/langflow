from __future__ import annotations

import importlib
import io
import zipfile
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException, status
from lfx.services.adapters.deployment.exceptions import (
    AuthorizationError,
    CredentialResolutionError,
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    OperationNotSupportedError,
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
    SnapshotItems,
    SnapshotListParams,
)

try:
    import langflow.services.adapters.deployment.watsonx_orchestrate  # noqa: F401
except ModuleNotFoundError:
    pytest.skip(
        "Skipping Watsonx deployment tests: optional IBM SDK dependencies not available.",
        allow_module_level=True,
    )

tools_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.core.tools")
service_module = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate.service")
update_helpers_module = importlib.import_module(
    "langflow.services.adapters.deployment.watsonx_orchestrate.update_helpers"
)
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


class DummySettingsService:
    def __init__(self):
        self.settings = SimpleNamespace()


class FakeAgentClient:
    def __init__(
        self,
        deployment: dict,
        listed_agents: list[dict] | None = None,
        get_payloads: dict[str, dict | list[dict]] | None = None,
    ):
        self._deployment = deployment
        self._listed_agents = listed_agents or []
        self._get_payloads = get_payloads or {}
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
        return SimpleNamespace(id="dep-created")

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
        self.create_calls: list[dict] = []
        self.create_config_calls: list[tuple[str, dict]] = []
        self.create_credentials_calls: list[tuple[str, object, bool, dict]] = []

    def get_draft_by_app_id(self, app_id: str):
        if app_id in self._connections_by_app_id:
            return SimpleNamespace(connection_id=self._connections_by_app_id[app_id])
        return None

    def get_config(self, app_id: str, env):  # noqa: ARG002
        return SimpleNamespace(security_scheme="key_value")

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


def _with_wxo_wrappers(ns):
    """Attach WxOClient SDK wrapper methods to a SimpleNamespace test double."""
    if hasattr(ns, "_base") and ns._base is not None:
        ns.get_agents_raw = lambda params=None: ns._base._get("/agents", params=params)
        ns.post_run = lambda *, query_suffix="", data: ns._base._post(f"/runs{query_suffix}", data)
        ns.get_run = lambda run_id: ns._base._get(f"/runs/{run_id}")
    return ns


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
async def test_create_rejects_config_reference_before_name_precheck(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(InvalidDeploymentOperationError, match="Config reference binding is not supported"):
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
                config=ConfigItem(reference_id="existing-config"),
            ),
        )


@pytest.mark.anyio
async def test_create_rejects_missing_resource_name_prefix():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    with pytest.raises(InvalidContentError, match="resource_name_prefix"):
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                ),
            ),
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
    monkeypatch.setattr(update_helpers_module, "validate_connection", mock_validate_connection)

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "tools": {"existing_ids": ["tool-3"]},
                "connections": {"existing_app_ids": ["cfg-new"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"reference_id": "tool-3"},
                        "app_ids": ["cfg-new"],
                    }
                ],
            }
        ),
        db=object(),
    )

    assert result.snapshot_ids == ["tool-3"]
    assert [tool_id for tool_id, _payload in fake_tool.update_calls] == ["tool-3"]
    _, updated_tool_payload = fake_tool.update_calls[0]
    assert updated_tool_payload["binding"]["langflow"]["connections"]["cfg-new"] == "conn-new"
    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload["tools"] == ["tool-1", "tool-3"]


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

    async def mock_create_and_upload(*, clients, tool_bindings, tool_name_prefix):
        _ = clients
        first_binding = tool_bindings[0]
        captured["connections"] = first_binding.connections
        captured["tool_name_prefix"] = tool_name_prefix
        return ["new-tool-1"]

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(update_helpers_module, "create_config", mock_create_config)
    monkeypatch.setattr(update_helpers_module, "validate_connection", mock_validate_connection)
    monkeypatch.setattr(
        update_helpers_module,
        "create_and_upload_wxo_flow_tools_with_bindings",
        mock_create_and_upload,
    )

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "resource_name_prefix": "lf_",
                "tools": {
                    "raw_payloads": [
                        {
                            "id": str(UUID("00000000-0000-0000-0000-000000000011")),
                            "name": "snapshot-new-1",
                            "description": "desc",
                            "data": {"nodes": [], "edges": []},
                            "tags": [],
                            "provider_data": {"project_id": "project-1"},
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

    assert captured["created_app_id"] == "lf_cfg"
    assert captured["connections"] == {"cfg": "conn-lf_cfg"}
    assert captured["tool_name_prefix"] == "lf_"
    assert result.snapshot_ids == ["new-tool-1"]
    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload["tools"] == ["tool-1", "new-tool-1"]


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
    monkeypatch.setattr(update_helpers_module, "validate_connection", mock_validate_connection)

    result = await service.update(
        user_id="user-1",
        deployment_id="dep-1",
        payload=DeploymentUpdate(
            provider_data={
                "tools": {"existing_ids": ["tool-1", "tool-2", "tool-3"]},
                "connections": {"existing_app_ids": ["cfg-1", "cfg-2"]},
                "operations": [
                    {"op": "bind", "tool": {"reference_id": "tool-3"}, "app_ids": ["cfg-2", "cfg-1"]},
                    {"op": "unbind", "tool_id": "tool-1", "app_ids": ["cfg-1", "cfg-2"]},
                    {"op": "remove_tool", "tool_id": "tool-2"},
                ],
            }
        ),
        db=object(),
    )

    assert validate_calls == ["cfg-1", "cfg-2"]
    assert result.snapshot_ids == ["tool-3"]

    # Existing tool updates should follow first encounter order: bind(tool-3) then unbind(tool-1).
    assert [tool_id for tool_id, _payload in fake_tool.update_calls] == ["tool-3", "tool-1"]

    _, tool3_payload = fake_tool.update_calls[0]
    assert list(tool3_payload["binding"]["langflow"]["connections"]) == ["cfg-2", "cfg-1"]
    assert tool3_payload["binding"]["langflow"]["connections"] == {"cfg-2": "conn-cfg-2", "cfg-1": "conn-cfg-1"}

    _, tool1_payload = fake_tool.update_calls[1]
    assert tool1_payload["binding"]["langflow"]["connections"] == {}

    _, agent_payload = fake_agent.update_calls[0]
    assert agent_payload["tools"] == ["tool-1", "tool-3"]


def test_ordered_unique_strs_preserves_encounter_order_and_safe_discard():
    ordered = update_helpers_module.OrderedUniqueStrs()
    ordered.extend(["b", "a", "b", "c"])
    ordered.add("a")
    ordered.add("d")
    ordered.discard("c")
    ordered.discard("missing")

    assert ordered.to_list() == ["b", "a", "d"]


def test_build_provider_update_plan_preserves_operation_encounter_order():
    provider_update = payloads_module.WatsonxDeploymentUpdatePayload.model_validate(
        {
            "resource_name_prefix": "lf_",
            "tools": {
                "existing_ids": ["tool-a", "tool-b", "tool-c"],
                "raw_payloads": [
                    {
                        "id": str(UUID("00000000-0000-0000-0000-000000000041")),
                        "name": "snapshot-raw-1",
                        "description": "desc",
                        "data": {"nodes": [], "edges": []},
                        "tags": [],
                        "provider_data": {"project_id": "project-1"},
                    }
                ],
            },
            "connections": {
                "existing_app_ids": ["cfg-1", "cfg-2", "cfg-3"],
                "raw_payloads": [
                    {"app_id": "cfg-raw-1", "environment_variables": {"API_KEY": {"source": "raw", "value": "x"}}},
                    {"app_id": "cfg-raw-2", "environment_variables": {"API_KEY": {"source": "raw", "value": "y"}}},
                ],
            },
            "operations": [
                {"op": "bind", "tool": {"reference_id": "tool-c"}, "app_ids": ["cfg-2", "cfg-1", "cfg-2"]},
                {"op": "bind", "tool": {"reference_id": "tool-a"}, "app_ids": ["cfg-1"]},
                {"op": "unbind", "tool_id": "tool-c", "app_ids": ["cfg-3", "cfg-1", "cfg-3"]},
                {"op": "remove_tool", "tool_id": "tool-b"},
                {"op": "bind", "tool": {"name_of_raw": "snapshot-raw-1"}, "app_ids": ["cfg-raw-2", "cfg-raw-1"]},
            ],
        }
    )
    plan = update_helpers_module.build_provider_update_plan(
        agent={"id": "dep-1", "tools": ["tool-a", "tool-b"]},
        provider_update=provider_update,
    )

    assert plan.bind_existing_tool_ids == ["tool-c", "tool-a"]
    assert plan.final_existing_tool_ids == ["tool-a", "tool-c"]
    assert plan.existing_app_ids == ["cfg-1", "cfg-2", "cfg-3"]
    assert [item.operation_app_id for item in plan.raw_connections_to_create] == ["cfg-raw-1", "cfg-raw-2"]
    assert [item.provider_app_id for item in plan.raw_connections_to_create] == ["lf_cfg-raw-1", "lf_cfg-raw-2"]
    assert len(plan.raw_tools_to_create) == 1
    assert plan.raw_tools_to_create[0].app_ids == ["cfg-raw-2", "cfg-raw-1"]

    delta = plan.existing_tool_deltas["tool-c"]
    assert delta.bind.to_list() == ["cfg-2", "cfg-1"]
    assert delta.unbind.to_list() == ["cfg-3", "cfg-1"]


@pytest.mark.anyio
async def test_update_existing_tool_connection_deltas_uses_bind_order_in_errors():
    fake_tool = FakeToolClient([{"id": "tool-c", "name": "tool-c", "binding": {"langflow": {"connections": {}}}}])
    clients = SimpleNamespace(tool=fake_tool)
    delta = update_helpers_module.ToolConnectionOps()
    delta.bind.extend(["cfg-missing-first", "cfg-present"])

    with pytest.raises(InvalidContentError, match="cfg-missing-first"):
        await update_helpers_module._update_existing_tool_connection_deltas(
            clients=clients,
            existing_tool_deltas={"tool-c": delta},
            resolved_connections={"cfg-present": "conn-present"},
            original_tools={},
        )


@pytest.mark.anyio
async def test_list_deployments_filters_with_provider_draft_filters(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": []},
        listed_agents=[
            {"id": "dep-1", "name": "deployment-1", "tools": []},
            {"id": "dep-2", "name": "deployment-2", "tools": []},
            {"id": "dep-3", "name": "deployment-3", "tools": []},
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
            provider_params={"ids": ["dep-2"], "names": ["deployment-3"]},
        ),
    )

    assert sorted(item.id for item in result.deployments) == ["dep-2", "dep-3"]


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
    monkeypatch.setattr(update_helpers_module, "create_config", mock_create_config)

    with pytest.raises(DeploymentConflictError, match="error details"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=DeploymentUpdate(
                provider_data={
                    "resource_name_prefix": "lf_",
                    "tools": {
                        "raw_payloads": [
                            {
                                "id": str(UUID("00000000-0000-0000-0000-000000000012")),
                                "name": "snapshot-new-1",
                                "description": "desc",
                                "data": {"nodes": [], "edges": []},
                                "tags": [],
                                "provider_data": {"project_id": "project-1"},
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


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider_data", "error_message"),
    [
        (
            {
                "tools": {"existing_ids": ["tool-1"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"reference_id": "tool-1"},
                        "app_ids": ["undeclared_app_for_bind"],
                    }
                ],
            },
            "operation app_ids must be declared in connections\\.existing_app_ids or "
            "connections\\.raw_payloads\\[\\*\\]\\.app_id",
        ),
        (
            {
                "tools": {"existing_ids": ["tool-1"]},
                "connections": {"existing_app_ids": ["cfg-1"]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"reference_id": "tool-missing"},
                        "app_ids": ["cfg-1"],
                    }
                ],
            },
            "bind.tool.reference_id not found in tools.existing_ids",
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
    monkeypatch.setattr(update_helpers_module, "validate_connection", mock_validate_connection)

    with pytest.raises(DeploymentError, match="Please check server logs for details"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=DeploymentUpdate(
                spec=BaseDeploymentDataUpdate(description="trigger update"),
                provider_data={
                    "tools": {"existing_ids": ["tool-1"]},
                    "connections": {"existing_app_ids": ["cfg-1"]},
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"reference_id": "tool-1"},
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

    async def mock_create_and_upload_with_bindings(*, clients, tool_bindings, tool_name_prefix):
        _ = clients, tool_bindings, tool_name_prefix
        raise core_tools_module.ToolUploadBatchError(
            created_tool_ids=["created-tool-1"],
            errors=[RuntimeError("upload failed")],
        )

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(update_helpers_module, "create_config", mock_create_config)
    monkeypatch.setattr(update_helpers_module, "validate_connection", mock_validate_connection)
    monkeypatch.setattr(
        update_helpers_module,
        "create_and_upload_wxo_flow_tools_with_bindings",
        mock_create_and_upload_with_bindings,
    )

    with pytest.raises(DeploymentError, match="Please check server logs for details"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=DeploymentUpdate(
                provider_data={
                    "resource_name_prefix": "lf_",
                    "tools": {
                        "raw_payloads": [
                            {
                                "id": str(UUID("00000000-0000-0000-0000-000000000021")),
                                "name": "snapshot-new-1",
                                "description": "desc",
                                "data": {"nodes": [], "edges": []},
                                "tags": [],
                                "provider_data": {"project_id": "project-1"},
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
    assert fake_connections.delete_calls == ["lf_cfg"]


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
        tool_name_prefix,
    ):
        captured["clients"] = clients
        captured["flow_payloads"] = flow_payloads
        captured["connections"] = connections
        captured["tool_name_prefix"] = tool_name_prefix
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
        flows=[],
        tool_name_prefix="lf_test_",
    )

    assert result == ["tool-1"]
    assert captured["connections"] == {"app-1": "conn-123"}
    assert captured["tool_name_prefix"] == "lf_test_"


def test_create_wxo_flow_tool_keeps_load_from_db_global_values_unprefixed(monkeypatch):
    captured_tool_definition = {}
    flow_payload = BaseFlowArtifact(
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
        provider_data={"project_id": "project-123"},
    )

    fake_tool = SimpleNamespace(
        __tool_spec__=SimpleNamespace(
            model_dump=lambda **kwargs: {"name": "flow"},  # noqa: ARG005
        )
    )

    def mock_create_langflow_tool(*, tool_definition, connections, show_details):  # noqa: ARG001
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
        tool_name_prefix="lf_test_",
    )

    template = captured_tool_definition["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] == "OPENAI_API_KEY"
    assert template["plain_value"]["value"] == "DO_NOT_TOUCH"


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
        match="Flow payload must include provider_data with a non-empty project_id",
    ):
        create_wxo_flow_tool(
            flow_payload=flow_payload,
            connections={},
            tool_name_prefix="lf_test_",
        )


def test_create_wxo_flow_tool_prefixes_name_for_raw_payload(monkeypatch):
    flow_payload = BaseFlowArtifact(
        id="00000000-0000-0000-0000-000000000001",
        name="basicllmwxo",
        description="desc",
        data={"nodes": [], "edges": []},
        tags=[],
        provider_data={"project_id": "project-123"},
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
        tool_name_prefix="lf_abcdef_",
    )

    assert tool_payload["name"] == "lf_abcdef_basicllmwxo"
    assert tool_payload["binding"]["langflow"]["project_id"] == "project-123"
    assert artifact_bytes == b"artifact"


@pytest.mark.anyio
async def test_create_wires_snapshot_ids_to_agent_and_prefixed_names(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )
    captured: dict[str, object] = {}

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    async def mock_process_config(user_id, db, deployment_name, config, *, clients):  # noqa: ARG001
        captured["config_deployment_name"] = deployment_name
        return deployment_name

    monkeypatch.setattr(
        service_module,
        "process_config",
        mock_process_config,
    )

    async def mock_process_raw_flows_with_app_id(
        clients,  # noqa: ARG001
        app_id,
        flows,
        tool_name_prefix,
    ):
        captured["snapshot_app_id"] = app_id
        captured["snapshot_flows"] = flows
        captured["tool_name_prefix"] = tool_name_prefix
        return ["tool-1", "tool-2"]

    monkeypatch.setattr(
        service_module,
        "process_raw_flows_with_app_id",
        mock_process_raw_flows_with_app_id,
    )

    deployment_payload = DeploymentCreate(
        spec=BaseDeploymentData(
            name="my deployment",
            description="desc",
            type=DeploymentType.AGENT,
            provider_spec={"resource_name_prefix": "lf_abcdef_"},
        ),
        config=ConfigItem(
            raw_payload=DeploymentConfig(
                name="ignored",
                description="from payload",
                environment_variables=None,
            )
        ),
        snapshot=SnapshotItems(
            raw_payloads=[
                BaseFlowArtifact(
                    id=UUID("00000000-0000-0000-0000-000000000001"),
                    name="snapshot-one",
                    description="desc",
                    data={"nodes": [], "edges": []},
                    tags=[],
                    provider_data={"project_id": "project-123"},
                )
            ]
        ),
    )

    result = await service.create(
        user_id="user-1",
        payload=deployment_payload,
        db=object(),
    )

    assert result.id == "dep-created"
    assert result.config_id == "lf_abcdef_my_deployment_ignored_app_id"
    assert result.snapshot_ids == ["tool-1", "tool-2"]
    assert captured["config_deployment_name"] == "lf_abcdef_my_deployment_ignored_app_id"
    assert captured["snapshot_app_id"] == "lf_abcdef_my_deployment_ignored_app_id"
    assert len(captured["snapshot_flows"]) == 1
    assert captured["tool_name_prefix"] == "lf_abcdef_"

    assert fake_clients.agent.create_calls
    assert fake_clients.agent.create_calls[0]["tools"] == ["tool-1", "tool-2"]
    assert fake_clients.agent.create_calls[0]["name"] == "lf_abcdef_my_deployment"


@pytest.mark.anyio
async def test_create_uses_caller_provided_resource_name_prefix(monkeypatch):
    """When provider_spec includes resource_name_prefix, the service uses it."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )
    captured: dict[str, object] = {}

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    async def mock_process_config(user_id, db, deployment_name, config, *, clients):  # noqa: ARG001
        captured["config_deployment_name"] = deployment_name
        return deployment_name

    monkeypatch.setattr(
        service_module,
        "process_config",
        mock_process_config,
    )

    async def mock_process_raw_flows_with_app_id(
        clients,  # noqa: ARG001
        app_id,
        flows,
        tool_name_prefix,
    ):
        captured["snapshot_app_id"] = app_id
        captured["snapshot_flows"] = flows
        captured["tool_name_prefix"] = tool_name_prefix
        return ["tool-1", "tool-2"]

    monkeypatch.setattr(
        service_module,
        "process_raw_flows_with_app_id",
        mock_process_raw_flows_with_app_id,
    )

    deployment_payload = DeploymentCreate(
        spec=BaseDeploymentData(
            name="my deployment",
            description="desc",
            type=DeploymentType.AGENT,
            provider_spec={"resource_name_prefix": "idempotent_abc_"},
        ),
        config=ConfigItem(
            raw_payload=DeploymentConfig(
                name="ignored",
                description="from payload",
                environment_variables=None,
            )
        ),
        snapshot=SnapshotItems(
            raw_payloads=[
                BaseFlowArtifact(
                    id=UUID("00000000-0000-0000-0000-000000000001"),
                    name="snapshot-one",
                    description="desc",
                    data={"nodes": [], "edges": []},
                    tags=[],
                    provider_data={"project_id": "project-123"},
                )
            ]
        ),
    )

    result = await service.create(
        user_id="user-1",
        payload=deployment_payload,
        db=object(),
    )

    assert result.id == "dep-created"
    assert captured["config_deployment_name"] == "idempotent_abc_my_deployment_ignored_app_id"
    assert captured["snapshot_app_id"] == "idempotent_abc_my_deployment_ignored_app_id"
    assert captured["tool_name_prefix"] == "idempotent_abc_"

    assert fake_clients.agent.create_calls
    assert fake_clients.agent.create_calls[0]["name"] == "idempotent_abc_my_deployment"


@pytest.mark.anyio
async def test_create_rolls_back_and_preserves_original_error_when_cleanup_fails(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_connections = FakeConnectionsClient()
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=fake_connections,
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    async def mock_process_config(user_id, db, deployment_name, config, *, clients):  # noqa: ARG001
        return deployment_name

    monkeypatch.setattr(
        service_module,
        "process_config",
        mock_process_config,
    )

    async def mock_process_raw_flows_with_app_id(
        clients,  # noqa: ARG001
        app_id,  # noqa: ARG001
        flows,  # noqa: ARG001
        tool_name_prefix,  # noqa: ARG001
    ):
        msg = "boom"
        raise RuntimeError(msg)

    def failing_delete(app_id: str):
        _ = app_id
        msg = "cleanup failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        service_module,
        "process_raw_flows_with_app_id",
        mock_process_raw_flows_with_app_id,
    )
    monkeypatch.setattr(fake_connections, "delete", failing_delete)

    deployment_payload = DeploymentCreate(
        spec=BaseDeploymentData(
            name="my deployment",
            description="desc",
            type=DeploymentType.AGENT,
            provider_spec={"resource_name_prefix": "lf_abcdef_"},
        ),
        config=ConfigItem(
            raw_payload=DeploymentConfig(
                name="ignored",
                description="from payload",
                environment_variables=None,
            )
        ),
        snapshot=SnapshotItems(
            raw_payloads=[
                BaseFlowArtifact(
                    id=UUID("00000000-0000-0000-0000-000000000001"),
                    name="snapshot-one",
                    description="desc",
                    data={"nodes": [], "edges": []},
                    tags=[],
                    provider_data={"project_id": "project-123"},
                )
            ]
        ),
    )

    with pytest.raises(DeploymentError, match="Please check server logs for details"):
        await service.create(
            user_id="user-1",
            payload=deployment_payload,
            db=object(),
        )


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
            provider_data={"input": "hello from test", "thread_id": "thread-123", "stream": False},
        ),
    )

    assert result.deployment_id == "dep-1"
    assert result.execution_id == "run-1"
    assert result.provider_result == {"status": "accepted", "run_id": "run-1"}
    assert fake_base.post_calls
    path, payload = fake_base.post_calls[0]
    assert path == "/runs?stream=false"
    assert payload["agent_id"] == "dep-1"
    assert payload["thread_id"] == "thread-123"
    assert payload["message"] == {"role": "user", "content": "hello from test"}


@pytest.mark.anyio
async def test_get_execution_returns_completed_output(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": []})
    fake_base = FakeBaseClient(
        get_payloads={
            "/runs/run-1": {
                "run_id": "run-1",
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
    assert result.provider_result["run_id"] == "run-1"
    assert result.provider_result["completed_at"] == "2026-03-08T18:23:25.277362Z"


@pytest.mark.anyio
async def test_get_execution_fetches_result_payload(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient({"id": "dep-1", "tools": []})
    fake_base = FakeBaseClient(
        get_payloads={
            "/runs/run-1": {
                "run_id": "run-1",
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
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=fake_tool,
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

    assert len(result.configs) == 1
    assert result.configs[0].id == "cfg-1"
    assert result.configs[0].name == "cfg-1"


@pytest.mark.anyio
async def test_list_snapshots_single_deployment_scope(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1", "tool-2"]}),
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

    assert [snapshot.id for snapshot in result.snapshots] == ["tool-1", "tool-2"]


@pytest.mark.anyio
async def test_list_configs_without_deployment_id_raises(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(OperationNotSupportedError, match="requires exactly one deployment_id"):
        await service.list_configs(user_id="user-1", db=object(), params=None)


@pytest.mark.anyio
async def test_list_snapshots_without_deployment_id_raises(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(OperationNotSupportedError, match="requires exactly one deployment_id"):
        await service.list_snapshots(user_id="user-1", db=object(), params=None)


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

    assert is_retryable_create_exception(DeploymentConflictError()) is False
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
        app_id="app-1",
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
        app_id="app-1",
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
            {"id": "dep-1", "name": "agent-1", "tools": []},
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
async def test_list_types_returns_supported_types():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    result = await service.list_types(user_id="user-1", db=object())
    assert DeploymentType.AGENT in result.deployment_types
    assert len(result.deployment_types) == 1


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
    monkeypatch.setattr(
        tools_module,
        "create_wxo_flow_tool",
        lambda flow_payload, connections, tool_name_prefix: (  # noqa: ARG005
            {"name": flow_payload.name, "description": flow_payload.description},
            b"artifact",
        ),
    )

    bindings = [
        tools_module.FlowToolBindingSpec(
            flow_payload=BaseFlowArtifact(
                id=UUID("00000000-0000-0000-0000-000000000031"),
                name="snapshot-one",
                description="desc",
                data={"nodes": [], "edges": []},
                tags=[],
                provider_data={"project_id": "project-1"},
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
                provider_data={"project_id": "project-1"},
            ),
            connections={"cfg-1": "conn-1"},
        ),
    ]

    with pytest.raises(tools_module.ToolUploadBatchError) as exc:
        await tools_module.create_and_upload_wxo_flow_tools_with_bindings(
            clients=fake_clients,
            tool_bindings=bindings,
            tool_name_prefix="lf_",
        )

    assert set(exc.value.created_tool_ids) == {"tool-1", "tool-2"}
    assert len(created_calls) == 2


def test_resolve_resource_name_prefix_uses_caller_provided_prefix():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import resolve_resource_name_prefix

    assert resolve_resource_name_prefix(caller_prefix="custom_abc_") == "custom_abc_"


def test_resolve_resource_name_prefix_rejects_empty_string():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import resolve_resource_name_prefix

    with pytest.raises(InvalidContentError, match="non-empty string"):
        resolve_resource_name_prefix(caller_prefix="")


def test_resolve_resource_name_prefix_rejects_non_alpha_start():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import resolve_resource_name_prefix

    with pytest.raises(InvalidContentError, match="start with a letter"):
        resolve_resource_name_prefix(caller_prefix="123_prefix_")


def test_resolve_resource_name_prefix_rejects_only_special_chars():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import resolve_resource_name_prefix

    with pytest.raises(InvalidContentError, match="alphanumeric"):
        resolve_resource_name_prefix(caller_prefix="!!!")


def test_resolve_resource_name_prefix_normalizes_caller_prefix():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import resolve_resource_name_prefix

    assert resolve_resource_name_prefix(caller_prefix="my-prefix!") == "my_prefix"


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

    with pytest.raises(DeploymentNotFoundError, match="not found"):
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

    with pytest.raises(DeploymentConflictError, match="already exists"):
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.UPDATE,
            log_msg="unexpected update conflict",
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


def test_build_agent_payload_requires_provider_spec():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import build_agent_payload

    data = SimpleNamespace(provider_spec=None, description="desc", name="test")
    with pytest.raises(InvalidContentError, match="provider_spec"):
        build_agent_payload(data=data, tool_ids=[])


def test_build_agent_payload_structure():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import build_agent_payload

    data = SimpleNamespace(
        provider_spec={"name": "agent_name", "display_name": "Agent Name"},
        description="test description",
        name="test",
    )
    payload = build_agent_payload(data=data, tool_ids=["tool-1", "tool-2"])
    assert payload["name"] == "agent_name"
    assert payload["display_name"] == "Agent Name"
    assert payload["description"] == "test description"
    assert payload["tools"] == ["tool-1", "tool-2"]
    assert "llm" in payload


def test_extract_agent_tool_ids():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_agent_tool_ids

    assert extract_agent_tool_ids({"tools": ["t1", "t2", None, ""]}) == ["t1", "t2"]
    assert extract_agent_tool_ids({}) == []


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


def test_build_orchestrate_runs_query():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import build_orchestrate_runs_query

    assert build_orchestrate_runs_query(None) == ""
    assert build_orchestrate_runs_query({}) == ""
    assert "stream=true" in build_orchestrate_runs_query({"stream": True})
    assert "stream_timeout=30" in build_orchestrate_runs_query({"stream_timeout": 30})


def test_create_agent_run_result_empty_raises():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    with pytest.raises(DeploymentError, match="empty response"):
        create_agent_run_result(None)
    with pytest.raises(DeploymentError, match="empty response"):
        create_agent_run_result({})


def test_create_agent_run_result_with_run_id():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    result = create_agent_run_result({"status": "running", "run_id": "r-1"})
    assert result == {"status": "running", "run_id": "r-1"}


# ---------------------------------------------------------------------------
# Status helper tests
# ---------------------------------------------------------------------------


def test_derive_agent_environment_draft():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import derive_agent_environment

    assert derive_agent_environment({"environments": [{"name": "draft"}]}) == "draft"


def test_derive_agent_environment_live():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import derive_agent_environment

    assert derive_agent_environment({"environments": [{"name": "production"}]}) == "live"


def test_derive_agent_environment_both():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import derive_agent_environment

    assert derive_agent_environment({"environments": [{"name": "draft"}, {"name": "prod"}]}) == "both"


def test_derive_agent_environment_empty():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.status import derive_agent_environment

    assert derive_agent_environment({}) == "unknown"
    assert derive_agent_environment({"environments": []}) == "unknown"


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
    from lfx.services.adapters.deployment.exceptions import DeploymentConflictError, InvalidContentError

    assert not is_retryable_create_exception(DeploymentConflictError())
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
    from lfx.services.adapters.deployment.exceptions import raise_for_status_and_detail

    # status_code=404 raises DeploymentNotFoundError regardless of detail text
    with pytest.raises(DeploymentNotFoundError):
        raise_for_status_and_detail(status_code=404, detail="anything", message_prefix="test")

    # status_code=409 raises DeploymentConflictError regardless of detail text
    with pytest.raises(DeploymentConflictError):
        raise_for_status_and_detail(status_code=409, detail="anything", message_prefix="test")

    # String heuristics still work as fallback for unmapped/None status codes
    with pytest.raises(DeploymentNotFoundError):
        raise_for_status_and_detail(status_code=None, detail="agent not found", message_prefix="test")
    with pytest.raises(DeploymentConflictError):
        raise_for_status_and_detail(status_code=None, detail="resource already exists", message_prefix="test")


# ---------------------------------------------------------------------------
# Test Coverage Gap #1: create — 409 conflict via ClientAPIException
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_maps_409_conflict_to_deployment_conflict_error(monkeypatch):
    """Create raises DeploymentConflictError when retry_create gets a 409 from the provider."""
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return SimpleNamespace(
            agent=FakeAgentClient({"id": "dep-1", "tools": []}),
            tool=FakeToolClient([]),
            connections=FakeConnectionsClient(),
        )

    async def mock_process_config(*args, **kwargs):  # noqa: ARG001
        response = SimpleNamespace(status_code=409, text='{"detail":"already exists"}')
        raise ClientAPIException(response=response)

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.service.process_config",
        mock_process_config,
    )

    with pytest.raises(DeploymentConflictError, match="already exist"):
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my_deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                    provider_spec={"resource_name_prefix": "lf_test_"},
                ),
            ),
        )


@pytest.mark.anyio
async def test_create_maps_422_to_invalid_content_error(monkeypatch):
    """Create raises InvalidContentError when retry_create gets a 422 from the provider."""
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return SimpleNamespace(
            agent=FakeAgentClient({"id": "dep-1", "tools": []}),
            tool=FakeToolClient([]),
            connections=FakeConnectionsClient(),
        )

    async def mock_process_config(*args, **kwargs):  # noqa: ARG001
        response = SimpleNamespace(status_code=422, text='{"detail":"validation error"}')
        raise ClientAPIException(response=response)

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.service.process_config",
        mock_process_config,
    )

    with pytest.raises(InvalidContentError, match="unprocessable"):
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my_deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                    provider_spec={"resource_name_prefix": "lf_test_"},
                ),
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
        provider_spec={"resource_name_prefix": "lf_test_"},
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
    """create_agent_run_result raises DeploymentError when response has no run_id."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    with pytest.raises(DeploymentError, match="did not return a run_id"):
        create_agent_run_result({"status": "accepted"})


def test_create_agent_run_result_extracts_run_id():
    """create_agent_run_result successfully extracts run_id from response."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    result = create_agent_run_result({"status": "accepted", "run_id": "run-123"})
    assert result["run_id"] == "run-123"
    assert result["status"] == "accepted"


def test_create_agent_run_result_falls_back_to_id_field():
    """create_agent_run_result uses 'id' field when 'run_id' is absent."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    result = create_agent_run_result({"status": "running", "id": "id-456"})
    assert result["run_id"] == "id-456"


# ---------------------------------------------------------------------------
# Additional coverage: _require_single_deployment_id — multiple IDs
# ---------------------------------------------------------------------------


def test_require_single_deployment_id_rejects_multiple_ids():
    """_require_single_deployment_id raises InvalidContentError for multiple IDs."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import _require_single_deployment_id

    params = ConfigListParams(deployment_ids=["id-1", "id-2"])
    with pytest.raises(InvalidContentError, match="exactly one deployment_id"):
        _require_single_deployment_id(params, resource_label="config")


# ---------------------------------------------------------------------------
# Additional coverage: exception chain preserved (from exc, not from None)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_preserves_exception_chain_on_unexpected_error(monkeypatch):
    """Create preserves exception chain with 'from exc' instead of 'from None'."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    original_error = RuntimeError("unexpected db error")

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        raise original_error

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    with pytest.raises(DeploymentError) as exc_info:
        await service.create(
            user_id="user-1",
            db=object(),
            payload=DeploymentCreate(
                spec=BaseDeploymentData(
                    name="my_deployment",
                    description="desc",
                    type=DeploymentType.AGENT,
                    provider_spec={"resource_name_prefix": "lf_test_"},
                ),
            ),
        )

    assert exc_info.value.__cause__ is original_error


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


def test_ensure_dict_logs_warning_on_non_dict(caplog):
    """_ensure_dict logs a warning when replacing a non-dict value."""
    import logging

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import _ensure_dict

    parent = {"binding": "not a dict"}
    with caplog.at_level(logging.WARNING):
        result = _ensure_dict(parent, "binding")
    assert result == {}
    assert parent["binding"] == {}
    assert "Expected dict" in caplog.text
    assert "str" in caplog.text

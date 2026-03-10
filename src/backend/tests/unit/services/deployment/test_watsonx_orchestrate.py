from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from uuid import UUID

import langflow.services.adapters.deployment.watsonx_orchestrate.core.tools as tools_module
import langflow.services.adapters.deployment.watsonx_orchestrate.service as service_module
import langflow.services.adapters.deployment.watsonx_orchestrate.utils as utils_module
import pytest
from fastapi import HTTPException, status
from langflow.services.adapters.deployment.watsonx_orchestrate import (
    WatsonxOrchestrateDeploymentService,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOCredentials
from lfx.services.adapters.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    InvalidContentError,
    InvalidDeploymentOperationError,
)
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    BaseFlowArtifact,
    ConfigDeploymentBindingUpdate,
    ConfigItem,
    DeploymentConfig,
    DeploymentCreate,
    DeploymentListParams,
    DeploymentType,
    DeploymentUpdate,
    EnvVarValueSpec,
    ExecutionCreate,
    SnapshotItems,
)


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
        self._tools = tools
        self._existing_names = existing_names or set()
        self.delete_calls: list[str] = []

    def get_drafts_by_ids(self, tool_ids: list[str]):  # noqa: ARG002
        return self._tools

    def get_draft_by_name(self, tool_name: str):
        if tool_name in self._existing_names:
            return [{"name": tool_name}]
        return []

    def delete(self, tool_id: str):
        self.delete_calls.append(tool_id)


class FakeConnectionsClient:
    def __init__(self, existing_app_id: str | None = None):
        self._existing_app_id = existing_app_id
        self.delete_calls: list[str] = []
        self.delete_credentials_calls: list[tuple[str, object, bool]] = []

    def get_draft_by_app_id(self, app_id: str):
        if self._existing_app_id and app_id == self._existing_app_id:
            return SimpleNamespace(connection_id="conn-1")
        return None

    def get_config(self, app_id: str, env):  # noqa: ARG002
        return SimpleNamespace(security_scheme="key_value")

    def get_credentials(self, app_id: str, env, *, use_app_credentials: bool):  # noqa: ARG002
        return {"runtime_credentials": {"TOKEN": "value"}}

    def delete_credentials(self, app_id: str, env, *, use_app_credentials: bool):
        self.delete_credentials_calls.append((app_id, env, use_app_credentials))

    def delete(self, app_id: str):
        self.delete_calls.append(app_id)


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

    async def mock_create_config(*, config, user_id, db, client_cache):  # noqa: ARG001
        captured["name"] = config.name
        captured["env_vars"] = config.environment_variables
        return config.name

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.core.config.create_config",
        mock_create_config,
    )

    app_id = await process_config(
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
        client_cache={},
    )

    assert app_id == "my_deployment"
    assert captured["name"] == "my_deployment"
    assert captured["env_vars"] is None


@pytest.mark.anyio
async def test_process_config_rejects_reference_id():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import process_config

    with pytest.raises(InvalidDeploymentOperationError, match="Config reference binding is not supported"):
        await process_config(
            user_id="user-1",
            db=object(),
            deployment_name="my_deployment",
            config=ConfigItem(reference_id="existing-config"),
            client_cache={},
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

    def should_not_be_called(**kwargs):  # noqa: ARG001
        msg = "_assert_create_resources_available should not be called"
        raise AssertionError(msg)

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(
        service_module,
        "assert_create_resources_available",
        should_not_be_called,
    )

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
async def test_update_deployment_denies_config_replacement(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient(
            [
                {
                    "id": "tool-1",
                    "binding": {"langflow": {"connections": {"existing-config": "conn-1"}}},
                }
            ]
        ),
        connections=FakeConnectionsClient(existing_app_id="existing-config"),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    update_data = DeploymentUpdate(config=ConfigDeploymentBindingUpdate(config_id="replacement-config"))

    with pytest.raises(InvalidDeploymentOperationError, match="Replacing or unbinding deployment"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=update_data,
            db=object(),
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
async def test_update_deployment_denies_config_unbind(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": ["tool-1"]}),
        tool=FakeToolClient(
            [
                {
                    "id": "tool-1",
                    "binding": {"langflow": {"connections": {"existing-config": "conn-1"}}},
                }
            ]
        ),
        connections=FakeConnectionsClient(existing_app_id="existing-config"),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)

    update_data = DeploymentUpdate(config=ConfigDeploymentBindingUpdate(config_id=None))

    with pytest.raises(InvalidDeploymentOperationError, match="Replacing or unbinding deployment"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=update_data,
            db=object(),
        )


@pytest.mark.anyio
async def test_assert_create_resources_available_rejects_existing_agent():
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(
            {"id": "dep-1", "tools": []},
            listed_agents=[{"id": "dep-1", "name": "my_deployment"}],
        ),
        connections=FakeConnectionsClient(),
        tool=FakeToolClient([]),
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import assert_create_resources_available

    with pytest.raises(DeploymentConflictError, match="Deployment 'my_deployment' already exists"):
        await assert_create_resources_available(
            clients=fake_clients,
            deployment_name="my_deployment",
            app_id="my_deployment_app_id",
        )


@pytest.mark.anyio
async def test_assert_create_resources_available_rejects_existing_config():
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        connections=FakeConnectionsClient(existing_app_id="my_deployment"),
        tool=FakeToolClient([]),
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import assert_create_resources_available

    with pytest.raises(DeploymentConflictError, match="Deployment config 'my_deployment' already exists"):
        await assert_create_resources_available(
            clients=fake_clients,
            deployment_name="my_deployment",
            app_id="my_deployment",
        )


@pytest.mark.anyio
async def test_assert_create_resources_available_rejects_existing_tool_name():
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        connections=FakeConnectionsClient(),
        tool=FakeToolClient([], existing_names={"my_tool"}),
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import assert_create_resources_available

    with pytest.raises(DeploymentConflictError, match="Deployment snapshot 'my_tool' already exists"):
        await assert_create_resources_available(
            clients=fake_clients,
            deployment_name="my_deployment",
            app_id="my_deployment_app_id",
            snapshot_tool_names=["my_tool"],
        )


@pytest.mark.anyio
async def test_process_raw_flows_with_app_id_awaits_connection_validation(monkeypatch):
    from langflow.services.adapters.deployment.watsonx_orchestrate.core import tools as tools_core_module

    fake_clients = SimpleNamespace(
        tool=SimpleNamespace(),
        connections=SimpleNamespace(),
    )
    captured: dict[str, object] = {}

    async def mock_get_provider_clients(*, user_id, db, client_cache):  # noqa: ARG001
        return fake_clients

    async def mock_validate_connection(connections_client, *, app_id):  # noqa: ARG001
        return SimpleNamespace(connection_id="conn-123")

    async def mock_create_and_upload_wxo_flow_tools(
        *,
        clients,
        flow_payloads,
        connections,
        app_id=None,
        tool_name_prefix,
    ):
        captured["clients"] = clients
        captured["flow_payloads"] = flow_payloads
        captured["connections"] = connections
        captured["app_id"] = app_id
        captured["tool_name_prefix"] = tool_name_prefix
        return ["tool-1"]

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.client.get_provider_clients",
        mock_get_provider_clients,
    )
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
        user_id="user-1",
        app_id="app-1",
        flows=[],
        db=object(),
        tool_name_prefix="lf_test_",
        client_cache={},
    )

    assert result == ["tool-1"]
    assert captured["connections"] == {"app-1": "conn-123"}
    assert captured["app_id"] == "app-1"
    assert captured["tool_name_prefix"] == "lf_test_"


def test_prefix_flow_global_variable_references_rewrites_load_from_db_values():
    flow_definition = {
        "data": {
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {
                                    "load_from_db": True,
                                    "value": "OPENAI_API_KEY",
                                },
                                "already_prefixed": {
                                    "load_from_db": True,
                                    "value": "foo_ALREADY",
                                },
                                "plain_value": {
                                    "load_from_db": False,
                                    "value": "DO_NOT_TOUCH",
                                },
                            }
                        }
                    }
                }
            ]
        }
    }

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import (
        prefix_flow_global_variable_references,
    )

    updated = prefix_flow_global_variable_references(flow_definition, app_id="foo")

    template = updated["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] == "foo_OPENAI_API_KEY"
    assert template["already_prefixed"]["value"] == "foo_ALREADY"
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

    async def mock_assert_create_resources_available(*, clients, deployment_name, app_id, snapshot_tool_names=None):  # noqa: ARG001
        captured["deployment_name"] = deployment_name
        captured["app_id"] = app_id
        captured["snapshot_tool_names"] = snapshot_tool_names

    monkeypatch.setattr(
        service_module,
        "assert_create_resources_available",
        mock_assert_create_resources_available,
    )

    async def mock_process_config(user_id, db, deployment_name, config, *, client_cache):  # noqa: ARG001
        captured["config_deployment_name"] = deployment_name
        return deployment_name

    monkeypatch.setattr(
        service_module,
        "process_config",
        mock_process_config,
    )

    async def mock_process_raw_flows_with_app_id(
        user_id,  # noqa: ARG001
        app_id,
        flows,
        db,  # noqa: ARG001
        tool_name_prefix,
        *,
        client_cache,  # noqa: ARG001
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
    monkeypatch.setattr(
        utils_module.secrets,
        "choice",
        lambda values: values[0],
    )
    monkeypatch.setattr(
        utils_module,
        "uuid4",
        lambda: SimpleNamespace(hex="abcdef123456"),
    )

    deployment_payload = DeploymentCreate(
        spec=BaseDeploymentData(name="my deployment", description="desc", type=DeploymentType.AGENT),
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
    assert result.name == "my deployment"
    assert captured["deployment_name"] == "lf_abcdef_my_deployment"
    assert captured["app_id"] == "lf_abcdef_my_deployment_ignored_app_id"
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

    async def mock_assert_create_resources_available(*, clients, deployment_name, app_id, snapshot_tool_names=None):  # noqa: ARG001
        captured["deployment_name"] = deployment_name
        captured["app_id"] = app_id
        captured["snapshot_tool_names"] = snapshot_tool_names

    monkeypatch.setattr(
        service_module,
        "assert_create_resources_available",
        mock_assert_create_resources_available,
    )

    async def mock_process_config(user_id, db, deployment_name, config, *, client_cache):  # noqa: ARG001
        captured["config_deployment_name"] = deployment_name
        return deployment_name

    monkeypatch.setattr(
        service_module,
        "process_config",
        mock_process_config,
    )

    async def mock_process_raw_flows_with_app_id(
        user_id,  # noqa: ARG001
        app_id,
        flows,
        db,  # noqa: ARG001
        tool_name_prefix,
        *,
        client_cache,  # noqa: ARG001
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
            provider_spec={"global_resource_name_prefix": "idempotent_abc_"},
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
    assert result.name == "my deployment"
    assert captured["deployment_name"] == "idempotent_abc_my_deployment"
    assert captured["app_id"] == "idempotent_abc_my_deployment_ignored_app_id"
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

    async def mock_assert_create_resources_available(*, clients, deployment_name, app_id, snapshot_tool_names=None):  # noqa: ARG001
        return None

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(
        service_module,
        "assert_create_resources_available",
        mock_assert_create_resources_available,
    )

    async def mock_process_config(user_id, db, deployment_name, config, *, client_cache):  # noqa: ARG001
        return deployment_name

    monkeypatch.setattr(
        service_module,
        "process_config",
        mock_process_config,
    )

    async def mock_process_raw_flows_with_app_id(
        user_id,  # noqa: ARG001
        app_id,  # noqa: ARG001
        flows,  # noqa: ARG001
        db,  # noqa: ARG001
        tool_name_prefix,  # noqa: ARG001
        *,
        client_cache,  # noqa: ARG001
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
    monkeypatch.setattr(
        utils_module.secrets,
        "choice",
        lambda values: values[0],
    )
    monkeypatch.setattr(
        utils_module,
        "uuid4",
        lambda: SimpleNamespace(hex="abcdef123456"),
    )

    deployment_payload = DeploymentCreate(
        spec=BaseDeploymentData(name="my deployment", description="desc", type=DeploymentType.AGENT),
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

    result = await service.get_status(user_id="user-1", deployment_id="dep-1", db=object())
    assert result.provider_data["status"] == "not found"


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

    auth = get_authenticator("https://api.us-south.cloud.ibm.com", "test-key")
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


def test_resolve_resource_name_prefix_uses_caller_provided_prefix():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import resolve_resource_name_prefix

    assert resolve_resource_name_prefix(caller_prefix="custom_abc_") == "custom_abc_"


def test_resolve_resource_name_prefix_falls_back_to_random():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import resolve_resource_name_prefix

    prefix = resolve_resource_name_prefix()
    assert prefix.startswith("lf_")
    assert prefix.endswith("_")


def test_resolve_resource_name_prefix_falls_back_when_none():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import resolve_resource_name_prefix

    prefix = resolve_resource_name_prefix(caller_prefix=None)
    assert prefix.startswith("lf_")


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


def test_dedupe_list():
    from langflow.services.adapters.deployment.watsonx_orchestrate.utils import dedupe_list

    assert dedupe_list(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert dedupe_list([]) == []


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


def test_create_agent_run_result_empty():
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.execution import create_agent_run_result

    assert create_agent_run_result(None) == {"status": "accepted"}
    assert create_agent_run_result({}) == {"status": "accepted"}


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


def test_wxo_credentials_repr_masks_api_key():
    creds = WxOCredentials(instance_url="https://example.com", api_key="sk-abcdef12345")
    repr_str = repr(creds)
    assert "****" in repr_str
    assert "sk-abcdef12345" not in repr_str
    assert "abcdef" not in repr_str


# ---------------------------------------------------------------------------
# NotImplementedError stubs
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_redeploy_raises_not_implemented():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    with pytest.raises(NotImplementedError):
        await service.redeploy(user_id="user-1", deployment_id="dep-1", db=object())


@pytest.mark.anyio
async def test_duplicate_raises_not_implemented():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    with pytest.raises(NotImplementedError):
        await service.duplicate(user_id="user-1", deployment_id="dep-1", db=object())


@pytest.mark.anyio
async def test_teardown_clears_client_cache():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    service._client_managers["test"] = SimpleNamespace()
    await service.teardown()
    assert len(service._client_managers) == 0

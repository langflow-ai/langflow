from __future__ import annotations

import importlib.metadata as md
from types import SimpleNamespace
from uuid import UUID

import langflow.services.adapters.deployment.watsonx_orchestrate.core.tools as tools_module
import langflow.services.adapters.deployment.watsonx_orchestrate.service as service_module
import pytest
from langflow.services.adapters.deployment.watsonx_orchestrate import (
    WatsonxOrchestrateDeploymentService,
)
from lfx.services.adapters.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    InvalidContentError,
    InvalidDeploymentOperationError,
)
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
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


@pytest.mark.anyio
async def test_process_config_uses_raw_payload_but_overrides_name(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    captured = {}

    async def mock_create_config(*, config, user_id, db, provider_name, client_cache):  # noqa: ARG001
        captured["name"] = config.name
        captured["env_vars"] = config.environment_variables

    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.core.config.create_config",
        mock_create_config,
    )

    app_id = await service._process_config(
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
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    with pytest.raises(InvalidDeploymentOperationError, match="Config reference binding is not supported"):
        await service._process_config(
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

    with pytest.raises(DeploymentConflictError, match="Replacing deployment configuration/connection"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=update_data,
            db=object(),
        )


@pytest.mark.anyio
async def test_list_deployments_filters_with_provider_draft_filters(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(
            {"id": "dep-1", "tools": []},
            listed_agents=[
                {"id": "dep-1", "name": "deployment-1", "tools": []},
                {"id": "dep-2", "name": "deployment-2", "tools": []},
                {"id": "dep-3", "name": "deployment-3", "tools": []},
            ],
        ),
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
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

    with pytest.raises(DeploymentConflictError, match="Unbinding deployment configuration/connection"):
        await service.update(
            user_id="user-1",
            deployment_id="dep-1",
            payload=update_data,
            db=object(),
        )


def test_assert_create_resources_available_rejects_existing_agent():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())  # noqa: F841
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
        assert_create_resources_available(
            clients=fake_clients,
            deployment_name="my_deployment",
            app_id="my_deployment_app_id",
        )


def test_assert_create_resources_available_rejects_existing_config():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())  # noqa: F841
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        connections=FakeConnectionsClient(existing_app_id="my_deployment"),
        tool=FakeToolClient([]),
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import assert_create_resources_available

    with pytest.raises(DeploymentConflictError, match="Deployment config 'my_deployment' already exists"):
        assert_create_resources_available(
            clients=fake_clients,
            deployment_name="my_deployment",
            app_id="my_deployment",
        )


def test_assert_create_resources_available_rejects_existing_tool_name():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())  # noqa: F841
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        connections=FakeConnectionsClient(),
        tool=FakeToolClient([], existing_names={"my_tool"}),
    )

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import assert_create_resources_available

    with pytest.raises(DeploymentConflictError, match="Deployment snapshot 'my_tool' already exists"):
        assert_create_resources_available(
            clients=fake_clients,
            deployment_name="my_deployment",
            app_id="my_deployment_app_id",
            snapshot_tool_names=["my_tool"],
        )


def test_resolve_lfx_runner_requirement_uses_tool_runner_requirement(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())  # noqa: F841
    tool = SimpleNamespace(requirements=["lfx-nightly>=0.0.0"])
    tools_module._pin_requirement_name.cache_clear()

    def fake_version(package_name: str) -> str:
        assert package_name == "lfx-nightly"
        return "1.2.3"

    monkeypatch.setattr("langflow.services.adapters.deployment.watsonx_orchestrate.core.tools.md.version", fake_version)

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import resolve_lfx_runner_requirement

    assert resolve_lfx_runner_requirement(tool) == "lfx-nightly==1.2.3"


def test_resolve_lfx_runner_requirement_falls_back_to_installed_lfx(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())  # noqa: F841
    tool = SimpleNamespace(requirements=[])
    tools_module._pin_requirement_name.cache_clear()

    def fake_version(package_name: str) -> str:
        if package_name == "lfx-nightly":
            raise md.PackageNotFoundError
        if package_name == "lfx":
            return "0.9.0"
        raise md.PackageNotFoundError

    monkeypatch.setattr("langflow.services.adapters.deployment.watsonx_orchestrate.core.tools.md.version", fake_version)

    from langflow.services.adapters.deployment.watsonx_orchestrate.core.tools import resolve_lfx_runner_requirement

    assert resolve_lfx_runner_requirement(tool) == "lfx==0.9.0"


def test_prefix_flow_global_variable_references_rewrites_load_from_db_values():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())  # noqa: F841
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
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())  # noqa: F841
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
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())  # noqa: F841
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
    monkeypatch.setattr(
        tools_module,
        "uuid4",
        lambda: SimpleNamespace(hex="abcdef123456"),
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

    def mock_assert_create_resources_available(*, clients, deployment_name, app_id, snapshot_tool_names=None):  # noqa: ARG001
        captured["deployment_name"] = deployment_name
        captured["app_id"] = app_id
        captured["snapshot_tool_names"] = snapshot_tool_names

    monkeypatch.setattr(
        service_module,
        "assert_create_resources_available",
        mock_assert_create_resources_available,
    )

    async def mock_process_config(user_id, db, deployment_name, config, *, provider_name, client_cache):  # noqa: ARG001
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
        provider_name,  # noqa: ARG001
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
        service_module.secrets,
        "choice",
        lambda values: values[0],
    )
    monkeypatch.setattr(
        service_module,
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

    def mock_assert_create_resources_available(*, clients, deployment_name, app_id, snapshot_tool_names=None):  # noqa: ARG001
        return None

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(
        service_module,
        "assert_create_resources_available",
        mock_assert_create_resources_available,
    )

    async def mock_process_config(user_id, db, deployment_name, config, *, provider_name, client_cache):  # noqa: ARG001
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
        provider_name,  # noqa: ARG001
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
        service_module.secrets,
        "choice",
        lambda values: values[0],
    )
    monkeypatch.setattr(
        service_module,
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

    with pytest.raises(DeploymentError, match="error details: boom"):
        await service.create(
            user_id="user-1",
            payload=deployment_payload,
            db=object(),
        )


@pytest.mark.anyio
async def test_create_execution_posts_runs_payload(monkeypatch):
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
    assert fake_agent.post_calls
    path, payload = fake_agent.post_calls[0]
    assert path == "/runs?stream=false"
    assert payload["agent_id"] == "dep-1"
    assert payload["thread_id"] == "thread-123"
    assert payload["message"] == {"role": "user", "content": "hello from test"}


@pytest.mark.anyio
async def test_get_execution_returns_completed_output(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": []},
        get_payloads={
            "/runs/run-1": {"status": "completed", "agent_id": "dep-1", "output": "Final assistant response"},
        },
    )
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
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
    assert result.provider_result["output"] == "Final assistant response"


@pytest.mark.anyio
async def test_get_execution_fetches_message_when_no_run_output(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": []},
        get_payloads={
            "/runs/run-1": {"status": "completed", "agent_id": "dep-1"},
        },
    )
    fake_clients = SimpleNamespace(
        agent=fake_agent,
        tool=FakeToolClient([]),
        connections=FakeConnectionsClient(),
    )

    async def mock_get_provider_clients(*, user_id, db):  # noqa: ARG001
        return fake_clients

    monkeypatch.setattr(service, "_get_provider_clients", mock_get_provider_clients)
    monkeypatch.setattr(
        "langflow.services.adapters.deployment.watsonx_orchestrate.service.fetch_execution_message_output",
        lambda *_args, **_kwargs: "Message payload output",
    )

    result = await service.get_execution(
        user_id="user-1",
        db=object(),
        execution_id="run-1",
    )

    assert result.provider_result["status"] == "completed"
    assert result.provider_result["output"] == "Message payload output"


@pytest.mark.anyio
async def test_get_execution_requires_execution_id(monkeypatch):
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

    with pytest.raises(ValueError, match="execution_id"):
        await service.get_execution(
            user_id="user-1",
            db=object(),
            execution_id="",
        )

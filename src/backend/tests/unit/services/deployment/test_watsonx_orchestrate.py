from __future__ import annotations

import importlib.metadata as md
from types import SimpleNamespace

import langflow.services.deployment.watsonx_orchestrate as watsonx_orchestrate_module
import pytest
from langflow.services.deployment.watsonx_orchestrate import (
    WatsonxOrchestrateDeploymentService,
)
from lfx.services.deployment.exceptions import (
    DeploymentConflictError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)
from lfx.services.deployment.schema import (
    BaseConfigData,
    BaseFlowArtifact,
    ConfigDeploymentBindingUpdate,
    ConfigItem,
    DeploymentExecution,
    DeploymentExecutionStatus,
    DeploymentListParams,
    DeploymentType,
    DeploymentUpdate,
    EnvVarValueSpec,
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
    def __init__(self, tools: list[dict]):
        self._tools = tools

    def get_drafts_by_ids(self, tool_ids: list[str]):  # noqa: ARG002
        return self._tools


class FakeConnectionsClient:
    def __init__(self, existing_app_id: str | None = None):
        self._existing_app_id = existing_app_id

    def get_draft_by_app_id(self, app_id: str):
        if self._existing_app_id and app_id == self._existing_app_id:
            return SimpleNamespace(connection_id="conn-1")
        return None

    def get_config(self, app_id: str, env):  # noqa: ARG002
        return SimpleNamespace(security_scheme="key_value")

    def get_credentials(self, app_id: str, env, *, use_app_credentials: bool):  # noqa: ARG002
        return {"runtime_credentials": {"TOKEN": "value"}}


@pytest.mark.anyio
async def test_process_config_uses_raw_payload_but_overrides_name(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    captured = {}

    async def mock_create_config(*, config, user_id, db):  # noqa: ARG001
        captured["name"] = config.name
        captured["env_vars"] = config.environment_variables

    monkeypatch.setattr(service, "create_config", mock_create_config)

    app_id = await service._process_config(
        user_id="user-1",
        db=object(),
        deployment_name="my_deployment",
        config=ConfigItem(
            raw_payload=BaseConfigData(
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
async def test_resolve_runtime_credentials_supports_variable_and_raw_sources(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())

    async def mock_resolve_variable_value(variable_name: str, *, user_id, db):  # noqa: ARG001
        return f"resolved::{variable_name}"

    monkeypatch.setattr(service, "_resolve_variable_value", mock_resolve_variable_value)

    runtime_credentials = await service._resolve_runtime_credentials(
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
            update_data=update_data,
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
            update_data=update_data,
            db=object(),
        )


def test_assert_create_resources_available_rejects_existing_agent():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient(
            {"id": "dep-1", "tools": []},
            listed_agents=[{"id": "dep-1", "name": "my_deployment"}],
        ),
        connections=FakeConnectionsClient(),
        tool=FakeToolClient([]),
    )

    with pytest.raises(DeploymentConflictError, match="Deployment 'my_deployment' already exists"):
        service._assert_create_resources_available(
            clients=fake_clients,
            deployment_name="my_deployment",
        )


def test_assert_create_resources_available_rejects_existing_config():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_clients = SimpleNamespace(
        agent=FakeAgentClient({"id": "dep-1", "tools": []}),
        connections=FakeConnectionsClient(existing_app_id="my_deployment"),
        tool=FakeToolClient([]),
    )

    with pytest.raises(DeploymentConflictError, match="Deployment config 'my_deployment' already exists"):
        service._assert_create_resources_available(
            clients=fake_clients,
            deployment_name="my_deployment",
        )


def test_resolve_lfx_runner_requirement_uses_tool_runner_requirement(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    tool = SimpleNamespace(requirements=["lfx-nightly>=0.0.0"])
    watsonx_orchestrate_module._pin_requirement_name.cache_clear()

    def fake_version(package_name: str) -> str:
        assert package_name == "lfx-nightly"
        return "1.2.3"

    monkeypatch.setattr("langflow.services.deployment.watsonx_orchestrate.md.version", fake_version)

    assert service._resolve_lfx_runner_requirement(tool) == "lfx-nightly==1.2.3"


def test_resolve_lfx_runner_requirement_falls_back_to_installed_lfx(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    tool = SimpleNamespace(requirements=[])
    watsonx_orchestrate_module._pin_requirement_name.cache_clear()

    def fake_version(package_name: str) -> str:
        if package_name == "lfx-nightly":
            raise md.PackageNotFoundError
        if package_name == "lfx":
            return "0.9.0"
        raise md.PackageNotFoundError

    monkeypatch.setattr("langflow.services.deployment.watsonx_orchestrate.md.version", fake_version)

    assert service._resolve_lfx_runner_requirement(tool) == "lfx==0.9.0"


def test_prefix_flow_global_variable_references_rewrites_load_from_db_values():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
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

    updated = service._prefix_flow_global_variable_references(flow_definition, app_id="foo")

    template = updated["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] == "foo_OPENAI_API_KEY"
    assert template["already_prefixed"]["value"] == "foo_ALREADY"
    assert template["plain_value"]["value"] == "DO_NOT_TOUCH"


def test_create_wxo_flow_tool_requires_provider_data_project_id():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    flow_payload = BaseFlowArtifact(
        id="00000000-0000-0000-0000-000000000001",
        name="flow",
        description="desc",
        data={"nodes": [], "edges": []},
        tags=[],
    )

    with pytest.raises(
        InvalidContentError,
        match="Flow payload must include provider_data with a non-empty project_id",
    ):
        service._create_wxo_flow_tool(
            flow_payload=flow_payload,
            connections={},
        )


def test_create_wxo_flow_tool_prefixes_name_for_raw_payload(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
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
        watsonx_orchestrate_module,
        "create_langflow_tool",
        lambda **kwargs: fake_tool,  # noqa: ARG005
    )
    monkeypatch.setattr(service, "_build_langflow_artifact_bytes", lambda **kwargs: b"artifact")  # noqa: ARG005
    monkeypatch.setattr(
        watsonx_orchestrate_module,
        "uuid4",
        lambda: SimpleNamespace(hex="abcdef123456"),
    )

    tool_payload, artifact_bytes = service._create_wxo_flow_tool(
        flow_payload=flow_payload,
        connections={},
    )

    assert tool_payload["name"] == "lf_abcdef_basicllmwxo"
    assert tool_payload["binding"]["langflow"]["project_id"] == "project-123"
    assert artifact_bytes == b"artifact"


def test_create_wxo_flow_tool_does_not_prefix_flow_variables(monkeypatch):
    """With app_id set, flow variable names remain unprefixed (TRM exposes both)."""
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    flow_payload = BaseFlowArtifact(
        id="00000000-0000-0000-0000-000000000001",
        name="testflow",
        description="desc",
        data={
            "nodes": [
                {
                    "data": {
                        "node": {
                            "template": {
                                "api_key": {"load_from_db": True, "value": "OPENAI_API_KEY"},
                            }
                        }
                    }
                }
            ]
        },
        tags=[],
        provider_data={"project_id": "project-123"},
    )
    captured = {}

    def capture_build(**kwargs):
        captured["flow_definition"] = kwargs["flow_definition"]
        return b"artifact"

    fake_tool = SimpleNamespace(
        __tool_spec__=SimpleNamespace(
            model_dump=lambda **kwargs: {"name": "testflow"},
        ),
    )
    monkeypatch.setattr(
        watsonx_orchestrate_module,
        "create_langflow_tool",
        lambda **kwargs: fake_tool,
    )
    monkeypatch.setattr(service, "_build_langflow_artifact_bytes", capture_build)
    monkeypatch.setattr(
        watsonx_orchestrate_module,
        "uuid4",
        lambda: SimpleNamespace(hex="abcdef123456"),
    )

    service._create_wxo_flow_tool(
        flow_payload=flow_payload,
        connections={"my_app": "conn-1"},
        app_id="my_app",
    )

    template = captured["flow_definition"]["data"]["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] == "OPENAI_API_KEY"
    assert "my_app_OPENAI_API_KEY" not in str(template["api_key"]["value"])


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
        execution=DeploymentExecution(
            deployment_id="dep-1",
            deployment_type=DeploymentType.AGENT,
            input="hello from test",
            provider_input={"thread_id": "thread-123", "stream": False},
        ),
    )

    assert result.deployment_id == "dep-1"
    assert result.status == "accepted"
    assert fake_agent.post_calls
    path, payload = fake_agent.post_calls[0]
    assert path == "/runs?stream=false"
    assert payload["agent_id"] == "dep-1"
    assert payload["thread_id"] == "thread-123"
    assert payload["message"] == {"role": "user", "content": "hello from test"}


@pytest.mark.anyio
async def test_create_execution_rejects_non_agent_type():
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    with pytest.raises(InvalidDeploymentTypeError, match="supports only agent deployments"):
        await service.create_execution(
            user_id="user-1",
            db=object(),
            execution=DeploymentExecution(
                deployment_id="dep-1",
                deployment_type=DeploymentType.MCP,
                input="hello",
            ),
        )


@pytest.mark.anyio
async def test_get_execution_returns_completed_output(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": []},
        get_payloads={
            "/runs/run-1": {"status": "completed", "output": "Final assistant response"},
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
        execution_status=DeploymentExecutionStatus(
            deployment_id="dep-1",
            deployment_type=DeploymentType.AGENT,
            provider_input={"run_id": "run-1"},
        ),
    )

    assert result.status == "completed"
    assert result.output == "Final assistant response"


@pytest.mark.anyio
async def test_get_execution_fetches_message_when_no_run_output(monkeypatch):
    service = WatsonxOrchestrateDeploymentService(DummySettingsService())
    fake_agent = FakeAgentClient(
        {"id": "dep-1", "tools": []},
        get_payloads={
            "/runs/run-1": {"status": "completed"},
            "/threads/thread-1/messages/message-1": {"content": "Message payload output"},
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
        execution_status=DeploymentExecutionStatus(
            deployment_id="dep-1",
            deployment_type=DeploymentType.AGENT,
            provider_input={
                "run_id": "run-1",
                "thread_id": "thread-1",
                "message_id": "message-1",
            },
        ),
    )

    assert result.status == "completed"
    assert result.output == "Message payload output"


@pytest.mark.anyio
async def test_get_execution_requires_run_id(monkeypatch):
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

    with pytest.raises(ValueError, match="run_id"):
        await service.get_execution(
            user_id="user-1",
            db=object(),
            execution_status=DeploymentExecutionStatus(
                deployment_id="dep-1",
                deployment_type=DeploymentType.AGENT,
                provider_input={},
            ),
        )

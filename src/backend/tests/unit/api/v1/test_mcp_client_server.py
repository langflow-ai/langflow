"""Integration tests for lfx.mcp.server MCP tools.

Uses the client_fixture (real Langflow app via ASGITransport) — no mocking.
Tests the full roundtrip: MCP tool -> LangflowClient -> Langflow API -> DB.
"""

import pytest
from httpx import AsyncClient
from lfx.mcp import server as mcp_server_module
from lfx.mcp.client import LangflowClient


@pytest.fixture
async def mcp_client(client: AsyncClient, logged_in_headers):
    """Wire up a LangflowClient that uses the test's AsyncClient transport."""
    # Extract the token from logged_in_headers
    auth_header = logged_in_headers["Authorization"]
    access_token = auth_header.removeprefix("Bearer ")

    lf_client = LangflowClient(server_url="http://testserver", access_token=access_token)
    # Inject the test's AsyncClient so requests go through ASGITransport
    lf_client._http = client

    # Patch the module-level + contextvar state in server.py
    old_client = mcp_server_module._shared_client
    old_registry = mcp_server_module._shared_registry

    mcp_server_module._set_client(lf_client)
    mcp_server_module._shared_registry = None
    mcp_server_module._registry_var.set(None)

    yield lf_client

    # Restore
    if old_client is not None:
        mcp_server_module._set_client(old_client)
    else:
        mcp_server_module._shared_client = None
        mcp_server_module._client_var.set(None)
    mcp_server_module._shared_registry = old_registry
    mcp_server_module._registry_var.set(old_registry)
    # Don't close the injected client — the fixture owns it
    lf_client._http = None


# ---------------------------------------------------------------------------
# Flow tools
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestCreateFlow:
    async def test_create_flow(self):
        result = await mcp_server_module.create_flow("Test Flow", "A test")
        assert "id" in result
        assert result["name"] == "Test Flow"

    async def test_create_flow_default_name(self):
        result = await mcp_server_module.create_flow()
        assert result["name"] == "Untitled Flow"


@pytest.mark.usefixtures("mcp_client")
class TestListFlows:
    async def test_list_flows_empty(self):
        flows = await mcp_server_module.list_flows()
        # May contain example flows, but should be a list
        assert isinstance(flows, list)

    async def test_list_flows_after_create(self):
        await mcp_server_module.create_flow("ListTest")
        flows = await mcp_server_module.list_flows()
        names = [f["name"] for f in flows]
        assert "ListTest" in names


@pytest.mark.usefixtures("mcp_client")
class TestGetFlowInfo:
    async def test_get_flow_info(self):
        created = await mcp_server_module.create_flow("InfoTest", "desc")
        info = await mcp_server_module.get_flow_info(created["id"])
        assert info["id"] == created["id"]
        assert info["name"] == "InfoTest"
        assert info["node_count"] == 0
        assert info["edge_count"] == 0


@pytest.mark.usefixtures("mcp_client")
class TestDeleteFlow:
    async def test_delete_flow(self):
        created = await mcp_server_module.create_flow("DeleteMe")
        result = await mcp_server_module.delete_flow(created["id"])
        assert result["deleted"] == created["id"]

        # Verify it's gone
        with pytest.raises(RuntimeError, match="failed"):
            await mcp_server_module.get_flow_info(created["id"])


# ---------------------------------------------------------------------------
# Component tools
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestAddComponent:
    async def test_add_component(self):
        created = await mcp_server_module.create_flow("CompTest")
        result = await mcp_server_module.add_component(created["id"], "ChatInput")
        assert result["id"].startswith("ChatInput-")
        assert result["display_name"] == "Chat Input"

    async def test_add_unknown_component_raises(self):
        created = await mcp_server_module.create_flow("CompTest2")
        with pytest.raises(ValueError, match="Unknown component"):
            await mcp_server_module.add_component(created["id"], "TotallyFake")


@pytest.mark.usefixtures("mcp_client")
class TestRemoveComponent:
    async def test_remove_component(self):
        created = await mcp_server_module.create_flow("RemoveTest")
        comp = await mcp_server_module.add_component(created["id"], "ChatInput")
        result = await mcp_server_module.remove_component(created["id"], comp["id"])
        assert result["removed"] == comp["id"]

        # Verify it's gone
        components = await mcp_server_module.list_components(created["id"])
        assert len(components) == 0


@pytest.mark.usefixtures("mcp_client")
class TestListComponents:
    async def test_list_components(self):
        created = await mcp_server_module.create_flow("ListCompTest")
        await mcp_server_module.add_component(created["id"], "ChatInput")
        await mcp_server_module.add_component(created["id"], "ChatOutput")
        components = await mcp_server_module.list_components(created["id"])
        types = {c["type"] for c in components}
        assert "ChatInput" in types
        assert "ChatOutput" in types


@pytest.mark.usefixtures("mcp_client")
class TestGetComponentInfo:
    async def test_get_component_info(self):
        created = await mcp_server_module.create_flow("GetCompTest")
        comp = await mcp_server_module.add_component(created["id"], "ChatInput")
        info = await mcp_server_module.get_component_info(created["id"], comp["id"])
        assert info["id"] == comp["id"]
        assert info["type"] == "ChatInput"
        assert "params" in info

    async def test_get_component_info_redacts_secrets(self):
        created = await mcp_server_module.create_flow("RedactTest")
        comp = await mcp_server_module.add_component(created["id"], "OpenAIModel")
        # Configure an API key
        await mcp_server_module.configure_component(
            created["id"],
            comp["id"],
            {"api_key": "sk-test-fake-12345"},  # pragma: allowlist secret
        )
        info = await mcp_server_module.get_component_info(created["id"], comp["id"])
        assert info["params"]["api_key"] == "***REDACTED***"

    async def test_get_single_field(self):
        created = await mcp_server_module.create_flow("FieldTest")
        comp = await mcp_server_module.add_component(created["id"], "ChatInput")
        await mcp_server_module.configure_component(created["id"], comp["id"], {"input_value": "Hello world"})
        result = await mcp_server_module.get_component_info(created["id"], comp["id"], field_name="input_value")
        assert result["component_id"] == comp["id"]
        assert result["field_name"] == "input_value"
        assert result["value"] == "Hello world"
        assert "display_name" in result
        assert "type" in result

    async def test_get_single_field_unknown_raises(self):
        created = await mcp_server_module.create_flow("FieldTest2")
        comp = await mcp_server_module.add_component(created["id"], "ChatInput")
        with pytest.raises(ValueError, match="Field 'nonexistent' not found"):
            await mcp_server_module.get_component_info(created["id"], comp["id"], field_name="nonexistent")

    async def test_get_single_field_redacts_secret(self):
        created = await mcp_server_module.create_flow("FieldRedact")
        comp = await mcp_server_module.add_component(created["id"], "OpenAIModel")
        await mcp_server_module.configure_component(
            created["id"],
            comp["id"],
            {"api_key": "sk-test-fake"},  # pragma: allowlist secret
        )
        result = await mcp_server_module.get_component_info(created["id"], comp["id"], field_name="api_key")
        assert result["value"] == "***REDACTED***"


# ---------------------------------------------------------------------------
# Configure component
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestConfigureComponent:
    async def test_configure_static_param(self):
        created = await mcp_server_module.create_flow("ConfigTest")
        comp = await mcp_server_module.add_component(created["id"], "ChatInput")
        result = await mcp_server_module.configure_component(created["id"], comp["id"], {"input_value": "Hello"})
        assert result["component_id"] == comp["id"]
        assert "input_value" in result["configured"]

        # Verify the value was set
        info = await mcp_server_module.get_component_info(created["id"], comp["id"])
        assert info["params"]["input_value"] == "Hello"

    async def test_configure_nonexistent_component_raises(self):
        created = await mcp_server_module.create_flow("ConfigTest2")
        with pytest.raises(ValueError, match="Component not found"):
            await mcp_server_module.configure_component(created["id"], "NoSuch-12345", {"key": "val"})

    async def test_configure_dynamic_field(self):
        """Fields with real_time_refresh trigger /custom_component/update."""
        created = await mcp_server_module.create_flow("DynamicTest")
        comp = await mcp_server_module.add_component(created["id"], "OpenAIModel")
        # model_name has real_time_refresh=True
        result = await mcp_server_module.configure_component(created["id"], comp["id"], {"model_name": "gpt-4o"})
        assert "model_name" in result["configured"]


# ---------------------------------------------------------------------------
# Connection tools
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestConnectComponents:
    async def test_connect_components(self):
        created = await mcp_server_module.create_flow("ConnectTest")
        c1 = await mcp_server_module.add_component(created["id"], "ChatInput")
        c2 = await mcp_server_module.add_component(created["id"], "ChatOutput")
        result = await mcp_server_module.connect_components(created["id"], c1["id"], "message", c2["id"], "input_value")
        assert result["source_id"] == c1["id"]
        assert result["target_id"] == c2["id"]

        # Verify via flow info
        info = await mcp_server_module.get_flow_info(created["id"])
        assert info["edge_count"] == 1

    async def test_connect_component_as_tool_auto_enables_tool_mode(self):
        created = await mcp_server_module.create_flow("ToolModeAutoTest")
        url_comp = await mcp_server_module.add_component(created["id"], "URLComponent")
        agent = await mcp_server_module.add_component(created["id"], "Agent")

        # Before: normal outputs
        info = await mcp_server_module.get_component_info(created["id"], url_comp["id"])
        output_names = [o["name"] for o in info["outputs"]]
        assert "component_as_tool" not in output_names

        # Connect via component_as_tool — should auto-enable tool_mode
        await mcp_server_module.connect_components(
            created["id"], url_comp["id"], "component_as_tool", agent["id"], "tools"
        )

        # After: tool_mode enabled, output switched
        info = await mcp_server_module.get_component_info(created["id"], url_comp["id"])
        output_names = [o["name"] for o in info["outputs"]]
        assert output_names == ["component_as_tool"]


@pytest.mark.usefixtures("mcp_client")
class TestDisconnectComponents:
    async def test_disconnect_components(self):
        created = await mcp_server_module.create_flow("DisconnectTest")
        c1 = await mcp_server_module.add_component(created["id"], "ChatInput")
        c2 = await mcp_server_module.add_component(created["id"], "ChatOutput")
        await mcp_server_module.connect_components(created["id"], c1["id"], "message", c2["id"], "input_value")
        result = await mcp_server_module.disconnect_components(created["id"], c1["id"], c2["id"])
        assert result["removed_count"] == 1

        # Verify
        info = await mcp_server_module.get_flow_info(created["id"])
        assert info["edge_count"] == 0

    async def test_disconnect_no_match_raises(self):
        created = await mcp_server_module.create_flow("DisconnectNoMatch")
        c1 = await mcp_server_module.add_component(created["id"], "ChatInput")
        c2 = await mcp_server_module.add_component(created["id"], "ChatOutput")
        # No connection exists between them
        with pytest.raises(ValueError, match="No connections found"):
            await mcp_server_module.disconnect_components(created["id"], c1["id"], c2["id"])


# ---------------------------------------------------------------------------
# Search / Describe (registry)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestSearchComponentTypes:
    async def test_search_all(self):
        results = await mcp_server_module.search_component_types()
        assert len(results) > 0

    async def test_search_by_query(self):
        results = await mcp_server_module.search_component_types(query="Chat")
        types = {r["type"] for r in results}
        assert "ChatInput" in types

    async def test_search_by_category(self):
        results = await mcp_server_module.search_component_types(category="inputs")
        assert all(r["category"] == "inputs" for r in results)

    async def test_search_by_output_type(self):
        results = await mcp_server_module.search_component_types(output_type="LanguageModel")
        assert len(results) > 0
        types = {r["type"] for r in results}
        assert "OpenAIModel" in types


@pytest.mark.usefixtures("mcp_client")
class TestDescribeComponentType:
    async def test_describe_chat_input(self):
        info = await mcp_server_module.describe_component_type("ChatInput")
        assert info["type"] == "ChatInput"
        assert "inputs" in info
        assert "outputs" in info

    async def test_describe_advanced_fields(self):
        info = await mcp_server_module.describe_component_type("OpenAIModel")
        assert "advanced_fields" in info
        assert isinstance(info["advanced_fields"], list)
        # Advanced fields should not appear in inputs or fields
        advanced = set(info["advanced_fields"])
        input_names = {i["name"] for i in info.get("inputs", [])}
        field_names = {f["name"] for f in info.get("fields", [])}
        assert not advanced & input_names
        assert not advanced & field_names

    async def test_describe_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown component"):
            await mcp_server_module.describe_component_type("TotallyFake")


# ---------------------------------------------------------------------------
# Flow duplication / starter projects
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestCreateFlowFromSpec:
    async def test_create_flow_from_spec(self):
        spec = """\
name: SpecTest
description: A test flow

nodes:
  A: ChatInput
  B: ChatOutput

edges:
  A.message -> B.input_value
"""
        result = await mcp_server_module.create_flow_from_spec(spec)
        assert result["name"] == "SpecTest"
        assert result["node_count"] == 2
        assert result["edge_count"] == 1
        assert "A" in result["node_id_map"]
        assert "B" in result["node_id_map"]
        assert "graph" in result

    async def test_create_flow_from_spec_with_config(self):
        spec = """\
name: SpecConfigTest

nodes:
  A: ChatInput
  B: ChatOutput

edges:
  A.message -> B.input_value

config:
  A.input_value: Hello from spec
"""
        result = await mcp_server_module.create_flow_from_spec(spec)
        info = await mcp_server_module.get_component_info(
            result["id"], result["node_id_map"]["A"], field_name="input_value"
        )
        assert info["value"] == "Hello from spec"

    async def test_create_flow_from_spec_with_tool_mode(self):
        spec = """\
name: SpecToolTest

nodes:
  A: ChatInput
  B: Agent
  C: ChatOutput
  D: URLComponent

edges:
  A.message -> B.input_value
  D.component_as_tool -> B.tools
  B.response -> C.input_value
"""
        result = await mcp_server_module.create_flow_from_spec(spec)
        assert result["node_count"] == 4
        assert result["edge_count"] == 3
        # URLComponent should have tool_mode enabled
        url_info = await mcp_server_module.get_component_info(result["id"], result["node_id_map"]["D"])
        output_names = [o["name"] for o in url_info["outputs"]]
        assert output_names == ["component_as_tool"]

    async def test_create_flow_from_spec_unknown_node_in_config(self):
        spec = """\
name: BadConfig

nodes:
  A: ChatInput

config:
  Z.field: value
"""
        with pytest.raises(ValueError, match="unknown node 'Z'"):
            await mcp_server_module.create_flow_from_spec(spec)

    async def test_create_flow_from_spec_unknown_node_in_edge(self):
        spec = """\
name: BadEdge

nodes:
  A: ChatInput

edges:
  A.message -> Z.input_value
"""
        with pytest.raises(ValueError, match="unknown target 'Z'"):
            await mcp_server_module.create_flow_from_spec(spec)

    async def test_create_flow_from_spec_prompt_template_variables(self):
        """Prompt Template with {var} in template creates dynamic input fields."""
        spec = """\
name: PromptVarTest

nodes:
  A: ChatInput
  B: Prompt Template
  C: OpenAIModel
  D: ChatOutput

edges:
  A.message -> B.user_input
  B.prompt -> C.input_value
  C.text_output -> D.input_value

config:
  B.template: |
    Translate to French: {user_input}
"""
        result = await mcp_server_module.create_flow_from_spec(spec)
        assert result["node_count"] == 4
        assert result["edge_count"] == 3

        # Verify the dynamic field was created
        prompt_info = await mcp_server_module.get_component_info(result["id"], result["node_id_map"]["B"])
        assert "user_input" in prompt_info["params"]

    async def test_create_flow_from_spec_prompt_multiple_variables(self):
        """Prompt with multiple {vars} creates all corresponding fields."""
        spec = """\
name: MultiVarTest

nodes:
  A: Prompt Template

config:
  A.template: |
    {tone} translation of {text} to {language}
"""
        result = await mcp_server_module.create_flow_from_spec(spec)
        prompt_info = await mcp_server_module.get_component_info(result["id"], result["node_id_map"]["A"])
        assert "tone" in prompt_info["params"]
        assert "text" in prompt_info["params"]
        assert "language" in prompt_info["params"]

    async def test_create_flow_from_spec_coerces_numeric_config(self):
        spec = """\
name: CoerceTest

nodes:
  A: ChatInput
  B: ChatOutput

edges:
  A.message -> B.input_value

config:
  A.input_value: 42
"""
        result = await mcp_server_module.create_flow_from_spec(spec)
        info = await mcp_server_module.get_component_info(
            result["id"], result["node_id_map"]["A"], field_name="input_value"
        )
        assert info["value"] == 42


@pytest.mark.usefixtures("mcp_client")
class TestDuplicateFlow:
    async def test_duplicate_flow(self):
        created = await mcp_server_module.create_flow("OriginalFlow", "desc")
        await mcp_server_module.add_component(created["id"], "ChatInput")
        dup = await mcp_server_module.duplicate_flow(created["id"], "TheCopy")
        assert dup["name"] == "TheCopy"
        assert dup["id"] != created["id"]
        info = await mcp_server_module.get_flow_info(dup["id"])
        assert info["node_count"] == 1


@pytest.mark.usefixtures("mcp_client")
class TestStarterProjects:
    async def test_list_starter_projects(self):
        starters = await mcp_server_module.list_starter_projects()
        assert isinstance(starters, list)
        assert len(starters) > 0
        assert "name" in starters[0]
        assert "graph" in starters[0]

    async def test_use_starter_project(self):
        starters = await mcp_server_module.list_starter_projects()
        starter_name = starters[0]["name"]
        result = await mcp_server_module.use_starter_project(starter_name, "MyStarter")
        assert result["name"] == "MyStarter"
        info = await mcp_server_module.get_flow_info(result["id"])
        assert info["node_count"] > 0

    async def test_use_starter_project_unknown_raises(self):
        with pytest.raises(ValueError, match="not found"):
            await mcp_server_module.use_starter_project("NonexistentStarter")


# ---------------------------------------------------------------------------
# Graph repr
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestGraphRepr:
    async def test_get_flow_info_includes_graph(self):
        created = await mcp_server_module.create_flow("GraphTest")
        await mcp_server_module.add_component(created["id"], "ChatInput")
        info = await mcp_server_module.get_flow_info(created["id"])
        assert "graph" in info
        assert "ChatInput" in info["graph"]

    async def test_list_flows_includes_graph(self):
        await mcp_server_module.create_flow("GraphListTest")
        flows = await mcp_server_module.list_flows(query="GraphListTest")
        assert len(flows) >= 1
        assert "graph" in flows[0]


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestBatch:
    async def test_batch_build_flow(self):
        """Build a complete ChatInput -> ChatOutput flow in one batch call."""
        results = await mcp_server_module.batch(
            [
                {"tool": "create_flow", "args": {"name": "BatchTest"}},
                {"tool": "add_component", "args": {"flow_id": "$0.id", "component_type": "ChatInput"}},
                {"tool": "add_component", "args": {"flow_id": "$0.id", "component_type": "ChatOutput"}},
                {
                    "tool": "connect_components",
                    "args": {
                        "flow_id": "$0.id",
                        "source_id": "$1.id",
                        "source_output": "message",
                        "target_id": "$2.id",
                        "target_input": "input_value",
                    },
                },
                {"tool": "get_flow_info", "args": {"flow_id": "$0.id"}},
            ]
        )
        assert len(results) == 5
        assert results[0]["name"] == "BatchTest"
        assert results[1]["id"].startswith("ChatInput-")
        assert results[4]["node_count"] == 2
        assert results[4]["edge_count"] == 1

    async def test_batch_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="unknown tool"):
            await mcp_server_module.batch(
                [
                    {"tool": "nonexistent_tool", "args": {}},
                ]
            )

    async def test_batch_bad_ref_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            await mcp_server_module.batch(
                [
                    {"tool": "create_flow", "args": {"name": "RefTest"}},
                    {"tool": "get_flow_info", "args": {"flow_id": "$5.id"}},
                ]
            )


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


class TestRunFlow:
    async def test_run_simple_flow(self, mcp_client, created_api_key):
        """Build a ChatInput -> ChatOutput flow and run it via streaming."""
        mcp_client.api_key = created_api_key.api_key
        created = await mcp_server_module.create_flow("RunTest")
        c1 = await mcp_server_module.add_component(created["id"], "ChatInput")
        c2 = await mcp_server_module.add_component(created["id"], "ChatOutput")
        await mcp_server_module.connect_components(created["id"], c1["id"], "message", c2["id"], "input_value")
        result = await mcp_server_module.run_flow(created["id"], input_value="Hello from test")
        assert isinstance(result, dict)
        assert "outputs" in result

    async def test_stream_post_yields_events(self, mcp_client, created_api_key):
        """Verify stream_post yields SSE events from Langflow's streaming endpoint."""
        mcp_client.api_key = created_api_key.api_key
        created = await mcp_server_module.create_flow("StreamTest")
        c1 = await mcp_server_module.add_component(created["id"], "ChatInput")
        c2 = await mcp_server_module.add_component(created["id"], "ChatOutput")
        await mcp_server_module.connect_components(created["id"], c1["id"], "message", c2["id"], "input_value")

        request = {
            "input_value": "Hello streaming",
            "input_type": "chat",
            "output_type": "chat",
            "tweaks": {},
        }
        events = []
        async for event in mcp_client.stream_post(f"/run/{created['id']}?stream=true", json_data=request):
            events.append(event)
            if event.get("event") == "end":
                break

        assert len(events) > 0
        event_types = {e.get("event") for e in events}
        assert "end" in event_types


# ---------------------------------------------------------------------------
# Build results / component outputs
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestGetBuildResults:
    async def test_get_build_results_after_run(self, mcp_client, created_api_key):
        """After running a flow, get_build_results should return per-component data."""
        mcp_client.api_key = created_api_key.api_key
        created = await mcp_server_module.create_flow("BuildResultsTest")
        c1 = await mcp_server_module.add_component(created["id"], "ChatInput")
        c2 = await mcp_server_module.add_component(created["id"], "ChatOutput")
        await mcp_server_module.connect_components(created["id"], c1["id"], "message", c2["id"], "input_value")
        await mcp_server_module.run_flow(created["id"], input_value="Hello")

        results = await mcp_server_module.get_build_results(created["id"])
        assert isinstance(results, dict)
        assert "builds" in results
        # Should have build data for at least the components we added
        assert len(results["builds"]) > 0

    async def test_get_build_results_empty_flow(self):
        """A flow that hasn't been run should return empty builds."""
        created = await mcp_server_module.create_flow("NoBuildTest")
        results = await mcp_server_module.get_build_results(created["id"])
        assert results["builds"] == {}

    async def test_get_component_output_after_run(self, mcp_client, created_api_key):
        """After running, get_component_output should return a specific component's output."""
        mcp_client.api_key = created_api_key.api_key
        created = await mcp_server_module.create_flow("CompOutputTest")
        c1 = await mcp_server_module.add_component(created["id"], "ChatInput")
        c2 = await mcp_server_module.add_component(created["id"], "ChatOutput")
        await mcp_server_module.connect_components(created["id"], c1["id"], "message", c2["id"], "input_value")
        await mcp_server_module.run_flow(created["id"], input_value="Test message")

        output = await mcp_server_module.get_component_output(created["id"], c1["id"])
        assert isinstance(output, dict)
        assert "component_id" in output


# ---------------------------------------------------------------------------
# Validate flow
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestValidateFlow:
    async def test_validate_flow_returns_structured_result(self, mcp_client, created_api_key):
        """validate_flow should return structured result with valid, component_count, errors."""
        mcp_client.api_key = created_api_key.api_key
        created = await mcp_server_module.create_flow("ValidateOK")
        c1 = await mcp_server_module.add_component(created["id"], "ChatInput")
        c2 = await mcp_server_module.add_component(created["id"], "ChatOutput")
        await mcp_server_module.connect_components(created["id"], c1["id"], "message", c2["id"], "input_value")

        result = await mcp_server_module.validate_flow(created["id"])
        # Must return structured result with these keys
        assert "valid" in result
        assert isinstance(result["valid"], bool)
        if "component_count" in result:
            assert result["component_count"] >= 2
        if "errors" in result:
            assert isinstance(result["errors"], list)

    async def test_validate_empty_flow(self):
        """An empty flow should validate as valid (no components to fail)."""
        created = await mcp_server_module.create_flow("ValidateEmpty")
        result = await mcp_server_module.validate_flow(created["id"])
        assert result["valid"] is True
        assert result["component_count"] == 0


# ---------------------------------------------------------------------------
# Rename flow
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestRenameFlow:
    async def test_rename_flow_name(self):
        created = await mcp_server_module.create_flow("OldName")
        result = await mcp_server_module.rename_flow(created["id"], name="NewName")
        assert result["name"] == "NewName"

        # Verify via get_flow_info
        info = await mcp_server_module.get_flow_info(created["id"])
        assert info["name"] == "NewName"

    async def test_rename_flow_description(self):
        created = await mcp_server_module.create_flow("DescTest", "old desc")
        result = await mcp_server_module.rename_flow(created["id"], description="new desc")
        assert result["description"] == "new desc"

    async def test_rename_flow_no_args_raises(self):
        created = await mcp_server_module.create_flow("NoArgs")
        with pytest.raises(ValueError, match="Provide at least"):
            await mcp_server_module.rename_flow(created["id"])


# ---------------------------------------------------------------------------
# Export flow
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestExportFlow:
    async def test_export_flow_structure(self):
        created = await mcp_server_module.create_flow("ExportTest")
        await mcp_server_module.add_component(created["id"], "ChatInput")

        result = await mcp_server_module.export_flow(created["id"])
        assert result["id"] == created["id"]
        assert result["name"] == "ExportTest"
        assert "data" in result
        assert "nodes" in result["data"]
        assert len(result["data"]["nodes"]) == 1

    async def test_export_flow_redacts_secrets(self):
        """API keys in exported flow data should be redacted."""
        created = await mcp_server_module.create_flow("SecretTest")
        comp = await mcp_server_module.add_component(created["id"], "OpenAIModel")
        await mcp_server_module.configure_component(
            created["id"],
            comp["id"],
            {"api_key": "sk-test-fake-key-12345"},  # pragma: allowlist secret
        )

        result = await mcp_server_module.export_flow(created["id"])
        # Find the OpenAI node and check api_key is redacted
        for node in result["data"]["nodes"]:
            if node.get("data", {}).get("type") == "OpenAIModel":
                template = node["data"].get("node", {}).get("template", {})
                api_key_val = template.get("api_key", {}).get("value", "")
                assert api_key_val in {"***REDACTED***", ""}
                break


# ---------------------------------------------------------------------------
# Update flow from spec
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestUpdateFlowFromSpec:
    async def test_update_replaces_flow_content(self):
        """update_flow_from_spec should replace the flow's nodes and edges."""
        created = await mcp_server_module.create_flow("UpdateTest")
        await mcp_server_module.add_component(created["id"], "ChatInput")

        # Update to a different flow
        spec = """\
name: Updated Flow
nodes:
  A: ChatInput
  B: OpenAIModel
  C: ChatOutput
edges:
  A.message -> B.input_value
  B.text_output -> C.input_value
"""
        result = await mcp_server_module.update_flow_from_spec(created["id"], spec)
        assert result["id"] == created["id"]
        assert result["node_count"] == 3
        assert result["edge_count"] == 2
        assert "spec_summary" in result

    async def test_update_preserves_flow_id(self):
        """The flow ID should not change after update."""
        created = await mcp_server_module.create_flow("PreserveID")
        spec = "name: New\nnodes:\n  A: ChatInput"
        result = await mcp_server_module.update_flow_from_spec(created["id"], spec)
        assert result["id"] == created["id"]

    async def test_update_rejects_bad_edge_reference(self):
        """Edges referencing unknown nodes should raise."""
        created = await mcp_server_module.create_flow("BadEdge")
        spec = """\
name: Bad
nodes:
  A: ChatInput
edges:
  A.message -> Z.input_value
"""
        with pytest.raises(ValueError, match="unknown target"):
            await mcp_server_module.update_flow_from_spec(created["id"], spec)


# ---------------------------------------------------------------------------
# Freeze / unfreeze
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestFreezeComponent:
    async def test_freeze_and_unfreeze(self):
        created = await mcp_server_module.create_flow("FreezeTest")
        comp = await mcp_server_module.add_component(created["id"], "ChatInput")

        result = await mcp_server_module.freeze_component(created["id"], comp["id"])
        assert result["frozen"] == comp["id"]

        result = await mcp_server_module.unfreeze_component(created["id"], comp["id"])
        assert result["unfrozen"] == comp["id"]

    async def test_freeze_unknown_component_raises(self):
        created = await mcp_server_module.create_flow("FreezeUnknown")
        with pytest.raises(ValueError, match="not found"):
            await mcp_server_module.freeze_component(created["id"], "Fake-12345")


# ---------------------------------------------------------------------------
# Layout flow
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestLayoutFlow:
    async def test_layout_flow(self):
        created = await mcp_server_module.create_flow("LayoutTest")
        await mcp_server_module.add_component(created["id"], "ChatInput")
        await mcp_server_module.add_component(created["id"], "ChatOutput")

        result = await mcp_server_module.layout_flow_tool(created["id"])
        assert result["laid_out"] == created["id"]


# ---------------------------------------------------------------------------
# Components (merged search + describe)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestComponentsTool:
    async def test_search_mode(self):
        """Without component_type, should search."""
        results = await mcp_server_module.components(query="Chat")
        assert isinstance(results, list)
        types = {r["type"] for r in results}
        assert "ChatInput" in types

    async def test_describe_mode(self):
        """With component_type, should describe."""
        result = await mcp_server_module.components(component_type="ChatInput")
        assert isinstance(result, dict)
        assert result["type"] == "ChatInput"
        assert "outputs" in result
        assert "inputs" in result

    async def test_list_all(self):
        """No args should list all."""
        results = await mcp_server_module.components()
        assert isinstance(results, list)
        assert len(results) > 0


# ---------------------------------------------------------------------------
# Spec summary in responses
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mcp_client")
class TestSpecSummaryInResponses:
    async def test_get_flow_info_includes_spec_summary(self):
        created = await mcp_server_module.create_flow("SpecSummary")
        await mcp_server_module.add_component(created["id"], "ChatInput")
        info = await mcp_server_module.get_flow_info(created["id"])
        assert "spec_summary" in info
        assert "ChatInput" in info["spec_summary"]

    async def test_list_flows_includes_spec_summary(self):
        await mcp_server_module.create_flow("SpecSummaryList")
        flows = await mcp_server_module.list_flows(query="SpecSummaryList")
        assert len(flows) >= 1
        assert "spec_summary" in flows[0]

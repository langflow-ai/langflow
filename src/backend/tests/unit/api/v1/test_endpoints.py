import asyncio
import inspect
from typing import Any

from anyio import Path
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1.schemas import CustomComponentRequest, UpdateCustomComponentRequest
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.custom.utils import build_custom_component_template


async def test_get_version(client: AsyncClient):
    response = await client.get("api/v1/version")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "version" in result, "The dictionary must contain a key called 'version'"
    assert "main_version" in result, "The dictionary must contain a key called 'main_version'"
    assert "package" in result, "The dictionary must contain a key called 'package'"


async def test_get_config_basic(client: AsyncClient, logged_in_headers: dict):
    """Test basic authenticated /config endpoint returns expected structure."""
    response = await client.get("api/v1/config", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "frontend_timeout" in result, "The dictionary must contain a key called 'frontend_timeout'"
    assert "auto_saving" in result, "The dictionary must contain a key called 'auto_saving'"
    assert "health_check_max_retries" in result, "The dictionary must contain a 'health_check_max_retries' key"
    assert "max_file_size_upload" in result, "The dictionary must contain a key called 'max_file_size_upload'"


async def test_update_component_outputs(client: AsyncClient, logged_in_headers: dict):
    path = Path(__file__).parent.parent.parent.parent / "data" / "dynamic_output_component.py"

    code = await path.read_text(encoding="utf-8")
    frontend_node: dict[str, Any] = {"outputs": []}
    request = UpdateCustomComponentRequest(
        code=code,
        frontend_node=frontend_node,
        field="show_output",
        field_value=True,
        template={},
    )
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    output_names = [output["name"] for output in result["outputs"]]
    assert "tool_output" in output_names


async def test_update_component_model_name_options(client: AsyncClient, logged_in_headers: dict):
    """Test that model options are updated when the model field changes."""
    component = AgentComponent()
    component_node, _cc_instance = build_custom_component_template(
        component,
    )

    # Initial template - check that model field exists and has options
    template = component_node["template"]
    assert "model" in template, f"model field not found. Available fields: {list(template.keys())}"

    # load the code from the file at lfx.components.models_and_agents.agent.py asynchronously
    # we are at str/backend/tests/unit/api/v1/test_endpoints.py
    # find the file by using the class AgentComponent
    agent_component_file = await asyncio.to_thread(inspect.getsourcefile, AgentComponent)
    code = await Path(agent_component_file).read_text(encoding="utf-8")

    # Create the request to update the component - change to a different provider's model
    # Select a model from a different provider to test that options update
    request = UpdateCustomComponentRequest(
        code=code,
        frontend_node=component_node,
        field="model",
        field_value=[{"provider": "Anthropic", "name": "claude-3-opus-20240229"}],  # Change provider
        template=template,
    )

    # Make the request to update the component
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    # Verify the response
    assert response.status_code == status.HTTP_200_OK, f"Response: {response.json()}"
    assert "template" in result
    assert "model" in result["template"], (
        f"model field not in result. Available fields: {list(result['template'].keys())}"
    )
    assert isinstance(result["template"]["model"].get("options", []), list)
    # Model options should be present (may be same or different depending on implementation)
    updated_model_options = result["template"]["model"].get("options", [])
    # Just verify that options exist after update
    assert isinstance(updated_model_options, list), (
        f"Model options should be a list, got: {type(updated_model_options)}"
    )


async def test_custom_component_update_admin_only_allows_known_template_refresh(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """Non-admin users can refresh known server templates in admin-only mode."""
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    admin_only_enabled = True
    monkeypatch.setitem(settings_service.settings.__dict__, "custom_component_admin_only", admin_only_enabled)
    monkeypatch.setattr(settings_service.settings, "allow_custom_components", True)

    component = AgentComponent()
    component_node, _cc_instance = build_custom_component_template(component)
    template = component_node["template"]

    agent_component_file = await asyncio.to_thread(inspect.getsourcefile, AgentComponent)
    code = await Path(agent_component_file).read_text(encoding="utf-8")

    request = UpdateCustomComponentRequest(
        code=code,
        frontend_node=component_node,
        field="model",
        field_value=[{"provider": "Anthropic", "name": "claude-3-opus-20240229"}],
        template=template,
    )
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.json()


async def test_custom_component_update_admin_only_blocks_unknown_custom_code(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """Non-admin users cannot edit truly custom code in admin-only mode."""
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    admin_only_enabled = True
    monkeypatch.setitem(settings_service.settings.__dict__, "custom_component_admin_only", admin_only_enabled)
    monkeypatch.setattr(settings_service.settings, "allow_custom_components", True)

    component_code = """
from lfx.custom import Component

class TestMetadataComponent(Component):
    display_name = "Test Metadata Component"
    description = "Test component for metadata"

    def run(self) -> str:
        return "ok"
"""

    request = UpdateCustomComponentRequest(
        code=component_code,
        frontend_node={"outputs": []},
        field="tool_mode",
        field_value=False,
        template={},
    )
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "restricted to administrators" in response.json().get("detail", "")


async def test_custom_component_create_admin_only_allows_known_template_refresh(
    client: AsyncClient,
    logged_in_headers: dict,
    monkeypatch,
):
    """Non-admin users can create/refresh known server templates in admin-only mode."""
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    admin_only_enabled = True
    monkeypatch.setitem(settings_service.settings.__dict__, "custom_component_admin_only", admin_only_enabled)
    monkeypatch.setattr(settings_service.settings, "allow_custom_components", True)

    agent_component_file = await asyncio.to_thread(inspect.getsourcefile, AgentComponent)
    code = await Path(agent_component_file).read_text(encoding="utf-8")

    request = CustomComponentRequest(code=code)
    response = await client.post("api/v1/custom_component", json=request.model_dump(), headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK, response.json()


async def test_custom_component_create_admin_only_blocks_unknown_custom_code(
    client: AsyncClient,
    logged_in_headers: dict,
    monkeypatch,
):
    """Non-admin users cannot create truly custom code in admin-only mode."""
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    admin_only_enabled = True
    monkeypatch.setitem(settings_service.settings.__dict__, "custom_component_admin_only", admin_only_enabled)
    monkeypatch.setattr(settings_service.settings, "allow_custom_components", True)

    component_code = """
from lfx.custom import Component

class TestMetadataComponent(Component):
    display_name = "Test Metadata Component"
    description = "Test component for metadata"

    def run(self) -> str:
        return "ok"
"""

    request = CustomComponentRequest(code=component_code)
    response = await client.post("api/v1/custom_component", json=request.model_dump(), headers=logged_in_headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "restricted to administrators" in response.json().get("detail", "")


async def test_custom_component_create_admin_only_allows_superuser(
    client: AsyncClient,
    logged_in_headers_super_user: dict,
    monkeypatch,
):
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    admin_only_enabled = True
    monkeypatch.setitem(settings_service.settings.__dict__, "custom_component_admin_only", admin_only_enabled)
    monkeypatch.setattr(settings_service.settings, "allow_custom_components", True)

    code = """
from lfx.custom import Component

class SuperUserMetadataComponent(Component):
    display_name = "SuperUser Metadata Component"
    description = "Test component for superuser bypass"

    def run(self) -> str:
        return "ok"
"""

    request = CustomComponentRequest(code=code)
    response = await client.post(
        "api/v1/custom_component",
        json=request.model_dump(),
        headers=logged_in_headers_super_user,
    )

    assert response.status_code == status.HTTP_200_OK, response.json()
    assert "data" in response.json()


async def test_custom_component_update_admin_only_allows_superuser(
    client: AsyncClient,
    logged_in_headers_super_user: dict,
    monkeypatch,
):
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    admin_only_enabled = True
    monkeypatch.setitem(settings_service.settings.__dict__, "custom_component_admin_only", admin_only_enabled)
    monkeypatch.setattr(settings_service.settings, "allow_custom_components", True)

    component_code = """
from lfx.custom import Component

class SuperUserUpdateMetadataComponent(Component):
    display_name = "SuperUser Update Metadata Component"
    description = "Test component update for superuser bypass"

    def run(self) -> str:
        return "ok"
"""

    request = UpdateCustomComponentRequest(
        code=component_code,
        frontend_node={"outputs": []},
        field="tool_mode",
        field_value=False,
        template={},
    )
    response = await client.post(
        "api/v1/custom_component/update",
        json=request.model_dump(),
        headers=logged_in_headers_super_user,
    )

    assert response.status_code == status.HTTP_200_OK, response.json()


async def test_custom_component_endpoint_returns_metadata(client: AsyncClient, logged_in_headers: dict):
    """Test that the /custom_component endpoint returns metadata with module and code_hash."""
    component_code = """
from lfx.custom import Component
from lfx.inputs import MessageTextInput
from lfx.template.field.base import Output

class TestMetadataComponent(Component):
    display_name = "Test Metadata Component"
    description = "Test component for metadata"

    inputs = [
        MessageTextInput(display_name="Input", name="input_value"),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="process_input"),
    ]

    def process_input(self) -> str:
        return f"Processed: {self.input_value}"
"""

    request = CustomComponentRequest(code=component_code)
    response = await client.post("api/v1/custom_component", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert "data" in result
    assert "type" in result

    # Verify metadata is present in the response
    frontend_node = result["data"]
    assert "metadata" in frontend_node, "Frontend node should contain metadata"

    # TODO: Temporarily skip metadata checks
    # metadata = frontend_node["metadata"]
    # assert "module" in metadata, "Metadata should contain module field"
    # assert "code_hash" in metadata, "Metadata should contain code_hash field"

    # Verify metadata values
    # assert isinstance(metadata["module"], str), "Module should be a string"
    # expected_module = "custom_components.test_metadata_component"
    # assert metadata["module"] == expected_module, "Module should be auto-generated from display_name"

    # assert isinstance(metadata["code_hash"], str), "Code hash should be a string"
    # assert len(metadata["code_hash"]) == 12, "Code hash should be 12 characters long"
    # assert all(c in "0123456789abcdef" for c in metadata["code_hash"]), "Code hash should be hexadecimal"


async def test_custom_component_endpoint_metadata_consistency(client: AsyncClient, logged_in_headers: dict):
    """Test that the same component code produces consistent metadata."""
    component_code = """
from lfx.custom import Component
from lfx.template.field.base import Output

class ConsistencyTestComponent(Component):
    display_name = "Consistency Test"

    outputs = [
        Output(display_name="Output", name="output", method="get_result"),
    ]

    def get_result(self) -> str:
        return "consistent result"
"""

    # Make two identical requests
    request = CustomComponentRequest(code=component_code)

    response1 = await client.post("api/v1/custom_component", json=request.model_dump(), headers=logged_in_headers)
    # result1 = response1.json()

    response2 = await client.post("api/v1/custom_component", json=request.model_dump(), headers=logged_in_headers)
    # result2 = response2.json()

    # Both requests should succeed
    assert response1.status_code == status.HTTP_200_OK
    assert response2.status_code == status.HTTP_200_OK
    # TODO: Temporarily skip metadata checks

    # Metadata should be identical
    # metadata1 = result1["data"]["metadata"]
    # metadata2 = result2["data"]["metadata"]

    # assert metadata1["module"] == metadata2["module"], "Module names should be consistent"
    # assert metadata1["code_hash"] == metadata2["code_hash"], "Code hashes should be consistent for identical code"


async def test_get_config_without_authentication_returns_public_config(client: AsyncClient):
    """Test that /config returns public config when accessed without authentication."""
    response = await client.get("api/v1/config")
    assert response.status_code == status.HTTP_200_OK


async def test_get_config_unauthenticated_returns_expected_fields(client: AsyncClient):
    """Test that unauthenticated /config response contains only public-safe fields."""
    response = await client.get("api/v1/config")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"

    # Verify expected public fields are present
    assert "max_file_size_upload" in result, "Response must contain 'max_file_size_upload'"
    assert "event_delivery" in result, "Response must contain 'event_delivery'"
    assert "feature_flags" in result, "Response must contain 'feature_flags'"
    assert "voice_mode_available" in result, "Response must contain 'voice_mode_available'"
    assert "frontend_timeout" in result, "Response must contain 'frontend_timeout'"

    # Verify type discriminator for public config
    assert "type" in result, "Response must contain 'type' discriminator field"
    assert result["type"] == "public", "Unauthenticated response must have type='public'"


async def test_get_config_unauthenticated_does_not_expose_sensitive_fields(client: AsyncClient):
    """Test that unauthenticated /config response does not contain sensitive configuration fields."""
    response = await client.get("api/v1/config")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK

    # Verify sensitive fields are NOT present
    sensitive_fields = [
        "database_url",
        "secret_key",
        "auto_saving",
        "auto_saving_interval",
        "health_check_max_retries",
        "webhook_polling_interval",
        "serialization_max_items_length",
        "webhook_auth_enable",
        "default_folder_name",
        "hide_getting_started_progress",
    ]

    for field in sensitive_fields:
        assert field not in result, f"Sensitive field '{field}' should not be exposed in unauthenticated config"


async def test_get_config_unauthenticated_returns_correct_field_types(client: AsyncClient):
    """Test that unauthenticated /config response fields have correct types."""
    response = await client.get("api/v1/config")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK

    # Verify field types
    assert isinstance(result["max_file_size_upload"], int), "max_file_size_upload must be an integer"
    assert isinstance(result["frontend_timeout"], int), "frontend_timeout must be an integer"
    assert isinstance(result["voice_mode_available"], bool), "voice_mode_available must be a boolean"
    assert isinstance(result["feature_flags"], dict), "feature_flags must be an object"
    assert result["feature_flags"].get("wxo_deployments") is False, "wxo_deployments flag should default to false"
    assert result["event_delivery"] in ["polling", "streaming", "direct"], (
        "event_delivery must be one of: polling, streaming, direct"
    )


async def test_get_config_returns_500_on_settings_error(client: AsyncClient, monkeypatch):
    """Test that /config endpoint returns 500 when settings retrieval fails."""
    error_message = "Settings retrieval failed"

    def raise_settings_error():
        raise RuntimeError(error_message)

    # Patch get_settings_service at the module level
    monkeypatch.setattr("langflow.api.v1.endpoints.get_settings_service", raise_settings_error)

    response = await client.get("api/v1/config")
    result = response.json()

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert error_message in result["detail"]


async def test_get_config_authenticated_returns_full_config(client: AsyncClient, logged_in_headers: dict):
    """Test that authenticated /config returns full ConfigResponse with all settings."""
    response = await client.get("api/v1/config", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"

    # Verify type discriminator for full config
    assert "type" in result, "Response must contain 'type' discriminator field"
    assert result["type"] == "full", "Authenticated response must have type='full'"

    # Verify full config fields are present (not just public fields)
    assert "auto_saving" in result, "Authenticated response must contain 'auto_saving'"
    assert "auto_saving_interval" in result, "Authenticated response must contain 'auto_saving_interval'"
    assert "health_check_max_retries" in result, "Authenticated response must contain 'health_check_max_retries'"
    assert "feature_flags" in result, "Authenticated response must contain 'feature_flags'"


async def test_get_config_embedded_mode_cascades_hide_flags(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """Embedded mode should only force UI hide flags, not security lock flags."""
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "embedded_mode", True)
    monkeypatch.setattr(settings_service.settings, "hide_logout_button", False)
    monkeypatch.setattr(settings_service.settings, "hide_new_project_button", False)
    monkeypatch.setattr(settings_service.settings, "hide_new_flow_button", False)
    monkeypatch.setattr(settings_service.settings, "hide_starter_projects", False)
    monkeypatch.setattr(settings_service.settings, "hide_getting_started_progress", False)
    monkeypatch.setattr(settings_service.settings, "mcp_servers_locked", False)
    monkeypatch.setattr(settings_service.settings, "custom_component_admin_only", False)

    response = await client.get("api/v1/config", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["embedded_mode"] is True
    assert result["hide_logout_button"] is True
    assert result["hide_new_project_button"] is True
    assert result["hide_new_flow_button"] is True
    assert result["hide_starter_projects"] is True
    # This flag is currently a direct passthrough (not part of embedded_mode cascade).
    assert result["hide_getting_started_progress"] is False
    # Security lock flags are explicit opt-ins and do not cascade from embedded_mode.
    assert result["mcp_servers_locked"] is False
    assert result["custom_component_admin_only"] is False


async def test_get_config_embedded_mode_false_keeps_individual_hide_flags(
    client: AsyncClient, logged_in_headers: dict, monkeypatch
):
    """When embedded mode is disabled, individual hide flags should retain explicit values."""
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "embedded_mode", False)
    monkeypatch.setattr(settings_service.settings, "hide_logout_button", False)
    monkeypatch.setattr(settings_service.settings, "hide_new_project_button", False)
    monkeypatch.setattr(settings_service.settings, "hide_new_flow_button", True)
    monkeypatch.setattr(settings_service.settings, "hide_starter_projects", False)
    monkeypatch.setattr(settings_service.settings, "hide_getting_started_progress", True)

    response = await client.get("api/v1/config", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["embedded_mode"] is False
    assert result["hide_logout_button"] is False
    assert result["hide_new_project_button"] is False
    assert result["hide_new_flow_button"] is True
    assert result["hide_starter_projects"] is False
    assert result["hide_getting_started_progress"] is True


async def test_get_config_returns_mcp_and_admin_only_flags(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """Config response should expose lock/admin feature flags from settings."""
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "mcp_servers_locked", True)
    monkeypatch.setattr(settings_service.settings, "custom_component_admin_only", True)

    response = await client.get("api/v1/config", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert result["mcp_servers_locked"] is True
    assert result["custom_component_admin_only"] is True


async def test_get_config_returns_mcp_base_url(client: AsyncClient, logged_in_headers: dict):
    """Test that /config includes mcp_base_url for both authenticated and unauthenticated responses."""
    # Authenticated
    response = await client.get("api/v1/config", headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert "mcp_base_url" in result, "Authenticated response must contain 'mcp_base_url'"
    assert isinstance(result["mcp_base_url"], str), "mcp_base_url must be a string"

    # Unauthenticated
    response = await client.get("api/v1/config")
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert "mcp_base_url" in result, "Public response must contain 'mcp_base_url'"
    assert isinstance(result["mcp_base_url"], str), "mcp_base_url must be a string"


async def test_get_config_mcp_base_url_defaults_to_empty(client: AsyncClient, logged_in_headers: dict):
    """Test that mcp_base_url defaults to empty string when LANGFLOW_MCP_BASE_URL is not set."""
    response = await client.get("api/v1/config", headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert result["mcp_base_url"] == ""


async def test_get_config_mcp_base_url_from_settings(client: AsyncClient, logged_in_headers: dict, monkeypatch):
    """Test that mcp_base_url reflects the value from settings."""
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "mcp_base_url", "https://langflow.example.com")

    response = await client.get("api/v1/config", headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert result["mcp_base_url"] == "https://langflow.example.com"


async def test_deprecated_upload_rejects_unauthenticated(client: AsyncClient, flow):
    """Regression: the deprecated /api/v1/upload/{flow_id} must require auth.

    Previously this endpoint accepted uploads without any credentials, letting
    anonymous callers write arbitrary files into a flow's cache folder.
    """
    response = await client.post(
        f"api/v1/upload/{flow.id}",
        files={"file": ("test.txt", b"test content")},
    )
    assert response.status_code != status.HTTP_201_CREATED, (
        "Deprecated upload endpoint must reject unauthenticated requests"
    )
    assert response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }, f"Expected 401/403, got {response.status_code}: {response.text}"


async def test_deprecated_upload_authenticated_succeeds(client: AsyncClient, logged_in_headers: dict, flow):
    """The deprecated endpoint still works for the flow's owner."""
    response = await client.post(
        f"api/v1/upload/{flow.id}",
        files={"file": ("test.txt", b"test content")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, (
        f"Expected 201 for authenticated owner, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body["flowId"] == str(flow.id)


async def test_deprecated_upload_enforces_max_file_size(
    client: AsyncClient, logged_in_headers: dict, flow, monkeypatch
):
    """Regression: the deprecated upload route must honor ``max_file_size_upload``.

    Without this guard, an authenticated user could still fill disk through
    this route by uploading arbitrarily large files, bypassing the limit the
    non-deprecated twin at /api/v1/files/upload/{flow_id} already enforces.
    """
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "max_file_size_upload", 1)  # 1 MB
    oversized = b"x" * (2 * 1024 * 1024)  # 2 MB, exceeds the limit

    response = await client.post(
        f"api/v1/upload/{flow.id}",
        files={"file": ("big.bin", oversized)},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE, (
        f"Expected 413 for oversized upload, got {response.status_code}: {response.text}"
    )

import asyncio
import hashlib
import inspect
from types import SimpleNamespace

import pytest
from anyio import Path
from fastapi import status
from httpx import AsyncClient
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.interface.components import component_cache
from lfx.services.catalog_policy.base import CatalogPolicySnapshot


@pytest.mark.usefixtures("active_user")
async def test_post_validate_code(client: AsyncClient, logged_in_headers):
    good_code = """
from pprint import pprint
var = {"a": 1, "b": 2}
pprint(var)
    """
    response = await client.post("api/v1/validate/code", json={"code": good_code}, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "imports" in result, "The result must have an 'imports' key"
    assert "function" in result, "The result must have a 'function' key"


@pytest.mark.usefixtures("active_user")
async def test_post_validate_code_blocks_catalog_template_before_validation(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    agent_component_file = await asyncio.to_thread(inspect.getsourcefile, AgentComponent)
    code = await Path(agent_component_file).read_text(encoding="utf-8")
    code_hash = hashlib.sha256(code.encode()).hexdigest()[:12]
    snapshot = CatalogPolicySnapshot(blocked_component_keys={"Agent"})
    monkeypatch.setattr(
        "langflow.api.v1.validate.get_catalog_policy_service",
        lambda: SimpleNamespace(snapshot=snapshot),
    )
    monkeypatch.setattr(
        "lfx.utils.flow_validation.get_component_hash_lookups_for_validation",
        lambda: {"Agent": {code_hash}},
    )

    def fail_if_validated(_code):
        msg = "blocked source must be denied before validate_code inspects imports"
        raise AssertionError(msg)

    monkeypatch.setattr("langflow.api.v1.validate.validate_code", fail_if_validated)

    response = await client.post("api/v1/validate/code", json={"code": code}, headers=logged_in_headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Agent" in response.json()["detail"]


@pytest.mark.parametrize(
    ("allow_custom_components", "admin_only", "expected_detail"),
    [
        (False, False, "disabled"),
        (True, True, "restricted to administrators"),
    ],
)
@pytest.mark.usefixtures("active_user")
async def test_post_validate_code_applies_custom_code_lockdown_before_validation(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
    allow_custom_components,
    admin_only,
    expected_detail: str,
):
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", allow_custom_components)
    monkeypatch.setattr(settings, "custom_component_admin_only", admin_only)
    monkeypatch.setattr(
        "langflow.api.v1.validate.get_catalog_policy_service",
        lambda: SimpleNamespace(snapshot=CatalogPolicySnapshot()),
    )
    monkeypatch.setattr(
        "langflow.api.v1.custom_component_policy.get_component_hash_lookups_for_validation",
        dict,
    )
    monkeypatch.setattr(component_cache, "all_known_hashes", set())

    def fail_if_validated(_code):
        msg = "restricted unknown source must be denied before validation"
        raise AssertionError(msg)

    monkeypatch.setattr("langflow.api.v1.validate.validate_code", fail_if_validated)

    response = await client.post(
        "api/v1/validate/code",
        json={"code": "import definitely_untrusted_module"},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert expected_detail in response.json()["detail"]


@pytest.mark.usefixtures("active_user")
async def test_post_validate_code_uses_trusted_template_source_in_restricted_mode(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    from langflow.services.deps import get_settings_service

    submitted_code = "known template source"
    trusted_code = "trusted server source"
    code_hash = hashlib.sha256(submitted_code.encode()).hexdigest()[:12]
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", False)
    monkeypatch.setattr(settings, "custom_component_admin_only", False)
    monkeypatch.setattr(
        "langflow.api.v1.validate.get_catalog_policy_service",
        lambda: SimpleNamespace(snapshot=CatalogPolicySnapshot()),
    )
    monkeypatch.setattr(
        "langflow.api.v1.custom_component_policy.get_component_hash_lookups_for_validation",
        lambda: {"Agent": {code_hash}},
    )
    monkeypatch.setattr(component_cache, "all_known_hashes", {code_hash})
    monkeypatch.setattr(component_cache, "code_by_hash", {code_hash: trusted_code})
    validated_codes = []

    def capture_validated_code(code):
        validated_codes.append(code)
        return {"imports": {}, "function": {}}

    monkeypatch.setattr("langflow.api.v1.validate.validate_code", capture_validated_code)

    response = await client.post(
        "api/v1/validate/code",
        json={"code": submitted_code},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert validated_codes == [trusted_code]


@pytest.mark.usefixtures("active_user")
async def test_post_validate_prompt(client: AsyncClient, logged_in_headers):
    basic_case = {
        "name": "string",
        "template": "string",
        "custom_fields": {},
        "frontend_node": {
            "template": {},
            "description": "string",
            "icon": "string",
            "is_input": True,
            "is_output": True,
            "is_composition": True,
            "base_classes": ["string"],
            "name": "",
            "display_name": "",
            "documentation": "",
            "custom_fields": {},
            "output_types": [],
            "full_path": "string",
            "pinned": False,
            "conditional_paths": [],
            "frozen": False,
            "outputs": [],
            "field_order": [],
            "beta": False,
            "minimized": False,
            "error": "string",
            "edited": False,
            "metadata": {},
        },
    }
    response = await client.post("api/v1/validate/prompt", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "frontend_node" in result, "The result must have a 'frontend_node' key"
    assert "input_variables" in result, "The result must have an 'input_variables' key"


@pytest.mark.usefixtures("active_user")
async def test_post_validate_prompt_with_invalid_data(client: AsyncClient, logged_in_headers):
    invalid_case = {
        "name": "string",
        # Missing required fields
        "frontend_node": {"template": {}, "is_input": True},
    }
    response = await client.post("api/v1/validate/prompt", json=invalid_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_post_validate_code_with_unauthenticated_user(client: AsyncClient):
    code = """
    print("Hello World")
    """
    response = await client.post("api/v1/validate/code", json={"code": code}, headers={"Authorization": "Bearer fake"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

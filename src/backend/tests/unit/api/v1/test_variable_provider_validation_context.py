"""Saving a provider API key must validate with the user's saved provider variables.

User report (Discord, 2026-06-11): with a local OpenAI-compatible server,
the dummy OPENAI_API_KEY cannot be saved — validation receives ONLY the
new variable, never the already-saved OPENAI_BASE_URL, so the check always
hits api.openai.com and 401s.

Mock boundary: ``validate_model_provider_key`` (a real external call).
"""

from unittest import mock

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE

pytestmark = pytest.mark.no_blockbuster

CUSTOM_BASE_URL = "http://localhost:11434/v1"


async def _delete_variable_if_present(client: AsyncClient, headers: dict, name: str) -> None:
    response = await client.get("api/v1/variables/", headers=headers)
    for variable in response.json():
        if variable["name"] == name:
            await client.delete(f"api/v1/variables/{variable['id']}", headers=headers)
            return


@pytest.mark.usefixtures("active_user")
async def test_should_validate_key_with_saved_base_url_when_creating_openai_key(client: AsyncClient, logged_in_headers):
    # store_environment_variables auto-imports OPENAI_API_KEY from the test env.
    await _delete_variable_if_present(client, logged_in_headers, "OPENAI_API_KEY")

    base_url_variable = {
        "name": "OPENAI_BASE_URL",
        "value": CUSTOM_BASE_URL,
        "type": GENERIC_TYPE,
        "default_fields": [],
    }
    response = await client.post("api/v1/variables/", json=base_url_variable, headers=logged_in_headers)
    assert response.status_code == status.HTTP_201_CREATED

    key_variable = {
        "name": "OPENAI_API_KEY",
        "value": "sk-local-dummy",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }
    with mock.patch("langflow.api.v1.variable.validate_model_provider_key") as validate:
        response = await client.post("api/v1/variables/", json=key_variable, headers=logged_in_headers)

    assert response.status_code == status.HTTP_201_CREATED
    validated_vars = validate.call_args.args[1]
    assert validated_vars.get("OPENAI_BASE_URL") == CUSTOM_BASE_URL, (
        f"Validation must see the saved base URL, got only: {validated_vars}"
    )
    assert validated_vars.get("OPENAI_API_KEY") == "sk-local-dummy"


async def test_should_validate_with_owner_provider_vars_not_caller_in_share_aware_update():
    """C4: share-aware update must fetch the OWNER's provider vars, not the caller's."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from langflow.api.v1 import variable as variable_module
    from langflow.services.database.models.variable.model import VariableUpdate

    caller = SimpleNamespace(id=uuid4())
    owner_id = uuid4()
    existing = SimpleNamespace(id=uuid4(), name="OPENAI_API_KEY", user_id=owner_id)

    svc = SimpleNamespace(update_variable_fields=AsyncMock(return_value=existing))
    captured = {}

    def fake_get_all_vars(user_id, _provider):
        captured["user_id"] = user_id
        return {"OPENAI_BASE_URL": CUSTOM_BASE_URL}

    with (
        mock.patch.object(variable_module, "get_variable_service", return_value=svc),
        mock.patch.object(variable_module, "DatabaseVariableService", object),
        mock.patch.object(variable_module, "authorized_or_owner_scoped", new=AsyncMock(return_value=existing)),
        mock.patch.object(variable_module, "ensure_variable_permission", new=AsyncMock()),
        mock.patch.object(variable_module, "get_provider_from_variable_name", return_value="OpenAI"),
        mock.patch.object(variable_module, "get_all_variables_for_provider", side_effect=fake_get_all_vars),
        mock.patch.object(variable_module, "validate_model_provider_key"),
    ):
        await variable_module.update_variable(
            session=AsyncMock(),
            variable_id=existing.id,
            variable=VariableUpdate(id=existing.id, name="OPENAI_API_KEY", value="sk-new"),
            current_user=caller,
        )

    assert captured["user_id"] == owner_id, (
        f"Provider vars must be fetched for the resource owner, not the caller. Got {captured['user_id']}"
    )

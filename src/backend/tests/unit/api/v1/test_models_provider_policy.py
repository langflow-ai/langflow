"""The model-provider policy must hide denied providers across shared OSS APIs."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import status
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.base.models.provider_registry import resolve_provider_id
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicyPurpose,
    ModelProviderPolicySnapshot,
)

if TYPE_CHECKING:
    from httpx import AsyncClient


def _openai_only_policy(*, user_id, providers, purpose, attributes=None):
    _ = attributes
    candidate_ids = frozenset(resolve_provider_id(provider) for provider in providers)
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id=user_id),
        purpose=purpose,
        candidate_provider_ids=candidate_ids,
        allowed_provider_ids=frozenset({"openai"}) & candidate_ids,
    )


def _allow_all_policy(*, user_id, providers, purpose, attributes=None):
    _ = attributes
    candidate_ids = frozenset(resolve_provider_id(provider) for provider in providers)
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id=user_id),
        purpose=purpose,
        candidate_provider_ids=candidate_ids,
        allowed_provider_ids=candidate_ids,
    )


async def _aopenai_only_policy(**kwargs):
    return _openai_only_policy(**kwargs)


async def _aallow_all_policy(**kwargs):
    return _allow_all_policy(**kwargs)


@pytest.fixture
async def scoped_flow(active_user):
    workspace_id = uuid4()
    folder = Folder(
        name=f"provider-policy-project-{uuid4()}",
        user_id=active_user.id,
        workspace_id=workspace_id,
    )
    flow = Flow(
        name=f"provider-policy-flow-{uuid4()}",
        data={},
        user_id=active_user.id,
        folder=folder,
        workspace_id=workspace_id,
    )
    async with session_scope() as session:
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        flow_id = flow.id
        project_id = folder.id

    yield SimpleNamespace(id=flow_id, project_id=project_id, workspace_id=workspace_id)

    async with session_scope() as session:
        stored_flow = await session.get(Flow, flow_id)
        if stored_flow is not None:
            await session.delete(stored_flow)
        stored_folder = await session.get(Folder, project_id)
        if stored_folder is not None:
            await session.delete(stored_folder)


@pytest.fixture(autouse=True)
def _restrict_to_openai(monkeypatch):
    monkeypatch.setattr("langflow.api.v1.models.aresolve_model_provider_policy", _aopenai_only_policy)
    monkeypatch.setattr("langflow.api.v1.model_options.aresolve_model_provider_policy", _aopenai_only_policy)


@pytest.mark.usefixtures("active_user")
async def test_provider_reads_hide_denied_providers(client: AsyncClient, logged_in_headers):
    providers_response = await client.get("api/v1/models/providers", headers=logged_in_headers)
    descriptors_response = await client.get("api/v1/models/provider-descriptors", headers=logged_in_headers)
    models_response = await client.get("api/v1/models", headers=logged_in_headers)
    mapping_response = await client.get("api/v1/models/provider-variable-mapping", headers=logged_in_headers)
    enabled_providers_response = await client.get("api/v1/models/enabled_providers", headers=logged_in_headers)
    enabled_models_response = await client.get("api/v1/models/enabled_models", headers=logged_in_headers)
    language_options_response = await client.get("api/v1/model_options/language", headers=logged_in_headers)
    embedding_options_response = await client.get("api/v1/model_options/embedding", headers=logged_in_headers)
    denied_query_response = await client.get(
        "api/v1/models",
        headers=logged_in_headers,
        params={"provider": "Anthropic"},
    )

    assert providers_response.status_code == status.HTTP_200_OK
    assert providers_response.json() == ["OpenAI"]
    assert descriptors_response.status_code == status.HTTP_200_OK
    assert descriptors_response.json() == [{"provider_id": "openai", "display_name": "OpenAI", "provider": "OpenAI"}]

    assert models_response.status_code == status.HTTP_200_OK
    model_groups = models_response.json()
    assert {group["provider"] for group in model_groups} == {"OpenAI"}
    assert {group["provider_id"] for group in model_groups} == {"openai"}
    assert all("is_allowed" not in group for group in model_groups)

    assert mapping_response.status_code == status.HTTP_200_OK
    assert set(mapping_response.json()) == {"OpenAI"}
    assert enabled_providers_response.status_code == status.HTTP_200_OK
    assert set(enabled_providers_response.json()["provider_status"]) == {"OpenAI"}
    assert enabled_models_response.status_code == status.HTTP_200_OK
    assert set(enabled_models_response.json()["enabled_models"]) == {"OpenAI"}
    assert language_options_response.status_code == status.HTTP_200_OK
    assert {option["provider"] for option in language_options_response.json()} <= {"OpenAI"}
    assert embedding_options_response.status_code == status.HTTP_200_OK
    assert {option["provider"] for option in embedding_options_response.json()} <= {"OpenAI"}
    assert denied_query_response.status_code == status.HTTP_200_OK
    assert denied_query_response.json() == []


async def test_provider_descriptors_union_stamped_palette_ids_without_duplicates(monkeypatch):
    from langflow.api.v1 import models as models_module

    captured_candidates = set()

    async def _allow_openai_and_mistral(*, user_id, providers, purpose, attributes=None):
        nonlocal captured_candidates
        _ = attributes
        captured_candidates = set(providers)
        candidate_ids = frozenset(resolve_provider_id(provider) for provider in providers)
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id),
            purpose=purpose,
            candidate_provider_ids=candidate_ids,
            allowed_provider_ids=frozenset({"openai", "mistral"}) & candidate_ids,
        )

    palette = {
        "mixed": {
            "OpenAIModel": {"metadata": {"model_provider_id": "openai", "model_provider_display_name": "OpenAI"}},
            "MistralChat": {"metadata": {"model_provider_id": "mistral", "model_provider_display_name": "Mistral"}},
            "MistralEmbedding": {
                "metadata": {"model_provider_id": "mistral", "model_provider_display_name": "Mistral"}
            },
            "HiddenModel": {
                "metadata": {"model_provider_id": "hidden-provider", "model_provider_display_name": "Hidden"}
            },
            "Utility": {"metadata": {}},
        }
    }
    monkeypatch.setattr(models_module, "aresolve_model_provider_policy", _allow_openai_and_mistral)
    monkeypatch.setattr(models_module, "get_model_providers", lambda: ["OpenAI"])
    monkeypatch.setattr(models_module, "get_and_cache_all_types_dict", AsyncMock(return_value=palette))

    descriptors = await models_module.list_model_provider_descriptors(
        SimpleNamespace(id="user-1"),
        {"is_superuser": False},
    )

    assert [descriptor.model_dump() for descriptor in descriptors] == [
        {"provider_id": "mistral", "display_name": "Mistral", "provider": "mistral"},
        {"provider_id": "openai", "display_name": "OpenAI", "provider": "OpenAI"},
    ]
    assert captured_candidates == {"openai", "mistral", "hidden-provider"}


@pytest.mark.usefixtures("active_user")
async def test_denied_provider_mutations_return_non_enumerating_not_found(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    provider_validation_called = False

    def _provider_validation(*_args, **_kwargs):
        nonlocal provider_validation_called
        provider_validation_called = True

    monkeypatch.setattr("langflow.api.v1.variable.validate_model_provider_key", _provider_validation)
    monkeypatch.setattr("lfx.base.models.unified_models.validate_model_provider_key", _provider_validation)
    validate_response = await client.post(
        "api/v1/models/validate-provider",
        headers=logged_in_headers,
        json={
            "provider": "Anthropic",
            "variables": {"ANTHROPIC_API_KEY": "test"},  # pragma: allowlist secret
        },
    )
    default_response = await client.post(
        "api/v1/models/default_model",
        headers=logged_in_headers,
        json={"provider": "Anthropic", "model_name": "claude-test", "model_type": "language"},
    )
    variable_response = await client.post(
        "api/v1/variables/",
        headers=logged_in_headers,
        json={
            "name": "ANTHROPIC_API_KEY",
            "value": "test",  # pragma: allowlist secret
            "type": "Credential",
            "default_fields": [],
        },
    )
    enabled_response = await client.post(
        "api/v1/models/enabled_models",
        headers=logged_in_headers,
        json=[{"provider": "Anthropic", "model_id": "claude-test", "enabled": True}],
    )

    assert validate_response.status_code == status.HTTP_404_NOT_FOUND
    assert default_response.status_code == status.HTTP_404_NOT_FOUND
    assert variable_response.status_code == status.HTTP_404_NOT_FOUND
    assert enabled_response.status_code == status.HTTP_404_NOT_FOUND
    assert provider_validation_called is False


@pytest.mark.usefixtures("active_user")
async def test_non_sluggable_provider_mutations_return_generic_not_found(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    provider = "秘密"
    provider_validation_called = False

    def _provider_validation(*_args, **_kwargs):
        nonlocal provider_validation_called
        provider_validation_called = True

    monkeypatch.setattr("langflow.api.v1.variable.validate_model_provider_key", _provider_validation)
    responses = [
        await client.post(
            "api/v1/models/validate-provider",
            headers=logged_in_headers,
            json={"provider": provider, "variables": {}},
        ),
        await client.post(
            "api/v1/models/default_model",
            headers=logged_in_headers,
            json={"provider": provider, "model_name": "unknown-model", "model_type": "language"},
        ),
        await client.post(
            "api/v1/models/enabled_models",
            headers=logged_in_headers,
            json=[{"provider": provider, "model_id": "unknown-model", "enabled": True}],
        ),
    ]

    for response in responses:
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "Model provider not found"}
        assert provider not in response.text
    assert provider_validation_called is False


@pytest.mark.usefixtures("active_user")
async def test_credential_rename_cannot_bypass_provider_policy(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    validation_called = False

    def _provider_validation(*_args, **_kwargs):
        nonlocal validation_called
        validation_called = True

    created = await client.post(
        "api/v1/variables/",
        headers=logged_in_headers,
        json={
            "name": f"POLICY_TEST_{uuid4().hex}",
            "value": "generic",
            "type": "Generic",
            "default_fields": [],
        },
    )
    assert created.status_code == status.HTTP_201_CREATED

    monkeypatch.setattr("langflow.api.v1.variable.validate_model_provider_key", _provider_validation)
    variable_id = created.json()["id"]
    response = await client.patch(
        f"api/v1/variables/{variable_id}",
        headers=logged_in_headers,
        json={
            "id": variable_id,
            "name": "ANTHROPIC_API_KEY",
            "value": "test",  # pragma: allowlist secret
            "type": "Credential",
            "default_fields": [],
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert validation_called is False


@pytest.mark.usefixtures("active_user")
async def test_dynamic_model_sources_cannot_reintroduce_denied_provider(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    from langflow.api.v1 import models as models_module

    monkeypatch.setattr(
        models_module,
        "_get_enabled_providers_result",
        AsyncMock(
            return_value={
                "enabled_providers": ["OpenAI", "Anthropic"],
                "provider_status": {"OpenAI": True, "Anthropic": True},
            }
        ),
    )
    monkeypatch.setattr(
        models_module,
        "_get_enabled_models_result",
        AsyncMock(return_value={"enabled_models": {}, "enabled_models_by_type": {}}),
    )
    live_provider_sets = []

    def _replace_with_live(groups, _user_id, configured_providers, *_args, **_kwargs):
        live_provider_sets.append(set(configured_providers))
        groups.append({"provider": "Anthropic", "models": [], "num_models": 0})

    def _inject_custom(groups, *_args, **_kwargs):
        groups.append(
            {
                "provider": "Anthropic",
                "models": [{"model_name": "blocked-custom", "metadata": {"model_type": "llm"}}],
                "num_models": 1,
            }
        )

    monkeypatch.setattr(models_module, "replace_with_live_models", _replace_with_live)
    monkeypatch.setattr(models_module, "inject_custom_enabled_models", _inject_custom)

    response = await client.get("api/v1/models", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert {group["provider"] for group in response.json()} == {"OpenAI"}
    assert live_provider_sets == [{"OpenAI"}]


@pytest.mark.usefixtures("active_user")
@pytest.mark.parametrize(
    "path",
    [
        "api/v1/models/providers",
        "api/v1/models",
        "api/v1/models/provider-variable-mapping",
        "api/v1/models/enabled_providers",
        "api/v1/models/enabled_models",
        "api/v1/model_options/language",
        "api/v1/model_options/embedding",
    ],
)
async def test_provider_read_purpose_rejects_unknown_values(
    client: AsyncClient,
    logged_in_headers,
    path: str,
):
    response = await client.get(path, headers=logged_in_headers, params={"purpose": "discover"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.usefixtures("active_user")
async def test_provider_read_purpose_defaults_and_overrides(client: AsyncClient, logged_in_headers, monkeypatch):
    captured_purposes = []

    async def _capture_policy(**kwargs):
        captured_purposes.append(kwargs["purpose"])
        return _allow_all_policy(**kwargs)

    monkeypatch.setattr("langflow.api.v1.models.aresolve_model_provider_policy", _capture_policy)
    monkeypatch.setattr("langflow.api.v1.model_options.aresolve_model_provider_policy", _capture_policy)

    default_paths = [
        ("api/v1/models/providers", ModelProviderPolicyPurpose.DISCOVER),
        (
            "api/v1/models",
            [ModelProviderPolicyPurpose.DISCOVER, ModelProviderPolicyPurpose.CONFIGURE],
        ),
        ("api/v1/models/provider-variable-mapping", ModelProviderPolicyPurpose.CONFIGURE),
        ("api/v1/models/enabled_providers", ModelProviderPolicyPurpose.CONFIGURE),
        ("api/v1/models/enabled_models", ModelProviderPolicyPurpose.CONFIGURE),
        ("api/v1/model_options/language", ModelProviderPolicyPurpose.USE),
        ("api/v1/model_options/embedding", ModelProviderPolicyPurpose.USE),
    ]
    for path, expected_purpose in default_paths:
        captured_purposes.clear()
        response = await client.get(path, headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK
        expected_purposes = expected_purpose if isinstance(expected_purpose, list) else [expected_purpose]
        assert captured_purposes == expected_purposes

    captured_purposes.clear()
    response = await client.get(
        "api/v1/model_options/language",
        headers=logged_in_headers,
        params={"purpose": "configure"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert captured_purposes == [
        ModelProviderPolicyPurpose.USE,
        ModelProviderPolicyPurpose.CONFIGURE,
    ]


@pytest.mark.usefixtures("active_user")
@pytest.mark.parametrize(
    "path",
    [
        "api/v1/models/providers",
        "api/v1/models",
        "api/v1/models/provider-variable-mapping",
        "api/v1/models/enabled_providers",
        "api/v1/models/enabled_models",
        "api/v1/model_options/language",
    ],
)
async def test_provider_reads_use_server_resolved_flow_scope(
    client: AsyncClient,
    logged_in_headers,
    scoped_flow,
    monkeypatch,
    path,
):
    captured_attributes = []

    async def _capture_policy(**kwargs):
        captured_attributes.append(kwargs.get("attributes"))
        return _allow_all_policy(**kwargs)

    monkeypatch.setattr("langflow.api.v1.models.aresolve_model_provider_policy", _capture_policy)
    monkeypatch.setattr("langflow.api.v1.model_options.aresolve_model_provider_policy", _capture_policy)

    response = await client.get(path, headers=logged_in_headers, params={"flow_id": str(scoped_flow.id)})

    assert response.status_code == status.HTTP_200_OK
    assert captured_attributes
    assert all(
        attributes["project_id"] == scoped_flow.project_id and attributes["workspace_id"] == scoped_flow.workspace_id
        for attributes in captured_attributes
    )


@pytest.mark.usefixtures("active_user")
async def test_global_provider_settings_remain_unscoped(client: AsyncClient, logged_in_headers, monkeypatch):
    captured_attributes = []

    async def _capture_policy(**kwargs):
        captured_attributes.append(kwargs.get("attributes"))
        return _allow_all_policy(**kwargs)

    monkeypatch.setattr("langflow.api.v1.models.aresolve_model_provider_policy", _capture_policy)

    response = await client.get("api/v1/models/providers", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert captured_attributes == [{"is_superuser": False}]


@pytest.mark.usefixtures("active_user")
async def test_provider_reads_accept_authorized_project_scope_and_resolve_workspace_server_side(
    client: AsyncClient,
    logged_in_headers,
    scoped_flow,
    monkeypatch,
):
    captured_attributes = []

    async def _capture_policy(**kwargs):
        captured_attributes.append(kwargs.get("attributes"))
        return _allow_all_policy(**kwargs)

    monkeypatch.setattr("langflow.api.v1.models.aresolve_model_provider_policy", _capture_policy)

    response = await client.get(
        "api/v1/models/providers",
        headers=logged_in_headers,
        params={"project_id": str(scoped_flow.project_id)},
    )

    assert response.status_code == status.HTTP_200_OK
    assert captured_attributes == [
        {
            "is_superuser": False,
            "project_id": scoped_flow.project_id,
            "workspace_id": scoped_flow.workspace_id,
        }
    ]


@pytest.mark.usefixtures("active_user")
@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"flow_id": str(uuid4()), "project_id": str(uuid4())}, status.HTTP_422_UNPROCESSABLE_CONTENT),
        ({"project_id": str(uuid4())}, status.HTTP_404_NOT_FOUND),
    ],
)
async def test_provider_scope_rejects_conflicts_and_inaccessible_targets(
    client: AsyncClient,
    logged_in_headers,
    params,
    expected_status,
):
    response = await client.get("api/v1/models/providers", headers=logged_in_headers, params=params)

    assert response.status_code == expected_status


@pytest.mark.usefixtures("active_user")
async def test_provider_credential_check_uses_server_resolved_flow_scope_before_validation(
    client: AsyncClient,
    logged_in_headers,
    scoped_flow,
    monkeypatch,
):
    captured_attributes = []
    validation_called = False

    async def _capture_policy(**kwargs):
        captured_attributes.append(kwargs.get("attributes"))
        return _allow_all_policy(**kwargs)

    def _validate(*_args, **_kwargs):
        nonlocal validation_called
        validation_called = True

    monkeypatch.setattr("langflow.api.v1.models.aresolve_model_provider_policy", _capture_policy)
    monkeypatch.setattr("lfx.base.models.unified_models.validate_model_provider_key", _validate)

    response = await client.post(
        "api/v1/models/validate-provider",
        headers=logged_in_headers,
        params={"flow_id": str(scoped_flow.id)},
        json={"provider": "OpenAI", "variables": {}},
    )

    assert response.status_code == status.HTTP_200_OK
    assert validation_called is True
    assert captured_attributes == [
        {
            "is_superuser": False,
            "project_id": scoped_flow.project_id,
            "workspace_id": scoped_flow.workspace_id,
        }
    ]


@pytest.mark.usefixtures("active_user")
async def test_provider_read_purpose_can_narrow_but_never_widen_endpoint_policy(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    from langflow.api.v1 import model_options as model_options_module

    allowed_by_purpose = {
        ModelProviderPolicyPurpose.DISCOVER: {"openai"},
        ModelProviderPolicyPurpose.CONFIGURE: {"openai"},
        ModelProviderPolicyPurpose.USE: {"openai", "anthropic"},
    }

    async def _divergent_policy(*, user_id, providers, purpose, attributes=None):
        _ = attributes
        candidate_ids = frozenset(resolve_provider_id(provider) for provider in providers)
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id),
            purpose=purpose,
            candidate_provider_ids=candidate_ids,
            allowed_provider_ids=frozenset(allowed_by_purpose[purpose]) & candidate_ids,
        )

    monkeypatch.setattr("langflow.api.v1.models.aresolve_model_provider_policy", _divergent_policy)
    monkeypatch.setattr("langflow.api.v1.model_options.aresolve_model_provider_policy", _divergent_policy)
    raw_options = [
        {"name": "gpt-test", "provider": "OpenAI", "metadata": {}},
        {"name": "claude-test", "provider": "Anthropic", "metadata": {}},
    ]
    monkeypatch.setattr(model_options_module, "get_language_model_options", lambda **_kwargs: raw_options)

    discover_use = await client.get(
        "api/v1/models/providers",
        headers=logged_in_headers,
        params={"purpose": "use"},
    )
    configure_use = await client.get(
        "api/v1/models/provider-variable-mapping",
        headers=logged_in_headers,
        params={"purpose": "use"},
    )
    use_configure = await client.get(
        "api/v1/model_options/language",
        headers=logged_in_headers,
        params={"purpose": "configure"},
    )

    assert discover_use.status_code == status.HTTP_200_OK
    assert discover_use.json() == ["OpenAI"]
    assert configure_use.status_code == status.HTTP_200_OK
    assert set(configure_use.json()) == {"OpenAI"}
    assert use_configure.status_code == status.HTTP_200_OK
    assert [option["provider"] for option in use_configure.json()] == ["OpenAI"]

    # An empty intersection stays empty; the requested purpose can never
    # replace a baseline decision with a disjoint provider set.
    allowed_by_purpose[ModelProviderPolicyPurpose.CONFIGURE] = {"anthropic"}
    empty_intersection = await client.get(
        "api/v1/models/providers",
        headers=logged_in_headers,
        params={"purpose": "configure"},
    )
    assert empty_intersection.status_code == status.HTTP_200_OK
    assert empty_intersection.json() == []


@pytest.mark.usefixtures("active_user")
async def test_model_options_add_provider_identity_and_filter_defensively(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    from langflow.api.v1 import model_options as model_options_module

    raw_options = [
        {"name": "gpt-test", "provider": "OpenAI", "metadata": {}},
        {"name": "claude-test", "provider": "Anthropic", "metadata": {}},
    ]
    monkeypatch.setattr(model_options_module, "get_language_model_options", lambda **_kwargs: raw_options)
    monkeypatch.setattr(model_options_module, "get_embedding_model_options", lambda **_kwargs: raw_options)

    for path in ("api/v1/model_options/language", "api/v1/model_options/embedding"):
        response = await client.get(path, headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [
            {
                "name": "gpt-test",
                "provider": "OpenAI",
                "metadata": {},
                "provider_id": "openai",
            }
        ]


@pytest.mark.usefixtures("active_user")
async def test_model_catalog_uses_configure_policy_for_configuration_status(
    client: AsyncClient,
    logged_in_headers,
    monkeypatch,
):
    from langflow.api.v1 import models as models_module

    allowed_by_purpose = {
        ModelProviderPolicyPurpose.DISCOVER: {"openai", "anthropic"},
        ModelProviderPolicyPurpose.CONFIGURE: {"openai"},
        ModelProviderPolicyPurpose.USE: {"openai", "anthropic"},
    }

    async def _divergent_policy(*, user_id, providers, purpose, attributes=None):
        _ = attributes
        candidate_ids = frozenset(resolve_provider_id(provider) for provider in providers)
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id),
            purpose=purpose,
            candidate_provider_ids=candidate_ids,
            allowed_provider_ids=frozenset(allowed_by_purpose[purpose]) & candidate_ids,
        )

    enabled_providers = AsyncMock(return_value={"enabled_providers": [], "provider_status": {}})
    enabled_models = AsyncMock(return_value={"enabled_models": {}, "enabled_models_by_type": {}})
    monkeypatch.setattr(models_module, "aresolve_model_provider_policy", _divergent_policy)
    monkeypatch.setattr(models_module, "_get_enabled_providers_result", enabled_providers)
    monkeypatch.setattr(models_module, "_get_enabled_models_result", enabled_models)

    response = await client.get("api/v1/models", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert {group["provider"] for group in response.json()} >= {"OpenAI", "Anthropic"}
    for helper in (enabled_providers, enabled_models):
        snapshot = helper.await_args.kwargs["provider_policy"]
        assert snapshot.purpose is ModelProviderPolicyPurpose.CONFIGURE
        assert snapshot.allowed_provider_ids == frozenset({"openai"})


@pytest.mark.usefixtures("active_user")
async def test_hidden_provider_variables_are_omitted_but_can_be_deleted(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    monkeypatch.setattr("langflow.api.v1.models.aresolve_model_provider_policy", _aallow_all_policy)
    existing_response = await client.get("api/v1/variables/", headers=logged_in_headers)
    for variable in existing_response.json():
        if variable["name"] == "ANTHROPIC_API_KEY":
            await client.delete(f"api/v1/variables/{variable['id']}", headers=logged_in_headers)

    monkeypatch.setattr("langflow.api.v1.variable.validate_model_provider_key", lambda *_args, **_kwargs: None)
    create_response = await client.post(
        "api/v1/variables/",
        headers=logged_in_headers,
        json={
            "name": "ANTHROPIC_API_KEY",
            "value": "test",  # pragma: allowlist secret
            "type": "Credential",
            "default_fields": [],
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    variable_id = create_response.json()["id"]

    monkeypatch.setattr("langflow.api.v1.models.aresolve_model_provider_policy", _aopenai_only_policy)
    hidden_response = await client.get("api/v1/variables/", headers=logged_in_headers)
    delete_response = await client.delete(f"api/v1/variables/{variable_id}", headers=logged_in_headers)

    assert "ANTHROPIC_API_KEY" not in {variable["name"] for variable in hidden_response.json()}
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

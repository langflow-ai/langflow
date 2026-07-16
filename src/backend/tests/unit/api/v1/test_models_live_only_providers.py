"""Live-discovery-only providers (extension bundles) in ``GET /api/v1/models``.

Providers registered by extension bundles (e.g. vLLM, OpenAI Compatible) ship
no static catalog rows and rely entirely on live discovery. ``list_models``
must still emit them -- with an empty model list -- while they are unconfigured,
otherwise the Model Providers dialog never offers their configuration form:
``replace_with_live_models`` only fills a provider once it is configured *and*
its endpoint returns models, a bootstrap dead-end for a fresh install.
"""

import pytest
from fastapi import status
from httpx import AsyncClient
from lfx.base.models import provider_registry
from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS, MODEL_PROVIDER_METADATA
from lfx.base.models.provider_registry import ProviderSpec, register_provider

_PROVIDER_NAME = "FakeLiveCo"
_API_DOCS_URL = "https://fakeliveco.example/docs"
_AMBIENT_PROVIDER_NAME = "AmbientAuthCo"
_AMBIENT_MODEL_NAME = "ambient-chat"


def fake_live_discovery(user_id, model_type):  # noqa: ARG001
    """Referenced by the ProviderSpec dotted path; never called while unconfigured."""
    return []


def ambient_auth_catalog():
    """Static catalog for a provider whose runtime uses ambient authentication."""
    return [
        {
            "name": _AMBIENT_MODEL_NAME,
            "model_type": "llm",
            "default": True,
        }
    ]


def _fakeliveco_spec() -> ProviderSpec:
    return ProviderSpec(
        name=_PROVIDER_NAME,
        metadata={
            "icon": "Bot",
            "variables": [
                {
                    "variable_name": "Base URL",
                    "variable_key": "FAKELIVECO_BASE_URL",
                    "required": True,
                    "is_secret": False,
                    "is_list": False,
                    "options": [],
                    "langchain_param": "base_url",
                },
            ],
            "api_docs_url": _API_DOCS_URL,
            "mapping": {"model_class": "ChatOpenAI", "model_param": "model"},
        },
        live=True,
        live_discovery=f"{__name__}:fake_live_discovery",
        api_key_required=False,
    )


def _ambient_auth_spec() -> ProviderSpec:
    return ProviderSpec(
        name=_AMBIENT_PROVIDER_NAME,
        metadata={
            "icon": "Bot",
            "variables": [],
            "mapping": {"model_class": "ChatOpenAI", "model_param": "model"},
        },
        api_key_required=False,
        catalog_loader=f"{__name__}:ambient_auth_catalog",
    )


def _unregister(name: str) -> None:
    """Remove a single provider registration.

    ``provider_registry.clear()`` reverses *every* registration, which would
    also wipe providers registered by real bundles during app startup and leak
    that loss into later tests in the same process. Reverse only ours instead.
    """
    MODEL_PROVIDER_METADATA.pop(name, None)
    if name in LIVE_MODEL_PROVIDERS:
        LIVE_MODEL_PROVIDERS.remove(name)
    descriptor = provider_registry._registered.pop(name, None)
    if descriptor is not None:
        provider_registry._registered_ids.pop(descriptor.canonical_id(), None)
    for alias, registered_name in list(provider_registry._registered_aliases.items()):
        if registered_name == name:
            provider_registry._registered_aliases.pop(alias, None)
    provider_registry._live_discovery_cache.pop(name, None)
    provider_registry._validator_cache.pop(name, None)
    provider_registry._catalog_cache.pop(name, None)
    provider_registry._undo.metadata_keys.discard(name)
    provider_registry._undo.live_names.discard(name)
    provider_registry._generation += 1
    provider_registry._clear_derived_caches()


@pytest.fixture
def fake_live_provider():
    assert register_provider(_fakeliveco_spec()) is True
    yield _PROVIDER_NAME
    _unregister(_PROVIDER_NAME)


@pytest.fixture
def ambient_auth_provider():
    assert register_provider(_ambient_auth_spec()) is True
    yield _AMBIENT_PROVIDER_NAME
    _unregister(_AMBIENT_PROVIDER_NAME)


async def _get_models(client: AsyncClient, headers: dict, params: dict | None = None) -> list[dict]:
    response = await client.get("api/v1/models", headers=headers, params=params)
    assert response.status_code == status.HTTP_200_OK
    return response.json()


@pytest.mark.usefixtures("active_user")
async def test_unconfigured_live_only_provider_is_listed(client: AsyncClient, logged_in_headers, fake_live_provider):
    providers = await _get_models(client, logged_in_headers)

    entry = next((p for p in providers if p["provider"] == fake_live_provider), None)
    assert entry is not None, "live-only provider missing from the default listing"
    assert entry["models"] == []
    assert entry["num_models"] == 0
    assert entry["is_configured"] is False
    assert entry["is_enabled"] is False
    # Provider metadata merges into the entry, same shape as catalog providers.
    assert entry["api_docs_url"] == _API_DOCS_URL


@pytest.mark.usefixtures("active_user")
async def test_live_only_provider_respects_provider_filter(client: AsyncClient, logged_in_headers, fake_live_provider):
    only_fake = await _get_models(client, logged_in_headers, params={"provider": fake_live_provider})
    assert [p["provider"] for p in only_fake] == [fake_live_provider]

    only_openai = await _get_models(client, logged_in_headers, params={"provider": "OpenAI"})
    assert fake_live_provider not in {p["provider"] for p in only_openai}


@pytest.mark.usefixtures("active_user")
async def test_live_only_provider_absent_from_model_queries(client: AsyncClient, logged_in_headers, fake_live_provider):
    # Queries about concrete models (model_name / metadata filters) must not
    # gain empty provider entries.
    by_metadata = await _get_models(client, logged_in_headers, params={"tool_calling": True})
    assert fake_live_provider not in {p["provider"] for p in by_metadata}

    by_name = await _get_models(client, logged_in_headers, params={"model_name": "no-such-model"})
    assert fake_live_provider not in {p["provider"] for p in by_name}


@pytest.mark.usefixtures("active_user")
async def test_non_live_metadata_providers_stay_hidden(client: AsyncClient, logged_in_headers):
    # Azure OpenAI / Groq have provider metadata but neither a static catalog
    # nor live discovery: the union must not resurrect them.
    providers = {p["provider"] for p in await _get_models(client, logged_in_headers)}
    assert "Azure OpenAI" not in providers
    assert "Groq" not in providers


@pytest.mark.usefixtures("active_user")
async def test_credentialless_extension_provider_is_enabled_and_offered(
    client: AsyncClient,
    logged_in_headers,
    ambient_auth_provider,
):
    enabled_response = await client.get("api/v1/models/enabled_providers", headers=logged_in_headers)
    options_response = await client.get("api/v1/model_options/language", headers=logged_in_headers)

    assert enabled_response.status_code == status.HTTP_200_OK
    assert enabled_response.json()["provider_status"][ambient_auth_provider] is True
    assert ambient_auth_provider in enabled_response.json()["enabled_providers"]

    assert options_response.status_code == status.HTTP_200_OK
    assert any(
        option["provider"] == ambient_auth_provider and option["name"] == _AMBIENT_MODEL_NAME
        for option in options_response.json()
    )

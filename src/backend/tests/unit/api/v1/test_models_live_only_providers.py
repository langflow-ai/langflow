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


def fake_live_discovery(user_id, model_type):  # noqa: ARG001
    """Referenced by the ProviderSpec dotted path; never called while unconfigured."""
    return []


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


def _unregister(name: str) -> None:
    """Remove a single provider registration.

    ``provider_registry.clear()`` reverses *every* registration, which would
    also wipe providers registered by real bundles during app startup and leak
    that loss into later tests in the same process. Reverse only ours instead.
    """
    MODEL_PROVIDER_METADATA.pop(name, None)
    if name in LIVE_MODEL_PROVIDERS:
        LIVE_MODEL_PROVIDERS.remove(name)
    provider_registry._registered.pop(name, None)
    provider_registry._live_discovery_cache.pop(name, None)
    provider_registry._validator_cache.pop(name, None)
    provider_registry._clear_derived_caches()


@pytest.fixture
def fake_live_provider():
    assert register_provider(_fakeliveco_spec()) is True
    yield _PROVIDER_NAME
    _unregister(_PROVIDER_NAME)


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

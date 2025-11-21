import pytest
from httpx import AsyncClient


def _flatten_models(result_json):
    for provider_dict in result_json:
        yield from provider_dict["models"]


@pytest.mark.asyncio
async def test_models_endpoint_default(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/models", headers=logged_in_headers)
    assert response.status_code == 200
    data = response.json()
    providers = {entry["provider"] for entry in data}
    assert "OpenAI" in providers
    assert "Anthropic" in providers
    assert "Google Generative AI" in providers

    for model in _flatten_models(data):
        assert model["metadata"].get("not_supported", False) is False


@pytest.mark.asyncio
async def test_models_endpoint_filter_provider(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/models", params={"provider": "Anthropic"}, headers=logged_in_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["provider"] == "Anthropic"


@pytest.mark.asyncio
async def test_models_endpoint_filter_model_type(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/models", params={"model_type": "embeddings"}, headers=logged_in_headers)
    assert response.status_code == 200
    data = response.json()
    models = list(_flatten_models(data))
    assert models, "Expected at least one embedding model through API"
    for model in models:
        assert model["metadata"].get("model_type", "llm") == "embeddings"

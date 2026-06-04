"""Reproduction tests for the F2 Langflow Assistant API bug report (2026-06-02).

Each test pins the CURRENT behavior of a reported issue so the fix has a
failing test to flip:

  Issue 1 — GET /agentic/check-config returns providers:[] / default_*:null
            even though configured_providers is populated.
  Issue 2 — POST /agentic/assist runs the LLM (HTTP 200) on an unknown or
            cross-user flow_id instead of rejecting with 404/403.
  Issue 3 — POST /agentic/execute/LangflowAssistant returns HTTP 500 for a
            valid assistant flow file (missing provider/model context).

The endpoint tests need at least one configured provider; OPENAI_API_KEY from
the repo .env (loaded by conftest) enables OpenAI for every user, so they skip
cleanly when no key is present.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope

from tests.api_keys import has_api_key

_NEEDS_KEY = pytest.mark.skipif(
    not has_api_key("OPENAI_API_KEY"),
    reason="A configured provider (OPENAI_API_KEY) is required to reach these paths",
)


def test_registry_language_model_type_filter_excludes_every_llm():
    """Issue 1 root cause: language models carry model_type='llm', not 'language'."""
    from lfx.base.models.unified_models import get_unified_models_detailed

    providers = ["OpenAI", "Anthropic"]
    as_llm = get_unified_models_detailed(providers=providers, model_type="llm")
    as_language = get_unified_models_detailed(providers=providers, model_type="language")

    assert sum(len(p.get("models", [])) for p in as_llm) > 0
    # check-config passes model_type="language" → this is why providers[] is empty.
    assert sum(len(p.get("models", [])) for p in as_language) == 0


@_NEEDS_KEY
async def test_check_config_providers_are_consistent_with_configured_providers(client, logged_in_headers):
    """Issue 1: providers[] and default_* must not be empty when a provider is configured."""
    response = await client.get("api/v1/agentic/check-config", headers=logged_in_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["configured_providers"], "expected at least OpenAI from the env key"
    assert data["providers"], f"providers[] empty despite configured_providers={data['configured_providers']}"
    assert data["default_provider"] is not None
    assert data["default_model"] is not None


@_NEEDS_KEY
async def test_assist_rejects_unknown_flow_id_before_invoking_the_model(client, logged_in_headers):
    """Issue 2: an unknown flow_id should be rejected, not silently run on empty context."""
    body = {"flow_id": "00000000-0000-0000-0000-000000000000", "input_value": "hi"}
    response = await client.post("api/v1/agentic/assist", json=body, headers=logged_in_headers)
    assert response.status_code in (403, 404), response.text


@_NEEDS_KEY
async def test_assist_rejects_cross_user_flow_id(client, active_user, user_two_api_key):
    """Issue 2: user B asking against user A's flow_id should be rejected, not run."""
    flow_id = uuid4()
    async with session_scope() as session:
        session.add(
            Flow(
                id=flow_id,
                name=f"repro-cross-user-{flow_id}",
                user_id=active_user.id,
                data={"nodes": [], "edges": []},
            )
        )
        await session.commit()

    try:
        body = {"flow_id": str(flow_id), "input_value": "what is on my canvas?"}
        response = await client.post("api/v1/agentic/assist", json=body, headers={"x-api-key": user_two_api_key})
        assert response.status_code in (403, 404), response.text
    finally:
        async with session_scope() as session:
            stored = await session.get(Flow, flow_id)
            if stored:
                await session.delete(stored)
                await session.commit()


@_NEEDS_KEY
async def test_execute_named_assistant_flow_is_graceful_not_500(client, logged_in_headers):
    """Issue 3: executing the built-in assistant flow must not 500."""
    body = {"flow_id": str(uuid4()), "input_value": "In one short sentence, what is Langflow?"}
    response = await client.post("api/v1/agentic/execute/LangflowAssistant", json=body, headers=logged_in_headers)
    assert response.status_code != 500, response.text

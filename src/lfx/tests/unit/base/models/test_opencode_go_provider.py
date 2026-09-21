"""Unit tests for the OpenCode Go unified model provider.

OpenCode Go is an OpenAI-compatible endpoint that *requires* an
``x-opencode-session`` header (stable per conversation) and a client-specific
``User-Agent``. These tests pin the provider metadata, the live ``/models``
fetch, the header wiring in ``get_llm``, and API-key validation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import requests

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_opencode_go_in_provider_registry():
    from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS, MODEL_PROVIDER_METADATA

    assert "OpenCode Go" in MODEL_PROVIDER_METADATA
    assert "OpenCode Go" in LIVE_MODEL_PROVIDERS


def test_opencode_go_metadata_shape():
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["OpenCode Go"]
    assert meta["provider_id"] == "opencode-go"
    assert meta["base_url"] == "https://opencode.ai/zen/go/v1"
    assert meta["api_docs_url"] == "https://opencode.ai/docs/go/"
    assert meta["max_tokens_field_name"] == "max_tokens"
    assert meta["mapping"]["model_class"] == "ChatOpenAI"
    assert meta["mapping"]["model_param"] == "model"

    var_keys = {v["variable_key"] for v in meta["variables"]}
    assert var_keys == {"OPENCODE_GO_API_KEY"}

    api_key_var = meta["variables"][0]
    assert api_key_var["required"] is True
    assert api_key_var["is_secret"] is True
    assert api_key_var["langchain_param"] == "api_key"
    assert api_key_var["component_metadata"]["mapping_field"] == "api_key"


def test_opencode_go_declares_no_base_url_override():
    """The endpoint is fixed; a user-editable URL would need SSRF validation."""
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["OpenCode Go"]
    assert all(v.get("langchain_param") != "base_url" for v in meta["variables"])


def test_opencode_go_appears_in_get_model_providers():
    from lfx.base.models.unified_models import get_model_providers

    assert "OpenCode Go" in get_model_providers()


def test_opencode_go_param_mapping_resolves_to_chatopenai():
    from lfx.base.models.model_metadata import get_provider_param_mapping

    mapping = get_provider_param_mapping("OpenCode Go")
    assert mapping["model_class"] == "ChatOpenAI"
    assert mapping["api_key_param"] == "api_key"


def test_opencode_go_secret_variable_key():
    from lfx.base.models.unified_models import get_provider_secret_variable_key

    assert get_provider_secret_variable_key("OpenCode Go") == "OPENCODE_GO_API_KEY"


def test_opencode_go_api_key_is_env_importable():
    """Env-only installs must still enable the provider, or live discovery never fires.

    ``_fetch_enabled_providers_for_user`` is DB-only, so a key that is never imported
    from the environment into a Global Variable leaves the provider un-enabled and the
    catalog pinned to the static seed.
    """
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA
    from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

    required_secrets = {
        v["variable_key"]
        for v in MODEL_PROVIDER_METADATA["OpenCode Go"]["variables"]
        if v.get("required") and v.get("is_secret")
    }
    assert required_secrets, "provider must declare at least one required secret"
    assert required_secrets <= set(VARIABLES_TO_GET_FROM_ENVIRONMENT)


# ---------------------------------------------------------------------------
# Seed catalog
# ---------------------------------------------------------------------------


def test_opencode_go_seed_catalog_is_well_formed():
    from lfx.base.models.opencode_go_constants import OPENCODE_GO_MODELS_DETAILED

    assert OPENCODE_GO_MODELS_DETAILED, "seed list backs the pre-credential dropdown"
    for row in OPENCODE_GO_MODELS_DETAILED:
        assert row["provider"] == "OpenCode Go"
        assert isinstance(row["name"], str)
        assert row["name"]
        assert row["tool_calling"] is True


def test_opencode_go_seed_is_registered_last():
    """Ordering IS the anti-shadowing mechanism, so pin it directly.

    ``get_provider_for_model_name`` returns the FIRST catalog hit. OpenCode Go
    exposes short, unprefixed IDs (``kimi-k3``, ``glm-5.3``) and its live endpoint
    can introduce new ones at any time, so its group must sit last: any name it
    ends up sharing with an earlier provider then keeps resolving to the provider
    a flow was saved with.

    This asserts the ordering rather than a specific collision on purpose. The Go
    catalog currently shares no names with Anthropic/OpenAI, so a collision-based
    test would silently become vacuous while looking like it still guarded this.
    """
    from lfx.base.models.opencode_go_constants import OPENCODE_GO_MODELS_DETAILED
    from lfx.base.models.unified_models.provider_queries import _STATIC_MODELS_DETAILED

    assert _STATIC_MODELS_DETAILED[-1] is OPENCODE_GO_MODELS_DETAILED


def test_opencode_go_seed_resolution_respects_earlier_providers():
    """Each seed name resolves to whichever provider declares it first.

    Unique names must resolve to OpenCode Go (proving the seed is registered at
    all); any name an earlier catalog already claims must not.
    """
    from lfx.base.models.opencode_go_constants import OPENCODE_GO_MODELS_DETAILED
    from lfx.base.models.unified_models import get_provider_for_model_name
    from lfx.base.models.unified_models.provider_queries import _STATIC_MODELS_DETAILED

    claimed_earlier = {row["name"] for group in _STATIC_MODELS_DETAILED[:-1] for row in group}
    for row in OPENCODE_GO_MODELS_DETAILED:
        resolved = get_provider_for_model_name(row["name"])
        if row["name"] in claimed_earlier:
            assert resolved != "OpenCode Go"
        else:
            assert resolved == "OpenCode Go"


def test_opencode_go_resolves_to_langchain_openai():
    """Without the fallback entry a deployed flow ImportErrors on a bare lfx runner."""
    from lfx.utils.flow_requirements import _PROVIDER_PACKAGE_FALLBACKS

    assert _PROVIDER_PACKAGE_FALLBACKS["OpenCode Go"] == {"langchain-openai"}


# ---------------------------------------------------------------------------
# Live discovery
# ---------------------------------------------------------------------------


def _models_payload():
    """Two IDs that are in the seed list, plus one that is live-only.

    The overlap is what exercises the default-set intersection; ``live-only-model``
    stands in for a model the live endpoint serves but the seed does not list.
    """
    return {
        "data": [
            {"id": "kimi-k3", "created": 1730000000},
            {"id": "glm-5.3", "created": 1731000000},
            {"id": "live-only-model"},
        ]
    }


def test_fetch_live_models_returns_catalog_rows():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    response = MagicMock()
    response.json.return_value = _models_payload()
    response.raise_for_status.return_value = None

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", return_value=response) as mock_get,
    ):
        models = fetch_live_opencode_go_models("user-1", "llm")

    url = mock_get.call_args[0][0]
    assert url == "https://opencode.ai/zen/go/v1/models"
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-test"

    # Sorted by id, every row owned by OpenCode Go, tool_calling assumed True.
    assert [m["name"] for m in models] == ["glm-5.3", "kimi-k3", "live-only-model"]
    assert all(m["provider"] == "OpenCode Go" for m in models)
    assert all(m["tool_calling"] is True for m in models)
    # Missing "created" degrades to 0 rather than raising.
    assert next(m for m in models if m["name"] == "live-only-model")["created"] == 0


def test_fetch_live_models_marks_defaults():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models
    from lfx.base.models.opencode_go_constants import OPENCODE_GO_MODELS_DETAILED

    response = MagicMock()
    response.json.return_value = _models_payload()
    response.raise_for_status.return_value = None

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", return_value=response),
    ):
        models = fetch_live_opencode_go_models("user-1", "llm")

    # Seed IDs present in the live catalog become the default set. Derived from
    # the seed module (rather than hardcoded) so this test pins the intersection
    # *behaviour* and doesn't retroactively break when the seed list is later
    # revised from the real endpoint.
    live_ids = {row["id"] for row in _models_payload()["data"]}
    expected = {m["name"] for m in OPENCODE_GO_MODELS_DETAILED} & live_ids
    assert expected, "payload must overlap the seed for this test to be meaningful"

    defaults = {m["name"] for m in models if m["default"]}
    assert defaults == expected


def test_fetch_live_models_defaults_fall_back_when_seed_is_stale():
    """When the live catalog shares no ids with the seed, fall back to the first.

    ``MIN_DEFAULT_MODELS`` sorted ids instead of an empty default set.
    """
    from lfx.base.models.model_utils import MIN_DEFAULT_MODELS, fetch_live_opencode_go_models

    payload = {
        "data": [{"id": f"unseeded-model-{i}", "created": 1700000000 + i} for i in range(MIN_DEFAULT_MODELS + 2)]
    }
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", return_value=response),
    ):
        models = fetch_live_opencode_go_models("user-1", "llm")

    sorted_ids = sorted(m["id"] for m in payload["data"])
    expected_defaults = set(sorted_ids[:MIN_DEFAULT_MODELS])

    defaults = {m["name"] for m in models if m["default"]}
    assert defaults == expected_defaults


def test_fetch_live_models_without_api_key_returns_empty():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    with patch("lfx.base.models.model_utils.get_provider_variable_value", return_value=None):
        assert fetch_live_opencode_go_models("user-1", "llm") == []


def test_fetch_live_models_ignores_embeddings():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    assert fetch_live_opencode_go_models("user-1", "embeddings") == []


@pytest.mark.parametrize(
    "boom",
    [
        httpx.RequestError("boom"),
        httpx.HTTPStatusError("boom", request=MagicMock(), response=MagicMock(status_code=500)),
    ],
)
def test_fetch_live_models_degrades_on_transport_error(boom):
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", side_effect=boom),
    ):
        assert fetch_live_opencode_go_models("user-1", "llm") == []


def test_fetch_live_models_degrades_on_malformed_payload():
    from lfx.base.models.model_utils import fetch_live_opencode_go_models

    response = MagicMock()
    response.json.return_value = {"data": "not-a-list"}
    response.raise_for_status.return_value = None

    with (
        patch("lfx.base.models.model_utils.get_provider_variable_value", return_value="sk-test"),
        patch("lfx.base.models.model_utils.httpx.get", return_value=response),
    ):
        assert fetch_live_opencode_go_models("user-1", "llm") == []


def test_get_live_models_for_provider_dispatches_opencode_go():
    from lfx.base.models import model_utils

    with patch.object(model_utils, "fetch_live_opencode_go_models", return_value=[{"name": "x"}]) as mock_fetch:
        result = model_utils.get_live_models_for_provider("user-1", "OpenCode Go", "llm")

    mock_fetch.assert_called_once_with("user-1", "llm")
    assert result == [{"name": "x"}]


# ---------------------------------------------------------------------------
# get_llm header wiring
# ---------------------------------------------------------------------------


def _opencode_model() -> list[dict]:
    return [{"provider": "OpenCode Go", "name": "kimi-k3", "metadata": {}}]


def _capture_factory():
    captured: dict = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    return FakeChatModel, captured


def _call_get_llm(**kwargs) -> dict:
    """Call ``get_llm`` for OpenCode Go, returning the chat-model constructor kwargs.

    Mirrors the harness in ``test_get_llm_streaming.py``: patching the two helpers
    on the ``unified_models`` package works because ``get_llm`` resolves them via
    ``unified_models_module.<name>`` at call time.
    """
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    fake_cls, captured = _capture_factory()
    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="sk-dummy",  # pragma: allowlist secret
        ),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
    ):
        get_llm(_opencode_model(), user_id=None, **kwargs)
    return captured


def test_get_llm_sets_base_url_and_required_headers():
    kwargs = _call_get_llm(session_id="sess-abc")

    assert kwargs["base_url"] == "https://opencode.ai/zen/go/v1"
    headers = kwargs["default_headers"]
    assert headers["x-opencode-session"] == "sess-abc"
    assert headers["User-Agent"].startswith("langflow/")
    # Never the generic openai SDK agent.
    assert "openai" not in headers["User-Agent"].lower()


def test_get_llm_session_header_is_stable_for_one_session():
    first = _call_get_llm(session_id="sess-abc")["default_headers"]["x-opencode-session"]
    second = _call_get_llm(session_id="sess-abc")["default_headers"]["x-opencode-session"]
    assert first == second == "sess-abc"


def test_get_llm_falls_back_to_generated_session_id():
    """Callers that don't pass a session id must still get a valid header.

    OpenCode Go rejects requests without it, so a missing session id degrades to
    a generated value rather than an omitted header.
    """
    headers = _call_get_llm()["default_headers"]
    assert headers["x-opencode-session"].startswith("langflow-")

    other = _call_get_llm()["default_headers"]["x-opencode-session"]
    assert other != headers["x-opencode-session"]


def test_get_llm_blank_session_id_falls_back():
    headers = _call_get_llm(session_id="   ")["default_headers"]
    assert headers["x-opencode-session"].startswith("langflow-")


def test_get_llm_does_not_add_headers_for_other_providers():
    """The branch must be inert for every other provider."""
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    fake_cls, captured = _capture_factory()
    anthropic = [
        {
            "name": "claude-3-5-sonnet-latest",
            "provider": "Anthropic",
            "metadata": {
                "model_class": "ChatAnthropic",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
            },
        }
    ]
    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="sk-dummy",  # pragma: allowlist secret
        ),
        patch.object(unified_models_module, "get_model_class", return_value=fake_cls),
    ):
        get_llm(anthropic, user_id=None, session_id="sess-abc")

    assert "default_headers" not in captured
    assert "base_url" not in captured


# ---------------------------------------------------------------------------
# Component -> get_llm session plumbing
# ---------------------------------------------------------------------------


def test_agent_passes_graph_session_id_to_get_llm():
    """Forward a fake graph's session id through ``_get_llm`` into ``get_llm``.

    ``AgentComponent.graph`` is a read-only property (``self._vertex.graph``) with no
    setter, so a bare ``agent.graph = ...`` assignment raises. Stub ``_vertex`` instead
    so the real property resolves to our fake graph.
    """
    from lfx.components.models_and_agents.agent import AgentComponent

    agent = AgentComponent.__new__(AgentComponent)
    agent._vertex = MagicMock(graph=MagicMock(session_id="sess-from-graph"))
    agent.model = _opencode_model()
    # ``user_id`` is also a read-only property (falls back to ``self.graph.user_id``);
    # set the backing ``_user_id`` attribute directly rather than the property.
    agent._user_id = "user-1"
    agent.max_tokens = None

    with patch("lfx.components.models_and_agents.agent.get_llm") as mock_get_llm:
        AgentComponent._get_llm(agent)

    assert mock_get_llm.call_args.kwargs["session_id"] == "sess-from-graph"


def test_language_model_passes_graph_session_id_to_get_llm():
    from lfx.components.models_and_agents.language_model import LanguageModelComponent

    component = LanguageModelComponent.__new__(LanguageModelComponent)
    component._vertex = MagicMock(graph=MagicMock(session_id="sess-from-graph"))
    component.model = _opencode_model()
    # ``user_id`` is also a read-only property; set the backing attribute directly.
    component._user_id = "user-1"
    component.api_key = None
    component.temperature = 0.1
    component.stream = False
    component.max_tokens = None

    with (
        patch(
            "lfx.components.models_and_agents.language_model.apply_model_overrides",
            side_effect=lambda model, **_: model,
        ),
        patch("lfx.components.models_and_agents.language_model.get_llm") as mock_get_llm,
    ):
        LanguageModelComponent.build_model(component)

    assert mock_get_llm.call_args.kwargs["session_id"] == "sess-from-graph"


def test_resolve_session_id_without_graph_returns_none():
    """Exercise ``_resolve_session_id`` with a bare stand-in rather than a real component.

    ``AgentComponent.graph``/``user_id`` are read-only properties backed by
    ``self._vertex``; on an uninitialized component (no ``_vertex``), accessing them
    routes through ``CustomComponent.__getattr__``'s "graph" fallback, which itself
    calls ``hasattr(self, "_user_id")`` — and that name is special-cased in
    ``Component.__getattr__`` to read straight out of ``__dict__``, raising
    ``KeyError`` (not ``AttributeError``) when unset. That's an unrelated framework
    quirk when synthesizing components via ``__new__``, not something this test is
    about. A plain object with neither attribute isolates the two ``hasattr`` checks
    ``_resolve_session_id`` actually performs.
    """
    from lfx.components.models_and_agents.agent import AgentComponent

    class _NoGraphStub:
        """Deliberately has neither ``graph`` nor ``_session_id``."""

    assert AgentComponent._resolve_session_id(_NoGraphStub()) is None


# ---------------------------------------------------------------------------
# Credential validation
# ---------------------------------------------------------------------------


def test_validate_api_key_success():
    from lfx.base.models.unified_models.credentials import validate_model_provider_key

    response = MagicMock(status_code=200)
    response.raise_for_status.return_value = None

    with patch("requests.get", return_value=response) as mock_get:
        validate_model_provider_key("OpenCode Go", {"OPENCODE_GO_API_KEY": "sk-test"})

    assert mock_get.call_args[0][0] == "https://opencode.ai/zen/go/v1/models"
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-test"


def test_validate_api_key_rejects_unauthorized():
    from lfx.base.models.unified_models.credentials import validate_model_provider_key

    response = MagicMock(status_code=401)

    with (
        patch("requests.get", return_value=response),
        pytest.raises(ValueError, match="Invalid OpenCode Go API key"),
    ):
        validate_model_provider_key("OpenCode Go", {"OPENCODE_GO_API_KEY": "sk-bad"})


def test_validate_api_key_network_error_raises_value_error():
    """The variable API only catches ValueError; a RequestException would 500."""
    from lfx.base.models.unified_models.credentials import validate_model_provider_key

    with (
        patch("requests.get", side_effect=requests.RequestException("boom")),
        pytest.raises(ValueError, match="Could not reach OpenCode Go"),
    ):
        validate_model_provider_key("OpenCode Go", {"OPENCODE_GO_API_KEY": "sk-test"})


def test_validate_api_key_missing_key_is_noop():
    from lfx.base.models.unified_models.credentials import validate_model_provider_key

    with patch("requests.get") as mock_get:
        validate_model_provider_key("OpenCode Go", {})

    mock_get.assert_not_called()

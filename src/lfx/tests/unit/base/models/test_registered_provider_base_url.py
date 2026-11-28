from __future__ import annotations

import pytest
from lfx.base.models import unified_models
from lfx.base.models.unified_models import instantiation


@pytest.fixture
def registered_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        instantiation.model_provider_metadata,
        "Test Provider",
        {
            "variables": [
                {
                    "variable_key": "TEST_BASE_URL",
                    "langchain_param": "base_url",
                    "base_url_suffix": "/v1",
                }
            ]
        },
    )
    monkeypatch.setattr(
        unified_models,
        "get_all_variables_for_provider",
        lambda *_args, **_kwargs: {"TEST_BASE_URL": "https://api.sarvam.ai/v2"},
    )


@pytest.mark.usefixtures("registered_provider")
def test_registered_provider_preserves_explicit_v2_base_url() -> None:
    kwargs: dict[str, str] = {}

    instantiation._apply_registered_provider_connection("Test Provider", None, kwargs)

    assert kwargs["base_url"] == "https://api.sarvam.ai/v2"


@pytest.mark.usefixtures("registered_provider")
def test_registered_provider_appends_v1_to_a_bare_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        unified_models,
        "get_all_variables_for_provider",
        lambda *_args, **_kwargs: {"TEST_BASE_URL": "https://gateway.example.com"},
    )
    kwargs: dict[str, str] = {}

    instantiation._apply_registered_provider_connection("Test Provider", None, kwargs)

    assert kwargs["base_url"] == "https://gateway.example.com/v1"


@pytest.mark.usefixtures("registered_provider")
def test_registered_provider_keeps_an_explicit_v1_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        unified_models,
        "get_all_variables_for_provider",
        lambda *_args, **_kwargs: {"TEST_BASE_URL": "https://gateway.example.com/v1"},
    )
    kwargs: dict[str, str] = {}

    instantiation._apply_registered_provider_connection("Test Provider", None, kwargs)

    assert kwargs["base_url"] == "https://gateway.example.com/v1"

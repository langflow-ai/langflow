from unittest.mock import MagicMock

import pytest

pytest.importorskip("lfx_bundles")

from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template
from lfx_bundles.volcengine.volcengine import (
    VOLCENGINE_MODELS,
    VolcengineModelComponent,
)


def test_volcengine_initialization():
    component = VolcengineModelComponent()
    assert component.display_name == "Volcengine Ark"
    assert component.icon == "Volcengine"


def test_volcengine_template():
    volcengine = VolcengineModelComponent()
    component = Component(_code=volcengine._code)
    frontend_node, _ = build_custom_component_template(component)

    assert isinstance(frontend_node, dict)
    assert "template" in frontend_node
    input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]

    expected_inputs = [
        "max_tokens",
        "model_kwargs",
        "json_mode",
        "model_name",
        "api_base",
        "api_key",
        "temperature",
        "reasoning_effort",
        "seed",
    ]

    for input_name in expected_inputs:
        assert input_name in input_names


def test_volcengine_model_ids_are_fully_versioned():
    """Ark 404s on the console's short names, so no bare family name may ship.

    doubao-seed-evolving is the one unversioned alias that resolves.
    """
    for model_id in VOLCENGINE_MODELS:
        if model_id == "doubao-seed-evolving":
            continue
        suffix = model_id.rsplit("-", 1)[-1]
        assert suffix.isdigit(), f"{model_id} is missing a dated version suffix"
        assert "." not in model_id, f"{model_id} looks like a console short name"


def test_get_models_drops_internal_entries():
    """/models is a dirty superset: prefix matching alone leaves dev/test builds."""
    component = VolcengineModelComponent()
    component.api_key = "test-key-not-real"
    component.api_base = "https://ark.cn-beijing.volces.com/api/v3"

    payload = {
        "data": [
            {"id": "doubao-seed-2-1-pro-260628"},
            {"id": "doubao-seed-1-6-flash-dev-test"},
            {"id": "doubao-seed-2-0-mini-mtp-train-test"},
            {"id": "doubao-seed-evolving"},
            {"id": "test-v1"},
            {"id": "ddd-1.0.0"},
        ]
    }
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "lfx_bundles.volcengine.volcengine.ssrf_safe_httpx_get",
            lambda *_args, **_kwargs: response,
        )
        models = component.get_models()

    assert models == ["doubao-seed-2-1-pro-260628", "doubao-seed-evolving"]


def test_get_models_falls_back_without_api_key():
    component = VolcengineModelComponent()
    component.api_key = ""
    assert component.get_models() == VOLCENGINE_MODELS


@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("langchain_openai.ChatOpenAI")


def test_reasoning_effort_is_passed_through(mock_chat_openai):
    """Ark grades thinking via reasoning_effort; unset must not send the key.

    It goes in as a first-class ChatOpenAI field, not via model_kwargs, which warns.
    """
    component = VolcengineModelComponent()
    component.api_key = "test-key-not-real"
    component.api_base = "https://ark.cn-beijing.volces.com/api/v3"
    component.model_name = VOLCENGINE_MODELS[0]
    component.max_tokens = 100
    component.temperature = 1.0
    component.seed = 1
    component.json_mode = False
    component.model_kwargs = {}

    component.reasoning_effort = "high"
    component.build_model()
    kwargs = mock_chat_openai.call_args.kwargs
    assert kwargs["reasoning_effort"] == "high"
    assert "reasoning_effort" not in kwargs["model_kwargs"]

    component.reasoning_effort = ""
    component.build_model()
    assert "reasoning_effort" not in mock_chat_openai.call_args.kwargs

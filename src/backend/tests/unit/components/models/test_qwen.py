import os

import pytest
from langchain_community.llms.tongyi import Tongyi
from langflow.base.models.qwen_constants import QWEN_MODEL_NAMES
from langflow.components.models.qwen import QwenModelComponent


@pytest.fixture
def qwen_credentials():
    """Fixture to get Qwen API key from environment variables."""
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        pytest.skip("QWEN_API_KEY environment variable is required.")
    return {"api_key": api_key}


@pytest.mark.api_key_required
@pytest.mark.parametrize("model_name", QWEN_MODEL_NAMES)
def test_qwen_different_models(qwen_credentials, model_name):
    """Test different Qwen models with a simple prompt."""
    component = QwenModelComponent()
    component.qwen_api_key = qwen_credentials["api_key"]
    component.model_name = model_name

    # Build the model
    model = component.build_model()
    assert isinstance(model, Tongyi)

    try:
        response = model.invoke("Who are you?")
        assert isinstance(response, str)
        assert len(response) > 0
    except ValueError as e:
        pytest.fail(f"Model {model_name} failed with error: {e!s}")


@pytest.mark.api_key_required
def test_qwen_nonexistent_model(qwen_credentials):
    """Test Qwen with a nonexistent model."""
    component = QwenModelComponent()
    component.model_name = "nonexistent-model"
    component.qwen_api_key = qwen_credentials["api_key"]
    model = component.build_model()
    assert isinstance(model, Tongyi)

    # invoke should raise an error with a specific message
    with pytest.raises(ValueError, match="status_code: 400 \n code: InvalidParameter \n message: Model not exist."):
        model.invoke("Say 'Hello' in Chinese")

import pytest
from unittest.mock import MagicMock

from langflow.custom import Component
from langflow.custom.utils import build_custom_component_template
from langflow.field_typing import Embeddings
from langflow.components.embeddings import HuggingFaceInferenceAPIEmbeddingsComponent


def test_huggingface_initialization():
    """Test initialization of HuggingFace component."""
    component = HuggingFaceInferenceAPIEmbeddingsComponent()
    assert component.display_name == "HuggingFace Embeddings Inference"
    assert component.description == "Generate embeddings using HuggingFace Text Embeddings Inference (TEI)"
    assert component.icon == "HuggingFace"
    assert component.name == "HuggingFaceInferenceAPIEmbeddings"


def test_huggingface_template():
    """Test the frontend template generation."""
    component = HuggingFaceInferenceAPIEmbeddingsComponent()
    custom_component = Component(_code=component._code)
    frontend_node, _ = build_custom_component_template(custom_component)

    assert isinstance(frontend_node, dict)

    input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]

    expected_inputs = [
        "api_key",
        "inference_endpoint",
        "model_name",
    ]

    for input_name in expected_inputs:
        assert input_name in input_names


@pytest.mark.parametrize(
    ("inference_endpoint", "model_name"),
    [
        ("https://api-inference.huggingface.co/models/", "BAAI/bge-large-en-v1.5"),
        ("http://localhost:8080", "sentence-transformers/all-mpnet-base-v2"),
    ],
)
@pytest.fixture
def mock_huggingface_embeddings(mocker):
    return mocker.patch("langchain_community.embeddings.huggingface.HuggingFaceInferenceAPIEmbeddings")


def test_huggingface_build_embeddings(mock_huggingface_embeddings):
    """Test the creation of HuggingFace embeddings."""
    component = HuggingFaceInferenceAPIEmbeddingsComponent()
    component.api_key = "test-key"
    component.inference_endpoint = "https://api-inference.huggingface.co/models/"
    component.model_name = "BAAI/bge-large-en-v1.5"

    # Mock the HuggingFaceInferenceAPIEmbeddings instance
    mock_instance = MagicMock()
    mock_huggingface_embeddings.return_value = mock_instance

    embeddings = component.build_embeddings()

    # Verify HuggingFaceInferenceAPIEmbeddings was called with correct params
    mock_huggingface_embeddings.assert_called_once_with(
        api_key="test-key",
        api_url="https://api-inference.huggingface.co/models/",
        model_name="BAAI/bge-large-en-v1.5",
    )
    assert embeddings == mock_instance


def test_huggingface_validate_inference_endpoint(mocker):
    """Test validation of the inference endpoint."""
    component = HuggingFaceInferenceAPIEmbeddingsComponent()

    # Mock requests.get for a successful health check
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200

    assert component.validate_inference_endpoint("https://api-inference.huggingface.co/models/") is True

    # Simulate a failed health check
    mock_get.return_value.status_code = 500
    with pytest.raises(ValueError, match="HuggingFace health check failed: 500"):
        component.validate_inference_endpoint("https://api-inference.huggingface.co/models/")


def test_huggingface_validate_inference_endpoint_invalid_format():
    """Test error handling for an invalid inference endpoint format."""
    component = HuggingFaceInferenceAPIEmbeddingsComponent()
    with pytest.raises(ValueError, match="Invalid inference endpoint format"):
        component.validate_inference_endpoint("invalid-url")


def test_huggingface_build_embeddings_without_api_key():
    """Test that an error is raised when trying to build embeddings without an API key (non-local)."""
    component = HuggingFaceInferenceAPIEmbeddingsComponent()
    component.api_key = None
    component.inference_endpoint = "https://api-inference.huggingface.co/models/"
    component.model_name = "BAAI/bge-large-en-v1.5"

    with pytest.raises(ValueError, match="API Key is required for non-local inference endpoints"):
        component.build_embeddings()


def test_huggingface_build_embeddings_local(mocker):
    """Test building embeddings in a local inference setup."""
    component = HuggingFaceInferenceAPIEmbeddingsComponent()
    component.inference_endpoint = "http://localhost:8080"
    component.api_key = None  # Local inference doesn't require an API key
    component.model_name = "sentence-transformers/all-mpnet-base-v2"

    # Mock the validation and embedding creation
    mock_validate = mocker.patch.object(component, "validate_inference_endpoint")
    mock_create = mocker.patch.object(component, "create_huggingface_embeddings", return_value=MagicMock())

    embeddings = component.build_embeddings()

    mock_validate.assert_called_once()
    mock_create.assert_called_once()
    assert isinstance(embeddings, Embeddings)


def test_huggingface_build_embeddings_connection_error(mocker):
    """Test error handling when the HuggingFace API connection fails."""
    component = HuggingFaceInferenceAPIEmbeddingsComponent()
    component.api_key = "test-key"
    component.inference_endpoint = "https://api-inference.huggingface.co/models/"
    component.model_name = "BAAI/bge-large-en-v1.5"

    mock_create = mocker.patch.object(component, "create_huggingface_embeddings", side_effect=Exception("Connection error"))

    with pytest.raises(ValueError, match="Could not connect to HuggingFace Inference API."):
        component.build_embeddings()

    mock_create.assert_called_once()

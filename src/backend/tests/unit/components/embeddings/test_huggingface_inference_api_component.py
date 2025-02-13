import pytest
from langflow.components.embeddings import HuggingFaceInferenceAPIEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestHuggingFaceInferenceAPIEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return HuggingFaceInferenceAPIEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "inference_endpoint": "https://api-inference.huggingface.co/models/",
            "model_name": "BAAI/bge-large-en-v1.5",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "huggingface", "file_name": "HuggingFaceInferenceAPIEmbeddings"},
        ]

    def test_validate_inference_endpoint_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component.validate_inference_endpoint(default_kwargs["inference_endpoint"]) is True

    def test_validate_inference_endpoint_invalid_url(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Invalid inference endpoint format"):
            component.validate_inference_endpoint("invalid_url")

    def test_validate_inference_endpoint_unreachable(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Inference endpoint 'https://invalid.endpoint' is not responding"):
            component.validate_inference_endpoint("https://invalid.endpoint")

    def test_build_embeddings_local(self, component_class, default_kwargs):
        local_kwargs = {**default_kwargs, "api_key": None, "inference_endpoint": "http://localhost:8080"}
        component = component_class(**local_kwargs)
        result = component.build_embeddings()
        assert result is not None

    def test_build_embeddings_non_local_without_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.api_key = None
        with pytest.raises(ValueError, match="API Key is required for non-local inference endpoints"):
            component.build_embeddings()

    def test_build_embeddings_connection_error(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.create_huggingface_embeddings = pytest.Mock(side_effect=Exception("Connection error"))
        with pytest.raises(ValueError, match="Could not connect to HuggingFace Inference API."):
            component.build_embeddings()

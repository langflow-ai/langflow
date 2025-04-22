from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from langflow.components.models import MaritalkModelComponent
from langflow.components.models.maritalk import DEFAULT_MODELS, MARITACA_API_URL, REQUEST_TIMEOUT

from tests.base import DID_NOT_EXIST, SUPPORTED_VERSIONS, ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMaritalkModelComponent(ComponentTestBaseWithClient):
    """Test MaritalkModelComponent."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        from langflow.components.models import MaritalkModelComponent

        return MaritalkModelComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {"model_name": "sabia-3", "api_key": "test-key"}

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for version-specific files."""
        return [
            {"version": "1.0.19", "module": "models", "file_name": "Maritalk"},
            {"version": "1.1.0", "module": "models", "file_name": "maritalk"},
            {"version": "1.1.1", "module": "models", "file_name": "maritalk"},
        ]

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS)
    def test_component_versions(
        self, version: str, default_kwargs: dict[str, Any], file_names_mapping: list[dict[str, str]], component_class
    ) -> None:
        """Test if the component works across different versions, with minimal validation."""
        version_mappings = {mapping["version"]: mapping for mapping in file_names_mapping}

        mapping = version_mappings[version]
        if mapping["file_name"] is DID_NOT_EXIST:
            pytest.skip(f"Skipping version {version} as it does not have a file name defined.")

        component = component_class(**default_kwargs)
        assert component is not None

    @patch("requests.get")
    def test_fetch_models(self, mock_get, component_class, default_kwargs):
        """Test fetch_models method."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "sabia-3", "created": 100},
                {"id": "sabiazinho-3", "created": 200},
                {"id": "new-model", "created": 300},
            ]
        }
        mock_get.return_value = mock_response

        # Create component and call fetch_models
        component = component_class(**default_kwargs)
        models = component.fetch_models()

        # Assertions
        mock_get.assert_called_once_with(
            MARITACA_API_URL, headers={"Authorization": f"Key {default_kwargs['api_key']}"}, timeout=REQUEST_TIMEOUT
        )
        # Modelos são ordenados do mais recente para o mais antigo
        assert models == ["new-model", "sabiazinho-3", "sabia-3"]

    @patch("requests.get")
    def test_fetch_models_api_error(self, mock_get, component_class, default_kwargs):
        """Test fetch_models method with API error."""
        # Setup mock response for API error
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        # Create component and call fetch_models
        component = component_class(**default_kwargs)
        models = component.fetch_models()

        # Assertions
        mock_get.assert_called_once_with(
            MARITACA_API_URL, headers={"Authorization": f"Key {default_kwargs['api_key']}"}, timeout=REQUEST_TIMEOUT
        )
        assert models == DEFAULT_MODELS

    @patch("requests.get")
    def test_fetch_models_request_exception(self, mock_get, component_class, default_kwargs):
        """Test fetch_models method with request exception."""
        # Setup mock to raise an exception
        mock_get.side_effect = requests.RequestException("Connection error")

        # Create component and call fetch_models
        component = component_class(**default_kwargs)
        models = component.fetch_models()

        # Assertions
        mock_get.assert_called_once_with(
            MARITACA_API_URL, headers={"Authorization": f"Key {default_kwargs['api_key']}"}, timeout=REQUEST_TIMEOUT
        )
        assert models == DEFAULT_MODELS

    async def test_update_build_config(self, component_class, default_kwargs):
        """Test update_build_config method."""
        # Patch fetch_models
        with patch.object(
            MaritalkModelComponent, "fetch_models", return_value=["new-model", "sabia-3", "sabiazinho-3"]
        ):
            # Create component
            component = component_class(**default_kwargs)

            # Create build config
            build_config = {
                "model_name": {"options": [], "value": ""},
                "api_key": {"display_name": "API Key"},
            }

            # Test update_build_config
            updated_config = await component.update_build_config(build_config, None, "api_key")

            # Verify model options were updated
            assert set(updated_config["model_name"]["options"]) == {
                "new-model",
                "sabia-3",
                "sabiazinho-3",
                DEFAULT_MODELS[0],
                DEFAULT_MODELS[1],
            }
            assert updated_config["model_name"]["value"] in updated_config["model_name"]["options"]

    async def test_update_build_config_with_existing_value(self, component_class, default_kwargs):
        """Test update_build_config method with existing value."""
        # Patch fetch_models
        with patch.object(
            MaritalkModelComponent, "fetch_models", return_value=["new-model", "sabia-3", "sabiazinho-3"]
        ):
            # Create component
            component = component_class(**default_kwargs)

            # Create build config with existing valid value
            build_config = {
                "model_name": {"options": [], "value": "sabia-3"},
                "api_key": {"display_name": "API Key"},
            }

            # Test update_build_config
            updated_config = await component.update_build_config(build_config, None, "api_key")

            # Verify model options were updated but value preserved
            assert set(updated_config["model_name"]["options"]) == {
                "new-model",
                "sabia-3",
                "sabiazinho-3",
                DEFAULT_MODELS[0],
                DEFAULT_MODELS[1],
            }
            assert updated_config["model_name"]["value"] == "sabia-3"

    @patch("langflow.components.models.maritalk.ChatMaritalk")
    def test_build_model(self, mock_chat_maritalk, component_class, default_kwargs):
        """Test build_model method."""
        # Create component with all parameters
        full_kwargs = {
            **default_kwargs,
            "temperature": 0.7,
            "max_tokens": 512,
            "system_message": "You are a helpful assistant.",
        }
        component = component_class(**full_kwargs)

        # Call build_model
        model = component.build_model()

        # Verify ChatMaritalk was constructed with correct params
        mock_chat_maritalk.assert_called_once_with(
            max_tokens=512,
            model="sabia-3",
            api_key="test-key",
            temperature=0.7,
            system_message="You are a helpful assistant.",
        )
        assert model == mock_chat_maritalk.return_value

    def test_build_model_missing_model_name(self, component_class):
        """Test build_model method with missing model_name."""
        # Create component without model_name
        component = component_class(api_key="test-key")
        component.model_name = None

        # Verify ValueError is raised when model_name is missing
        with pytest.raises(ValueError, match="Model name is required"):
            component.build_model()

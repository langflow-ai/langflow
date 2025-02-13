import pytest
from langflow.components.icosacomputing import CombinatorialReasonerComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCombinatorialReasonerComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CombinatorialReasonerComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "prompt": "What is the capital of France?",
            "openai_api_key": "test_api_key",
            "username": "test_user",
            "password": "test_password",
            "model_name": "gpt-3.5-turbo",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "combinatorial_reasoner", "file_name": "CombinatorialReasoner"},
        ]

    def test_build_prompt(self, component_class, default_kwargs, mocker):
        mock_response = {"prompt": "The capital of France is Paris.", "finalReasons": [["Reason 1"], ["Reason 2"]]}
        mocker.patch("requests.post", return_value=mocker.Mock(status_code=200, json=lambda: mock_response))

        component = component_class(**default_kwargs)
        result = component.build_prompt()

        assert result == "The capital of France is Paris."
        assert component.reasons == [["Reason 1"], ["Reason 2"]]

    def test_build_reasons(self, component_class, default_kwargs, mocker):
        mock_response = {"prompt": "The capital of France is Paris.", "finalReasons": [["Reason 1"], ["Reason 2"]]}
        mocker.patch("requests.post", return_value=mocker.Mock(status_code=200, json=lambda: mock_response))

        component = component_class(**default_kwargs)
        component.build_prompt()  # Call to set reasons
        result = component.build_reasons()

        assert result.value == ["Reason 1", "Reason 2"]

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."

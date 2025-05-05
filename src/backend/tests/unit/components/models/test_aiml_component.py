import pytest
from langflow.components.models import AIMLModelComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAIMLModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AIMLModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "AIML_API_KEY",
            "model_name": "gpt-3.5-turbo",
            "max_tokens": 100,
            "aiml_api_base": "https://api.aimlapi.com",
            "temperature": 0.5,
            "model_kwargs": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "aiml", "file_name": "AIMLModel"},
            {"version": "1.1.0", "module": "aiml", "file_name": "aiml_model"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert model.model == default_kwargs["model_name"]
        assert model.temperature == default_kwargs["temperature"]
        assert model.api_key == default_kwargs["api_key"].get_secret_value()

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "gpt-3.5-turbo", "model_name")
        assert "options" in updated_config["model_name"]
        assert len(updated_config["model_name"]["options"]) > 0

    async def test_invalid_api_key(self, component_class, default_kwargs):
        default_kwargs["api_key"] = "INVALID_API_KEY"
        component = component_class(**default_kwargs)
        with pytest.raises(Exception) as exc_info:
            await component.build_model()
        assert "Invalid API key" in str(exc_info.value)

    async def test_all_versions_have_a_file_name_defined(self, file_names_mapping):
        if not file_names_mapping:
            pytest.skip("No file names mapping defined for this component.")
        version_mappings = {mapping["version"]: mapping for mapping in file_names_mapping}

        for version in SUPPORTED_VERSIONS:
            if version not in version_mappings:
                supported_versions = ", ".join(sorted(m["version"] for m in file_names_mapping))
                msg = (
                    f"Version {version} not found in file_names_mapping for {self.__class__.__name__}.\n"
                    f"Currently defined versions: {supported_versions}\n"
                    "Please add this version to your component's file_names_mapping."
                )
                raise AssertionError(msg)

            mapping = version_mappings[version]
            assert mapping["file_name"] is not None, (
                f"file_name is None for version {version} in {self.__class__.__name__}."
            )
            assert mapping["module"] is not None, f"module is None for version {version} in {self.__class__.__name__}."

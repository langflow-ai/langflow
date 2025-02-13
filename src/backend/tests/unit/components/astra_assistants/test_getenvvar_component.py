import os

import pytest

from langflow.components.astra_assistants import GetEnvVar
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGetEnvVarComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GetEnvVar

    @pytest.fixture
    def default_kwargs(self):
        return {"env_var_name": "TEST_ENV_VAR"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_process_inputs_env_var_set(self, component_class, default_kwargs):
        os.environ["TEST_ENV_VAR"] = "test_value"
        component = component_class(**default_kwargs)
        result = component.process_inputs()
        assert result.text == "test_value"

    def test_process_inputs_env_var_not_set(self, component_class, default_kwargs):
        if "TEST_ENV_VAR" in os.environ:
            del os.environ["TEST_ENV_VAR"]
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Environment variable TEST_ENV_VAR not set"):
            component.process_inputs()

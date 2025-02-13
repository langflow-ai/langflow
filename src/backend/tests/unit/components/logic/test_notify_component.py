import pytest

from langflow.components.logic import NotifyComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestNotifyComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return NotifyComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"name": "Test Notification", "data": {"key": "value"}, "append": False}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "notifications", "file_name": "Notify"},
        ]

    def test_build_config(self, component_class):
        component = component_class()
        config = component.build_config()
        assert "name" in config
        assert "data" in config
        assert "append" in config

    def test_build_with_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.build(**default_kwargs)
        assert result is not None
        assert result.text == '{"key": "value"}'
        assert component.status == result

    def test_build_with_string_data(self, component_class):
        component = component_class(name="Test Notification")
        result = component.build(name="Test Notification", data="Simple text")
        assert result.text == "Simple text"
        assert component.status == result

    def test_build_with_dict_data(self, component_class):
        component = component_class(name="Test Notification")
        result = component.build(name="Test Notification", data={"key": "value"})
        assert result.data == {"key": "value"}
        assert component.status == result

    def test_build_with_no_data(self, component_class):
        component = component_class(name="Test Notification")
        result = component.build(name="Test Notification", data=None)
        assert result.text == ""
        assert component.status == result

    def test_build_with_append(self, component_class):
        component = component_class(name="Test Notification")
        component.build(name="Test Notification", data={"key": "value"}, append=True)
        assert component.status.data == {"key": "value"}
        assert component._vertex.is_state is True

import pytest
from langflow.components.helpers import CurrentDateComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCurrentDateComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CurrentDateComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"timezone": "UTC"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "current_date", "file_name": "CurrentDate"},
        ]

    def test_get_current_date(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.get_current_date()
        assert result is not None
        assert "Current date and time in UTC:" in result.text

    def test_get_current_date_invalid_timezone(self, component_class):
        component = component_class(timezone="Invalid/Timezone")
        result = component.get_current_date()
        assert result is not None
        assert "Error:" in result.text

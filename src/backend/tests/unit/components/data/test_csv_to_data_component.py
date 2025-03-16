import pytest
from langflow.components.data import CSVToDataComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCSVToDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CSVToDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"csv_string": "name,age\nAlice,30\nBob,25", "text_key": "name", "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_load_csv_from_string(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.load_csv_to_data()
        assert len(result) == 2
        assert result[0].data["name"] == "Alice"
        assert result[1].data["age"] == "25"

    def test_load_csv_from_file(self, component_class, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,age\nAlice,30\nBob,25")
        component = component_class(csv_file=str(csv_file), text_key="name", _session_id="123")
        result = component.load_csv_to_data()
        assert len(result) == 2
        assert result[0].data["name"] == "Alice"
        assert result[1].data["age"] == "25"

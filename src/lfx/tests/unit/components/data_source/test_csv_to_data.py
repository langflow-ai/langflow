from types import SimpleNamespace

import pytest
from lfx.components.data_source.csv_to_data import CSVToDataComponent

# Excel's "CSV UTF-8" format starts the file with a UTF-8 byte order mark.
CSV_WITH_BOM = b"\xef\xbb\xbfname,age\r\nAlice,30\r\nBob,25\r\n"


@pytest.fixture(autouse=True)
def _unrestricted_file_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests read local files directly; opt out of file containment."""
    monkeypatch.setattr(
        "lfx.utils.file_path_security.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(restrict_local_file_access=False)),
    )


@pytest.mark.parametrize("input_name", ["csv_file", "csv_path"])
def test_load_csv_strips_utf8_byte_order_mark(tmp_path, input_name):
    csv_file = tmp_path / "people.csv"
    csv_file.write_bytes(CSV_WITH_BOM)
    component = CSVToDataComponent(**{input_name: str(csv_file)}, text_key="name")

    result = component.load_csv_to_data()

    assert [row.data for row in result] == [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
    assert [row.get_text() for row in result] == ["Alice", "Bob"]


@pytest.mark.parametrize("input_name", ["csv_file", "csv_path"])
def test_load_csv_without_byte_order_mark(tmp_path, input_name):
    csv_file = tmp_path / "people.csv"
    csv_file.write_bytes(CSV_WITH_BOM.removeprefix(b"\xef\xbb\xbf"))
    component = CSVToDataComponent(**{input_name: str(csv_file)}, text_key="name")

    result = component.load_csv_to_data()

    assert [row.data for row in result] == [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]

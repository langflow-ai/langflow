"""Read File CSV delimiter tests using the pandas parser for local and S3 data."""

import csv
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.components.files_and_knowledge.file import FileComponent


@pytest.mark.parametrize("storage_type", ["local", "s3"])
@pytest.mark.parametrize("delimiter", [",", ";", "|", "\t", r"\t"])
def test_csv_delimiter_preserves_quoted_fields(tmp_path, monkeypatch, storage_type, delimiter):
    component = FileComponent()
    component.set(csv_delimiter=delimiter)
    separator = "\t" if delimiter == r"\t" else delimiter
    text = StringIO()
    writer = csv.writer(text, delimiter=separator)
    writer.writerow(["name", "count"])
    writer.writerow([f"quoted{separator}value\nsecond line", 2])
    content = text.getvalue().encode()
    path = tmp_path / "sample.CSV"
    path.write_bytes(content)
    monkeypatch.setattr(
        "lfx.base.data.base_file.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(storage_type=storage_type)),
    )
    read_bytes = AsyncMock(return_value=content)
    monkeypatch.setattr("lfx.base.data.base_file.read_file_bytes", read_bytes)

    rows = component.load_files_structured_helper(str(path))

    assert rows == [{"name": f"quoted{separator}value\nsecond line", "count": 2}]
    if storage_type == "s3":
        read_bytes.assert_awaited_once_with(str(path))
    else:
        read_bytes.assert_not_awaited()


def test_csv_delimiter_defaults_to_comma(tmp_path):
    component = FileComponent()
    path = tmp_path / "sample.csv"
    path.write_text("name,count\nexample,2\n", encoding="utf-8")

    assert component.load_files_structured_helper(str(path)) == [{"name": "example", "count": 2}]


def test_csv_delimiter_applies_to_structured_output(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("name;count\nexample;2\n", encoding="utf-8")
    component = FileComponent()
    component.set(path=[str(path)], csv_delimiter=";")

    result = component.load_files_structured()

    assert result.to_dict("records") == [{"name": "example", "count": 2}]
    assert result.attrs["source_file_path"] == str(path)


@pytest.mark.parametrize("delimiter", ["", "||", "\n", "\r", "\0"])
def test_invalid_csv_delimiter_reports_configuration_error(tmp_path, delimiter):
    component = FileComponent()
    component.set(csv_delimiter=delimiter)
    path = tmp_path / "sample.csv"
    path.write_text("name,count\nexample,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="CSV Delimiter must be a single character"):
        component.load_files_structured_helper(str(path))


def test_csv_delimiter_does_not_affect_excel(tmp_path):
    import pandas as pd

    component = FileComponent()
    component.set(csv_delimiter="invalid")
    path = tmp_path / "sample.xlsx"
    pd.DataFrame([{"name": "example", "count": 2}]).to_excel(path, index=False)

    assert component.load_files_structured_helper(str(path)) == [{"name": "example", "count": 2}]

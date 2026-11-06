"""Text encoding selection is visible and explicit overrides are strict."""

from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.data.utils import aparse_text_file_to_data, read_text_file, read_text_file_async
from lfx.components.files_and_knowledge.file import FileComponent
from lfx.services.deps import get_settings_service


@pytest.fixture(autouse=True)
def local_storage(monkeypatch):
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "storage_type", "local")
    monkeypatch.setattr(settings, "restrict_local_file_access", False)


@pytest.mark.parametrize("reader", [read_text_file, read_text_file_async])
@pytest.mark.parametrize("content", ["Café résumé naïve", "“Oui”—dit-il.\n"])
async def test_explicit_cp1252_preserves_short_text(tmp_path, reader, content):
    file_path = tmp_path / "short.txt"
    file_path.write_bytes(content.encode("cp1252"))

    result = reader(str(file_path), encoding="cp1252")
    if reader is read_text_file_async:
        result = await result

    assert result == content


@pytest.mark.parametrize("reader", [read_text_file, read_text_file_async])
@pytest.mark.parametrize("encoding", ["utf-8", "unknown-encoding"])
async def test_explicit_encoding_does_not_fall_back(tmp_path, reader, encoding):
    file_path = tmp_path / "short.txt"
    file_path.write_bytes("Café".encode("cp1252"))

    if reader is read_text_file_async:
        with pytest.raises((UnicodeDecodeError, LookupError)):
            await reader(str(file_path), encoding=encoding)
    else:
        with pytest.raises((UnicodeDecodeError, LookupError)):
            reader(str(file_path), encoding=encoding)


@pytest.mark.parametrize("reader", [read_text_file, read_text_file_async])
@pytest.mark.parametrize("content", ["Café résumé naïve", "“Oui”—dit-il.\n"])
async def test_automatic_legacy_encoding_is_reported(tmp_path, caplog, reader, content):
    file_path = tmp_path / "short.txt"
    file_path.write_bytes(content.encode("cp1252"))

    result = reader(str(file_path))
    if reader is read_text_file_async:
        result = await result

    assert "Auto-selected text encoding" in caplog.text
    assert "specify an encoding" in caplog.text


async def test_metadata_records_successful_fallback_not_detector_guess(tmp_path):
    file_path = tmp_path / "short.txt"
    # The trailing accented byte is invalid in ASCII, UTF-8, and GB18030.
    file_path.write_bytes("Café".encode("cp1252"))

    with patch("lfx.base.data.utils.chardet.detect", return_value={"encoding": "ascii", "confidence": 0.99}):
        result = await aparse_text_file_to_data(str(file_path), silent_errors=False)

    assert result.data["encoding"] == "cp1252"
    assert result.text == "Café"


async def test_storage_reader_honors_override_and_reports_encoding(monkeypatch):
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "storage_type", "s3")
    content = "Café résumé naïve"
    with patch("lfx.base.data.utils.read_file_bytes", new=AsyncMock(return_value=content.encode("cp1252"))):
        result = await aparse_text_file_to_data("user-id/cafe.txt", silent_errors=False, encoding="cp1252")

    assert result.text == content
    assert result.data["encoding"] == "cp1252"


@pytest.mark.parametrize("encoding", ["gb18030", "big5", "shift_jis", "utf-8"])
async def test_explicit_legacy_and_unicode_encodings(tmp_path, encoding):
    content = "中文測試" if encoding in {"gb18030", "big5"} else "日本語のテスト"
    file_path = tmp_path / "text.txt"
    file_path.write_bytes(content.encode(encoding))

    assert read_text_file(str(file_path), encoding=encoding) == content
    assert await read_text_file_async(str(file_path), encoding=encoding) == content


async def test_component_exposes_auto_encoding_and_invalidates_cache_for_override(tmp_path):
    file_path = tmp_path / "cafe.txt"
    content = "Café résumé naïve"
    raw = content.encode("cp1252")
    file_path.write_bytes(raw)
    component = FileComponent()
    component.path = [str(file_path)]

    automatic = await component.aload_files_message()
    chosen = automatic.data["encoding"]
    assert automatic.text == raw.decode(chosen)
    assert any(chosen in str(log.message) and "Text Encoding" in str(log.message) for log in component._logs)

    component.text_encoding = "cp1252"
    explicit = await component.aload_files_message()
    assert explicit.text == content
    assert explicit.data["encoding"] == "cp1252"


async def test_component_retains_encoding_for_each_source_file(tmp_path):
    paths = [tmp_path / "cafe.txt", tmp_path / "quotes.txt"]
    contents = ["Café résumé naïve", "“Oui”—dit-il.\n"]
    for path, content in zip(paths, contents, strict=True):
        path.write_bytes(content.encode("cp1252"))
    component = FileComponent()
    component.path = [str(path) for path in paths]
    component.text_encoding = "cp1252"

    message = await component.aload_files_message()

    assert [source["text"] for source in message.data["source_files"]] == contents
    assert [source["encoding"] for source in message.data["source_files"]] == ["cp1252", "cp1252"]


async def test_component_csv_structured_output_honors_encoding(tmp_path):
    file_path = tmp_path / "cafe.csv"
    file_path.write_bytes("name\nCafé\n".encode("cp1252"))
    component = FileComponent()
    component.path = [str(file_path)]
    component.text_encoding = "cp1252"

    result = await component.aload_files_structured()

    assert result.to_dict("records") == [{"name": "Café"}]


async def test_component_invalid_encoding_surfaces_error(tmp_path):
    file_path = tmp_path / "cafe.txt"
    file_path.write_bytes("Café".encode("cp1252"))
    component = FileComponent()
    component.path = [str(file_path)]
    component.text_encoding = "utf-8"

    with pytest.raises(ValueError, match="utf-8"):
        await component.aload_files_message()

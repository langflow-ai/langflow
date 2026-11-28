import io
import zipfile
from unittest.mock import Mock

import orjson
import pytest
from langflow.api.utils import zip_utils


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
async def test_imports_zip_entry_across_multiple_reads(compression, monkeypatch):
    flow = {"name": "example", "description": "A test flow"}
    payload = orjson.dumps(flow)
    monkeypatch.setattr(zip_utils, "_ZIP_READ_CHUNK_BYTES", 8)
    monkeypatch.setattr(zip_utils, "MAX_ENTRY_UNCOMPRESSED_BYTES", len(payload))
    monkeypatch.setattr(zip_utils, "MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES", len(payload))
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=compression) as entries:
        entries.writestr("flow.json", payload)

    assert await zip_utils.extract_flows_from_zip(archive.getvalue()) == [flow]


@pytest.mark.parametrize("output", [b"a", b"abc"])
def test_rejects_entry_when_reader_reports_a_different_size(output):
    info = zipfile.ZipInfo("flow.json")
    info.file_size = 2
    archive = Mock(spec=zipfile.ZipFile)
    archive.open.return_value = io.BytesIO(output)

    with pytest.raises(ValueError, match="Uncompressed size does not match"):
        zip_utils._read_zip_entry(archive, info)


async def test_rejects_zip_entry_with_invalid_checksum():
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as entries:
        entries.writestr("flow.json", b'{"name":"example"}')
    corrupted = archive.getvalue().replace(b'"example"', b'"changed"', 1)

    with pytest.raises(ValueError, match=r"Invalid ZIP entry 'flow\.json'") as error:
        await zip_utils.extract_flows_from_zip(corrupted)

    assert isinstance(error.value.__cause__, zipfile.BadZipFile)


async def test_rejects_unsupported_zip_compression():
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_BZIP2) as entries:
        entries.writestr("flow.json", b"{}")

    with pytest.raises(ValueError, match="Unsupported compression method"):
        await zip_utils.extract_flows_from_zip(archive.getvalue())

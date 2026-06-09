import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import aiofiles
import pytest
from lfx.schema.image import (
    get_file_paths,
    get_files,
    is_image_file,
)
from PIL import Image as PILImage


@pytest.fixture
def file_image():
    image = PILImage.new("RGB", (100, 100), (255, 0, 0))
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as temp_file:
        image.save(temp_file.name)
        yield temp_file.name


@pytest.fixture
def file_txt():
    content = """\
line1: This is an example text file.
line2: It can be used for testing.
line3: End of file.
"""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(content.encode())
        temp_file.flush()
        yield temp_file.name


def test_is_image_file(file_image):
    assert is_image_file(file_image) is True


def test_is_image_file__not_image(file_txt):
    assert is_image_file(file_txt) is False


def test_get_file_paths(file_image, file_txt):
    files = [file_image, file_txt]
    result = get_file_paths(files)
    expected_len = 2
    assert len(result) == expected_len
    assert result[0].endswith(".png")
    assert result[1].endswith(".txt")


def test_get_file_paths_with_dicts():
    files = [{"path": "test.png"}, {"path": "test.txt"}]
    result = get_file_paths(files)
    expected_len = 2
    assert len(result) == expected_len
    assert result[0].endswith(".png")
    assert result[1].endswith(".txt")


def test_get_file_paths__empty():
    result = get_file_paths([])
    expected_len = 0
    assert len(result) == expected_len


@pytest.mark.asyncio
async def test_get_files(file_image, file_txt, caplog):  # noqa: ARG001
    file_paths = [file_image, file_txt]

    result = await get_files(file_paths)

    for index, file in enumerate(result):
        async with aiofiles.open(file_paths[index], "rb") as f:
            assert file == await f.read()


@pytest.mark.asyncio
async def test_get_files__convert_to_base64(file_image, file_txt, caplog):  # noqa: ARG001
    file_paths = [file_image, file_txt]

    result = await get_files(file_paths, convert_to_base64=True)

    for index, file in enumerate(result):
        async with aiofiles.open(file_paths[index], "rb") as f:
            assert file != await f.read()


@pytest.mark.asyncio
async def test_get_files__empty():
    result = await get_files([])

    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_files_with_storage_service_local_path():
    """Test that get_files uses parse_file_path for local storage paths."""
    mock_storage = MagicMock()
    mock_storage.parse_file_path = MagicMock(return_value=("flow_123", "image.png"))
    mock_storage.get_file = AsyncMock(return_value=b"fake image content")

    with patch("lfx.schema.image.get_storage_service", return_value=mock_storage):
        result = await get_files(["/data/flow_123/image.png"])

        # Verify parse_file_path was called with the correct path
        mock_storage.parse_file_path.assert_called_once_with("/data/flow_123/image.png")
        # Verify get_file was called with parsed flow_id and file_name
        mock_storage.get_file.assert_called_once_with(flow_id="flow_123", file_name="image.png")
        # Verify result contains the file content
        assert result == [b"fake image content"]


@pytest.mark.asyncio
async def test_get_files_with_storage_service_s3_path():
    """Test that get_files uses parse_file_path for S3 storage paths."""
    mock_storage = MagicMock()
    # S3 path with prefix
    mock_storage.parse_file_path = MagicMock(return_value=("flow_456", "document.pdf"))
    mock_storage.get_file = AsyncMock(return_value=b"fake pdf content")

    with patch("lfx.schema.image.get_storage_service", return_value=mock_storage):
        result = await get_files(["files/flow_456/document.pdf"])

        # Verify parse_file_path was called with the S3 path
        mock_storage.parse_file_path.assert_called_once_with("files/flow_456/document.pdf")
        # Verify get_file was called with parsed flow_id and file_name
        mock_storage.get_file.assert_called_once_with(flow_id="flow_456", file_name="document.pdf")
        # Verify result contains the file content
        assert result == [b"fake pdf content"]


@pytest.mark.asyncio
async def test_get_files_with_storage_service_convert_to_base64():
    """Test that get_files converts to base64 when requested."""
    import base64

    mock_storage = MagicMock()
    mock_storage.parse_file_path = MagicMock(return_value=("flow_789", "test.txt"))
    mock_storage.get_file = AsyncMock(return_value=b"test content")

    with patch("lfx.schema.image.get_storage_service", return_value=mock_storage):
        result = await get_files(["flow_789/test.txt"], convert_to_base64=True)

        # Verify parse_file_path was called
        mock_storage.parse_file_path.assert_called_once_with("flow_789/test.txt")
        # Verify result is base64 encoded
        assert isinstance(result[0], str)
        assert result[0] == base64.b64encode(b"test content").decode("utf-8")


@pytest.mark.asyncio
async def test_get_files_with_storage_service_multiple_files():
    """Test that get_files handles multiple files correctly."""
    mock_storage = MagicMock()
    mock_storage.parse_file_path = MagicMock(side_effect=[("flow_1", "file1.txt"), ("flow_2", "file2.txt")])
    mock_storage.get_file = AsyncMock(side_effect=[b"content1", b"content2"])

    with patch("lfx.schema.image.get_storage_service", return_value=mock_storage):
        result = await get_files(["flow_1/file1.txt", "flow_2/file2.txt"])

        # Verify parse_file_path was called for each file
        assert mock_storage.parse_file_path.call_count == 2
        # Verify get_file was called for each file
        assert mock_storage.get_file.call_count == 2
        # Verify results
        assert result == [b"content1", b"content2"]

import tempfile

import aiofiles
import pytest
from PIL import Image as PILImage

from lfx.schema.image import (
    get_file_paths,
    get_files,
    is_image_file,
)


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

import io

import pytest
from httpx import AsyncClient


@pytest.fixture
def sample_text_file():
    """Create an in-memory text file for testing."""
    content = (
        "This is the first paragraph of content. It contains enough text to be split into chunks.\n\n"
        "This is the second paragraph. It discusses a different topic entirely.\n\n"
        "This is the third paragraph. It wraps up the document with some final thoughts.\n\n"
        "And here is a fourth paragraph to ensure we have enough text for chunking with smaller sizes."
    )
    return ("test_document.txt", content)


@pytest.fixture
def empty_text_file():
    """Create an empty in-memory text file for testing."""
    return ("empty.txt", "")


@pytest.fixture
def whitespace_text_file():
    """Create a whitespace-only in-memory text file for testing."""
    return ("whitespace.txt", "   \n\n   \t   ")


class TestPreviewChunks:
    """Tests for the POST /knowledge_bases/preview-chunks endpoint."""

    async def test_preview_chunks_basic(self, client: AsyncClient, logged_in_headers, sample_text_file):
        """Test basic chunk preview with default parameters."""
        file_name, file_content = sample_text_file
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
            data={
                "chunk_size": "100",
                "chunk_overlap": "20",
                "separator": "\\n",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 1

        file_preview = data["files"][0]
        assert file_preview["file_name"] == file_name
        assert file_preview["total_chunks"] > 0
        assert len(file_preview["preview_chunks"]) > 0

        # Check chunk structure
        chunk = file_preview["preview_chunks"][0]
        assert "content" in chunk
        assert "index" in chunk
        assert "char_count" in chunk
        assert "start" in chunk
        assert "end" in chunk
        assert chunk["index"] == 0
        assert chunk["char_count"] == len(chunk["content"])

    async def test_preview_chunks_respects_chunk_size(self, client: AsyncClient, logged_in_headers, sample_text_file):
        """Test that chunk sizes are respected."""
        file_name, file_content = sample_text_file
        chunk_size = 50
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
            data={
                "chunk_size": str(chunk_size),
                "chunk_overlap": "0",
                "separator": "\\n",
            },
        )

        assert response.status_code == 200
        data = response.json()
        file_preview = data["files"][0]
        assert file_preview["total_chunks"] > 1

        # Each preview chunk should not exceed the chunk_size
        for chunk in file_preview["preview_chunks"]:
            assert chunk["char_count"] <= chunk_size

    async def test_preview_chunks_max_chunks_limit(self, client: AsyncClient, logged_in_headers, sample_text_file):
        """Test that max_chunks limits the number of preview chunks returned."""
        file_name, file_content = sample_text_file
        max_chunks = 2
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
            data={
                "chunk_size": "50",
                "chunk_overlap": "0",
                "separator": "\\n",
                "max_chunks": str(max_chunks),
            },
        )

        assert response.status_code == 200
        data = response.json()
        file_preview = data["files"][0]

        # preview_chunks should be capped at max_chunks even if total_chunks is higher
        assert len(file_preview["preview_chunks"]) <= max_chunks
        assert file_preview["total_chunks"] >= len(file_preview["preview_chunks"])

    async def test_preview_chunks_empty_file(self, client: AsyncClient, logged_in_headers, empty_text_file):
        """Test preview with an empty file."""
        file_name, file_content = empty_text_file
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
            data={
                "chunk_size": "100",
                "chunk_overlap": "20",
                "separator": "\\n",
            },
        )

        assert response.status_code == 200
        data = response.json()
        file_preview = data["files"][0]
        assert file_preview["total_chunks"] == 0
        assert file_preview["preview_chunks"] == []

    async def test_preview_chunks_whitespace_file(self, client: AsyncClient, logged_in_headers, whitespace_text_file):
        """Test preview with a whitespace-only file."""
        file_name, file_content = whitespace_text_file
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
            data={
                "chunk_size": "100",
                "chunk_overlap": "20",
                "separator": "\\n",
            },
        )

        assert response.status_code == 200
        data = response.json()
        file_preview = data["files"][0]
        assert file_preview["total_chunks"] == 0
        assert file_preview["preview_chunks"] == []

    async def test_preview_chunks_with_separator(self, client: AsyncClient, logged_in_headers):
        """Test that separator parameter affects chunking."""
        content = "Section A---Section B---Section C"
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": ("sections.txt", io.BytesIO(content.encode()), "text/plain")},
            data={
                "chunk_size": "1000",
                "chunk_overlap": "0",
                "separator": "---",
            },
        )

        assert response.status_code == 200
        data = response.json()
        file_preview = data["files"][0]
        # With "---" as a separator and large chunk_size, the splitter should use it
        assert file_preview["total_chunks"] >= 1

    async def test_preview_chunks_default_parameters(self, client: AsyncClient, logged_in_headers, sample_text_file):
        """Test preview with default parameters (no data fields)."""
        file_name, file_content = sample_text_file
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 1

    async def test_preview_chunks_chunk_positions(self, client: AsyncClient, logged_in_headers, sample_text_file):
        """Test that chunk start/end positions are reasonable."""
        file_name, file_content = sample_text_file
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
            data={
                "chunk_size": "100",
                "chunk_overlap": "0",
                "separator": "\\n",
            },
        )

        assert response.status_code == 200
        data = response.json()
        file_preview = data["files"][0]

        for chunk in file_preview["preview_chunks"]:
            # start should be non-negative
            assert chunk["start"] >= 0
            # end should be after start
            assert chunk["end"] > chunk["start"]
            # end - start should equal the content length
            assert chunk["end"] - chunk["start"] == len(chunk["content"])

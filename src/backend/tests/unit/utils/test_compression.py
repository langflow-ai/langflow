import gzip
import json
from datetime import date, datetime, timezone
from unittest.mock import patch

from fastapi import Response
from langflow.utils.compression import compress_response


class TestCompressResponse:
    """Test cases for compress_response function."""

    def test_compress_response_simple_dict(self):
        """Test compressing a simple dictionary."""
        data = {"message": "hello", "status": "success"}

        response = compress_response(data)

        assert isinstance(response, Response)
        assert response.media_type == "application/json"
        assert response.headers["Content-Encoding"] == "gzip"
        assert response.headers["Vary"] == "Accept-Encoding"
        assert "Content-Length" in response.headers

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_simple_list(self):
        """Test compressing a simple list."""
        data = ["item1", "item2", "item3"]

        response = compress_response(data)

        assert isinstance(response, Response)
        assert response.media_type == "application/json"

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_string(self):
        """Test compressing a string."""
        data = "simple string message"

        response = compress_response(data)

        assert isinstance(response, Response)

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_number(self):
        """Test compressing numeric data."""
        data = 42

        response = compress_response(data)

        assert isinstance(response, Response)

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_boolean(self):
        """Test compressing boolean data."""
        data = True

        response = compress_response(data)

        assert isinstance(response, Response)

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_none(self):
        """Test compressing None value."""
        data = None

        response = compress_response(data)

        assert isinstance(response, Response)

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data is None

    def test_compress_response_nested_data(self):
        """Test compressing nested data structures."""
        data = {
            "users": [{"id": 1, "name": "Alice", "active": True}, {"id": 2, "name": "Bob", "active": False}],
            "metadata": {"total": 2, "page": 1, "has_more": False},
            "settings": None,
        }

        response = compress_response(data)

        assert isinstance(response, Response)

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_large_data(self):
        """Test compressing large data to verify compression effectiveness."""
        # Create large data that should compress well (repeated patterns)
        data = {"items": ["test_item"] * 1000, "metadata": {"repeated_value": "x" * 500}}

        response = compress_response(data)

        # Original JSON size
        original_json = json.dumps(data).encode("utf-8")
        original_size = len(original_json)
        compressed_size = len(response.body)

        # Verify compression occurred (should be significantly smaller)
        assert compressed_size < original_size
        assert compressed_size < original_size * 0.5  # At least 50% compression

        # Verify content integrity
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_unicode_data(self):
        """Test compressing data with unicode characters."""
        data = {
            "message": "Hello 世界! 🌍 Émojis and accénts",
            "unicode_string": "テスト データ",
            "special_chars": "àáâãäåæçèéêë",
        }

        response = compress_response(data)

        assert isinstance(response, Response)

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_empty_dict(self):
        """Test compressing empty dictionary."""
        data = {}

        response = compress_response(data)

        assert isinstance(response, Response)

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_empty_list(self):
        """Test compressing empty list."""
        data = []

        response = compress_response(data)

        assert isinstance(response, Response)

        # Decompress and verify content
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))
        assert parsed_data == data

    def test_compress_response_headers(self):
        """Test that response has correct headers."""
        data = {"test": "data"}

        response = compress_response(data)

        # Check required headers
        assert response.headers["Content-Encoding"] == "gzip"
        assert response.headers["Vary"] == "Accept-Encoding"
        assert response.headers["Content-Length"] == str(len(response.body))
        assert response.media_type == "application/json"

    def test_compress_response_content_length_accuracy(self):
        """Test that Content-Length header matches actual body length."""
        data = {"message": "test", "numbers": [1, 2, 3, 4, 5]}

        response = compress_response(data)

        content_length = int(response.headers["Content-Length"])
        actual_length = len(response.body)

        assert content_length == actual_length

    @patch("langflow.utils.compression.jsonable_encoder")
    def test_compress_response_jsonable_encoder_called(self, mock_encoder):
        """Test that jsonable_encoder is called on the data."""
        data = {"test": "data"}
        mock_encoder.return_value = data

        compress_response(data)

        mock_encoder.assert_called_once_with(data)

    @patch("langflow.utils.compression.gzip.compress")
    def test_compress_response_gzip_compression_level(self, mock_compress):
        """Test that gzip.compress is called with correct compression level."""
        data = {"test": "data"}
        mock_compress.return_value = b"compressed_data"

        compress_response(data)

        # Verify gzip.compress was called with compresslevel=6
        mock_compress.assert_called_once()
        call_args = mock_compress.call_args
        assert call_args[1]["compresslevel"] == 6

    def test_compress_response_with_custom_objects(self):
        """Test compressing data with objects that need JSON encoding."""
        data = {
            "timestamp": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "date": date(2023, 1, 1),
            "message": "test with custom objects",
        }

        response = compress_response(data)

        assert isinstance(response, Response)

        # Decompress and verify content (datetime should be converted to string)
        decompressed = gzip.decompress(response.body)
        parsed_data = json.loads(decompressed.decode("utf-8"))

        # Check that custom objects were properly serialized
        assert "timestamp" in parsed_data
        assert "date" in parsed_data
        assert parsed_data["message"] == "test with custom objects"

    def test_compress_response_compression_ratio(self):
        """Test compression ratio with different types of data."""
        # Highly compressible data (lots of repetition)
        repetitive_data = {"data": "a" * 1000}

        # Less compressible data (more random)
        import random
        import string

        random_data = {"data": ["".join(random.choices(string.ascii_letters, k=10)) for _ in range(100)]}  # noqa: S311

        rep_response = compress_response(repetitive_data)
        rand_response = compress_response(random_data)

        rep_original = len(json.dumps(repetitive_data).encode("utf-8"))
        rand_original = len(json.dumps(random_data).encode("utf-8"))

        rep_compressed = len(rep_response.body)
        rand_compressed = len(rand_response.body)

        # Repetitive data should have better compression ratio
        rep_ratio = rep_compressed / rep_original
        rand_ratio = rand_compressed / rand_original

        assert rep_ratio < rand_ratio  # Better compression for repetitive data
        assert rep_ratio < 0.1  # Very good compression for repetitive data

    def test_compress_response_error_handling_invalid_json(self):
        """Test error handling when data cannot be JSON serialized."""

        # Create an object that cannot be JSON serialized
        class NonSerializable:
            def __init__(self):
                self.func = lambda x: x

        data = {"object": NonSerializable()}

        # jsonable_encoder should handle this, but if it doesn't, test the behavior
        try:
            response = compress_response(data)
            # If no exception, verify the response is still valid
            assert isinstance(response, Response)
        except (TypeError, ValueError):
            # Expected behavior if jsonable_encoder can't handle the object
            pass

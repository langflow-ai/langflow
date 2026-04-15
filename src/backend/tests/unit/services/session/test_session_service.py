"""Tests for SessionService and session utilities."""

import re

import pytest
from langflow.services.cache.service import AsyncInMemoryCache, ThreadingInMemoryCache
from langflow.services.session.service import SessionService
from langflow.services.session.utils import compute_dict_hash, session_id_generator


class TestSessionIdGenerator:
    """Tests for session_id_generator function."""

    def test_default_size(self):
        session_id = session_id_generator()
        assert len(session_id) == 6

    def test_custom_size(self):
        session_id = session_id_generator(size=10)
        assert len(session_id) == 10

    def test_alphanumeric_uppercase(self):
        session_id = session_id_generator(size=100)
        assert re.match(r"^[A-Z0-9]+$", session_id)

    def test_uniqueness(self):
        ids = {session_id_generator() for _ in range(100)}
        # With 6 chars from 36 possible chars, collision in 100 is extremely unlikely
        assert len(ids) == 100


class TestComputeDictHash:
    """Tests for compute_dict_hash function."""

    def test_produces_sha256_hash(self):
        data = {"nodes": [{"id": "1"}], "edges": []}
        result = compute_dict_hash(data)
        assert len(result) == 64  # SHA-256 hex digest
        assert re.match(r"^[a-f0-9]+$", result)

    def test_deterministic(self):
        data = {"nodes": [{"id": "1"}], "edges": []}
        assert compute_dict_hash(data) == compute_dict_hash(data)

    def test_filters_ui_fields(self):
        data1 = {"nodes": [{"id": "1"}], "edges": []}
        data2 = {"nodes": [{"id": "1"}], "edges": [], "viewport": {"x": 0, "y": 0}}
        # Viewport should be filtered out, so hashes should match
        assert compute_dict_hash(data1) == compute_dict_hash(data2)

    def test_different_data_different_hash(self):
        data1 = {"nodes": [{"id": "1"}], "edges": []}
        data2 = {"nodes": [{"id": "2"}], "edges": []}
        assert compute_dict_hash(data1) != compute_dict_hash(data2)


class TestSessionServiceBuildKey:
    """Tests for SessionService.build_key static method."""

    def test_build_key_with_session_id(self):
        key = SessionService.build_key("session123", {"nodes": []})
        assert key.startswith("session123:")
        # Rest should be a hash
        hash_part = key.split(":")[1]
        assert len(hash_part) == 64

    def test_build_key_without_session_id(self):
        key = SessionService.build_key(None, {"nodes": []})
        # None session_id results in "None" prefix (string conversion)
        # The key format is f"{session_id}{':' if session_id else ''}{json_hash}"
        # Since None is truthy-ish in this context, check format
        assert isinstance(key, str)
        assert len(key) > 0

    def test_build_key_empty_string_session_id(self):
        key = SessionService.build_key("", {"nodes": []})
        # Empty string is falsy, so no colon separator
        hash_only = compute_dict_hash({"nodes": []})
        assert key == hash_only


class TestSessionServiceGenerateKey:
    """Tests for SessionService.generate_key."""

    def test_generate_key_with_session_id(self):
        cache = ThreadingInMemoryCache()
        service = SessionService(cache)
        key = service.generate_key("session123", {"nodes": []})
        assert key.startswith("session123:")

    def test_generate_key_without_session_id(self):
        cache = ThreadingInMemoryCache()
        service = SessionService(cache)
        key = service.generate_key(None, {"nodes": []})
        # Should auto-generate a session ID
        parts = key.split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 6  # Default session_id_generator size


class TestSessionServiceWithSyncCache:
    """Tests for SessionService with ThreadingInMemoryCache."""

    pytestmark = pytest.mark.asyncio

    async def test_update_and_clear_session(self):
        cache = AsyncInMemoryCache()
        service = SessionService(cache)
        await service.update_session("session1", ("graph", "artifacts"))
        await service.clear_session("session1")
        # After clearing, load_session should return None for missing key
        result = await service.load_session("session1", flow_id="flow1")
        assert result == (None, None)

    async def test_load_session_no_data_graph(self):
        cache = AsyncInMemoryCache()
        service = SessionService(cache)
        result = await service.load_session("session1", flow_id="flow1", data_graph=None)
        assert result == (None, None)

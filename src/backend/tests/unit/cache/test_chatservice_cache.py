import asyncio

import pytest

from langflow.services.chat.service import ChatService


class _FakeSyncCache:
    def __init__(self):
        self.store = {}

    def upsert(self, key, value, lock=None):  # noqa: ARG002
        self.store[str(key)] = value

    def __contains__(self, key):
        return str(key) in self.store

    def get(self, key, lock=None):  # noqa: ARG002
        return self.store.get(str(key))


@pytest.mark.asyncio
async def test_chatservice_set_cache_normalizes_payload():
    cs = ChatService()
    # Inject fake async cache
    fake = _FakeSyncCache()
    cs.cache_service = fake  # type: ignore

    dynamic_cls = type("C", (), {})
    value = {
        "built": True,
        "results": {"ok": 1},
        "built_object": dynamic_cls,  # not cacheable
        "artifacts": {},
        "built_result": {"foo": "bar"},
        "full_data": {"id": "v"},
    }

    ok = await cs.set_cache("k1", value)
    assert ok is True
    stored = fake.get("k1")

    assert stored["type"] == "normalized"
    result = stored["result"]
    assert result["__cache_vertex__"] is True
    assert result["built_object"] == {"__cache_placeholder__": "unbuilt"}

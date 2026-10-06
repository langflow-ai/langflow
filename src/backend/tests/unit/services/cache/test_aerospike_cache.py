"""Tests for AerospikeCache against an in-memory stand-in for the aerospike client.

The real client is an optional C extension and needs a running cluster, so these tests swap
in a fake module that mimics the subset of the client API the cache uses.
"""

import sys
import types

import dill
import pytest
from langflow.services.cache.service import AerospikeCache, parse_aerospike_hosts
from lfx.services.cache.utils import CACHE_MISS


class RecordNotFoundError(Exception):
    pass


class FakeClient:
    def __init__(self, config):
        self.config = config
        self.records: dict = {}
        self.connected = False
        self.ttls: dict = {}

    def connect(self):
        self.connected = True
        return self

    def is_connected(self):
        return self.connected

    def close(self):
        self.connected = False

    def get(self, key):
        if key not in self.records:
            raise RecordNotFoundError
        return key, {}, self.records[key]

    def put(self, key, bins, meta=None):
        self.records[key] = bins
        self.ttls[key] = (meta or {}).get("ttl")

    def remove(self, key):
        if key not in self.records:
            raise RecordNotFoundError
        del self.records[key]

    def exists(self, key):
        return key, ({"gen": 1} if key in self.records else None)

    def truncate(self, namespace, set_name, _nanos):
        for key in [k for k in self.records if k[0] == namespace and k[1] == set_name]:
            del self.records[key]


@pytest.fixture
def fake_aerospike(monkeypatch):
    clients: list[FakeClient] = []

    def client(config):
        c = FakeClient(config)
        clients.append(c)
        return c

    module = types.ModuleType("aerospike")
    module.client = client
    exception = types.ModuleType("aerospike.exception")
    exception.RecordNotFound = RecordNotFoundError
    module.exception = exception
    monkeypatch.setitem(sys.modules, "aerospike", module)
    monkeypatch.setitem(sys.modules, "aerospike.exception", exception)
    return clients


def _cache(**kwargs) -> AerospikeCache:
    cache = AerospikeCache(**kwargs)
    cache._signing_key = b"k" * 32  # inject a fixed key (no settings dependency)
    return cache


def test_parse_hosts():
    assert parse_aerospike_hosts("a:3100, b") == [("a", 3100), ("b", 3000)]
    with pytest.raises(ValueError, match="at least one host"):
        parse_aerospike_hosts(" , ")


def test_missing_client_package_raises_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "aerospike", None)
    with pytest.raises(ImportError, match=r"langflow-base\[aerospike\]"):
        AerospikeCache()


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_aerospike")
class TestAerospikeCacheOperations:
    async def test_round_trip_upsert_and_delete(self):
        cache = _cache(namespace="ns", set_name="cache")

        assert await cache.is_connected()
        assert await cache.get("missing") is CACHE_MISS
        assert not await cache.contains("k")

        await cache.set("k", {"a": 1})
        assert await cache.get("k") == {"a": 1}
        assert await cache.contains("k")

        await cache.upsert("k", {"b": 2})
        assert await cache.get("k") == {"a": 1, "b": 2}

        await cache.delete("k")
        await cache.delete("k")  # deleting a missing key is a no-op
        assert await cache.get("k") is CACHE_MISS

    async def test_clear_only_truncates_the_cache_set(self, fake_aerospike):
        cache = _cache(namespace="ns", set_name="cache")
        await cache.set("k", 1)
        client = fake_aerospike[0]
        client.records[("ns", "other", "x")] = {"v": b"keep"}

        await cache.clear()

        assert ("ns", "other", "x") in client.records
        assert await cache.get("k") is CACHE_MISS

    async def test_teardown_closes_and_reconnects_lazily(self, fake_aerospike):
        cache = _cache(user="u", password="p")  # noqa: S106
        await cache.set("k", 1)
        first = fake_aerospike[0]
        assert first.config["user"] == "u"

        await cache.teardown()
        assert not first.connected

        assert await cache.get("k") is CACHE_MISS  # new client, fresh fake store
        assert len(fake_aerospike) == 2

    async def test_unpicklable_value_skips_the_cache_and_drops_the_old_entry(self):
        import ssl

        cache = _cache()
        await cache.set("k", {"old": True})
        # Must not raise: dill raises a bare TypeError for an SSLContext.
        await cache.set("k", {"built_object": ssl.create_default_context()})

        assert await cache.get("k") is CACHE_MISS


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_aerospike")
class TestAerospikeCacheTTL:
    async def test_default_and_per_key_expiration(self, fake_aerospike):
        cache = _cache(namespace="ns", set_name="cache", expiration_time=3600)
        await cache.set("default", 1)
        await cache.set("short", 1, expiration_time=30)
        await cache.set("tiny", 1, expiration_time=0.2)
        await cache.set("forever", 1, expiration_time=-1)

        ttls = fake_aerospike[0].ttls
        assert ttls[("ns", "cache", "default")] == 3600
        assert ttls[("ns", "cache", "short")] == 30
        assert ttls[("ns", "cache", "tiny")] == 1  # never 0 (namespace default)
        assert ttls[("ns", "cache", "forever")] == -1  # never expire passes through


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_aerospike")
class TestAerospikeCacheIntegrity:
    """Stored payloads are only deserialized when their HMAC tag verifies (CWE-502)."""

    async def test_unsigned_payload_is_never_deserialized(self, fake_aerospike):
        ran = []

        class _Gadget:
            def __reduce__(self):
                return (ran.append, ("gadget-ran",))

        cache = _cache(namespace="ns", set_name="cache")
        await cache.is_connected()
        forged = b"\x00" * cache._HMAC_DIGEST_SIZE + dill.dumps(_Gadget())
        fake_aerospike[0].records[("ns", "cache", "k")] = {"v": bytearray(forged)}

        assert await cache.get("k") is CACHE_MISS
        assert ran == []

    async def test_tampered_payload_is_a_miss(self, fake_aerospike):
        cache = _cache(namespace="ns", set_name="cache")
        await cache.set("k", "value")
        record = fake_aerospike[0].records[("ns", "cache", "k")]
        record["v"][-1] ^= 0xFF

        assert await cache.get("k") is CACHE_MISS

    async def test_signed_entry_cannot_be_replayed_under_another_key(self, fake_aerospike):
        cache = _cache(namespace="ns", set_name="cache")
        await cache.set("a", "for-a")
        records = fake_aerospike[0].records
        records[("ns", "cache", "b")] = records[("ns", "cache", "a")]

        assert await cache.get("b") is CACHE_MISS

    async def test_entry_signed_with_another_key_is_a_miss(self):
        cache = _cache(namespace="ns", set_name="cache")
        await cache.set("k", "value")
        cache._signing_key = b"x" * 32  # e.g. a replica configured with a different CACHE_SIGNING_KEY

        assert await cache.get("k") is CACHE_MISS

    async def test_signing_key_differs_from_redis_for_the_same_secret(self, monkeypatch):
        from langflow.services.cache import service
        from langflow.services.cache.service import RedisCache

        monkeypatch.setattr(service, "_load_or_create_cache_signing_secret", lambda: "shared-secret")
        aerospike_cache = AerospikeCache()
        redis_cache = RedisCache.__new__(RedisCache)
        redis_cache._signing_key = None

        assert aerospike_cache._get_signing_key() != redis_cache._get_signing_key()


@pytest.mark.usefixtures("fake_aerospike")
def test_factory_builds_aerospike_cache(monkeypatch):
    from langflow.services.cache.factory import CacheServiceFactory
    from lfx.services.settings.base import Settings

    monkeypatch.setenv("LANGFLOW_CACHE_TYPE", "aerospike")
    monkeypatch.setenv("LANGFLOW_AEROSPIKE_HOSTS", "as1:3000,as2:3001")
    monkeypatch.setenv("LANGFLOW_AEROSPIKE_NAMESPACE", "lf")
    settings_service = types.SimpleNamespace(settings=Settings())

    cache = CacheServiceFactory().create(settings_service)

    assert isinstance(cache, AerospikeCache)
    assert cache.namespace == "lf"
    assert cache._config["hosts"] == [("as1", 3000), ("as2", 3001)]

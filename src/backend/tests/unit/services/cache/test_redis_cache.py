"""Tests for RedisCache teardown functionality."""

import hashlib
import hmac
import ssl
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis
import pytest
from langflow.services.cache.service import (
    RedisCache,
    _claim_cache_signing_secret,
    _load_or_create_cache_signing_secret,
    _read_existing_cache_signing_secret,
)
from lfx.services.cache.utils import CACHE_MISS
from pydantic import SecretStr


@pytest.mark.asyncio
class TestRedisCacheTeardown:
    """Test RedisCache teardown functionality."""

    async def test_teardown_closes_redis_client(self):
        """Test that teardown() calls aclose() on the Redis client."""
        # Mock the Redis client
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client

            # Create RedisCache instance
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)

            # Verify the client was created
            assert cache._client is mock_client

            # Call teardown
            await cache.teardown()

            # Verify aclose was called
            mock_client.aclose.assert_called_once()

    async def test_teardown_with_url(self):
        """Test that teardown() works with Redis URL configuration."""
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client

            # Create RedisCache instance with URL
            cache = RedisCache(url="redis://localhost:6379/0", expiration_time=3600)

            # Verify the client was created with from_url
            mock_redis_class.from_url.assert_called_once_with("redis://localhost:6379/0")
            assert cache._client is mock_client

            # Call teardown
            await cache.teardown()

            # Verify aclose was called
            mock_client.aclose.assert_called_once()

    async def test_is_external_async_base_cache_service(self):
        """Test that RedisCache is an instance of ExternalAsyncBaseCacheService."""
        from langflow.services.cache.base import ExternalAsyncBaseCacheService

        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client

            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)

            # Verify it's an instance of ExternalAsyncBaseCacheService
            assert isinstance(cache, ExternalAsyncBaseCacheService)

            # Verify teardown method exists and is callable
            assert hasattr(cache, "teardown")
            assert callable(cache.teardown)

            # Clean up
            await cache.teardown()

    async def test_preload_teardown_pattern(self):
        """Test the teardown pattern used in preload.py.

        ``teardown`` is now an abstract method on ``ExternalAsyncBaseCacheService``,
        so preload can call it directly without ``getattr`` fallbacks.
        """
        from langflow.services.cache.base import ExternalAsyncBaseCacheService

        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client

            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)

            if isinstance(cache, ExternalAsyncBaseCacheService):
                await cache.teardown()

            mock_client.aclose.assert_called_once()


_MARKER_PATH_HOLDER: list[str] = []


def _deser_side_effect(path: str) -> str:
    """Module-level callable used as a pickle reduce gadget in the test below."""
    _MARKER_PATH_HOLDER.append(path)
    return path


class _Gadget:
    """A picklable object whose deserialization would run _deser_side_effect."""

    def __init__(self, path: str) -> None:
        self.path = path

    def __reduce__(self):
        return (_deser_side_effect, (self.path,))


@pytest.mark.asyncio
class TestRedisCacheDeserializationIntegrity:
    """Regression (insecure dill.loads of untrusted Redis bytes)."""

    async def test_get_rejects_payload_without_valid_hmac(self):
        """A payload lacking a valid HMAC tag must not be deserialized (no gadget run)."""
        import dill
        from lfx.services.cache.utils import CACHE_MISS

        _MARKER_PATH_HOLDER.clear()
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            cache._signing_key = b"k" * 32  # inject a fixed key (no settings dependency)

            # Attacker-written value: a reduce gadget, prefixed with a WRONG 32-byte tag.
            forged = b"\x00" * cache._HMAC_DIGEST_SIZE + dill.dumps(_Gadget("gadget-ran"))
            mock_client.get.return_value = forged

            result = await cache.get("k")

            assert result is CACHE_MISS  # rejected before dill.loads
            assert _MARKER_PATH_HOLDER == []  # gadget never executed

    async def test_get_rejects_payload_shorter_than_tag(self):
        """A value too short to even hold a tag is a miss (cheapest attacker write)."""
        from lfx.services.cache.utils import CACHE_MISS

        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            cache._signing_key = b"k" * 32

            # Fewer bytes than the HMAC tag length: rejected before any slicing/HMAC.
            mock_client.get.return_value = b"short"

            assert await cache.get("k") is CACHE_MISS

    async def test_set_get_roundtrip_with_signature(self):
        """Values written by set() carry a valid tag and round-trip through get()."""
        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            cache._signing_key = b"k" * 32

            store: dict[str, bytes] = {}

            async def fake_setex(key, _ttl, value):
                store[key] = value
                return True

            async def fake_get(key):
                return store.get(key)

            mock_client.setex.side_effect = fake_setex
            mock_client.get.side_effect = fake_get

            await cache.set("k", {"a": 1, "b": [2, 3]})
            assert await cache.get("k") == {"a": 1, "b": [2, 3]}

    async def test_get_rejects_payload_replayed_under_different_key(self):
        """A validly-signed entry must not verify when relocated to another key.

        The integrity tag is bound to the namespaced Redis key, so copying a
        legitimately-signed payload from key ``a`` into the slot for key ``b``
        (cross-key substitution) is rejected as a miss instead of deserialized.
        """
        from lfx.services.cache.utils import CACHE_MISS

        with patch("redis.asyncio.StrictRedis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            cache._signing_key = b"k" * 32

            store: dict[str, bytes] = {}

            async def fake_setex(key, _ttl, value):
                store[key] = value
                return True

            async def fake_get(key):
                return store.get(key)

            mock_client.setex.side_effect = fake_setex
            mock_client.get.side_effect = fake_get

            # Write a real, validly-signed entry under key "a".
            await cache.set("a", {"secret": "for-a"})
            assert await cache.get("a") == {"secret": "for-a"}

            # Attacker relocates a's signed bytes into b's namespaced slot.
            store[cache._key("b")] = store[cache._key("a")]

            # The tag was bound to "a"'s key, so it fails verification under "b".
            assert await cache.get("b") is CACHE_MISS


@pytest.mark.asyncio
class TestRedisCacheSerialization:
    """Test that RedisCache degrades gracefully on unpicklable values.

    Live objects built during a flow run (e.g. an LLM client holding an
    ``ssl.SSLContext``, httpx clients, thread locks) cannot be serialized. The
    cache write must not crash the flow build; the value should simply be
    skipped. See https://github.com/langflow-ai/langflow/issues/13764.
    """

    def _cache(self) -> RedisCache:
        with patch("redis.asyncio.StrictRedis"):
            cache = RedisCache(expiration_time=3600)
        cache._client = fakeredis.FakeAsyncRedis()
        return cache

    async def test_set_unpicklable_value_does_not_raise(self):
        """An unpicklable value (SSLContext) is skipped instead of raising.

        ``dill.dumps`` raises a bare ``TypeError`` for an ``SSLContext`` (not a
        ``pickle.PicklingError``), so the original narrow ``except`` let it
        escape and crash the build.
        """
        cache = self._cache()
        value = {"result": {"built_object": ssl.create_default_context()}, "type": dict}

        # Should not raise (previously raised TypeError: cannot pickle 'SSLContext').
        await cache.set("vertex-id", value)

        # The value was skipped, so a later read is a cache miss rather than stale data.
        assert await cache.get("vertex-id") is CACHE_MISS

    async def test_upsert_unpicklable_value_does_not_raise(self):
        """upsert() (used by the build cache path) also degrades gracefully."""
        cache = self._cache()
        value = {"built_object": ssl.create_default_context()}

        await cache.upsert("vertex-id", value)

        assert await cache.get("vertex-id") is CACHE_MISS

    async def test_picklable_value_still_round_trips(self):
        """Regression: ordinary picklable values continue to cache and load."""
        cache = self._cache()
        value = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}

        await cache.set("ok-key", value)

        assert await cache.get("ok-key") == value

    async def test_unpicklable_set_evicts_stale_value(self):
        """A skipped write must drop any previously cached value for that key.

        ``upsert`` is get -> merge -> set; if a later value is unserializable we
        skip the write, but a stale entry left in Redis would be served on the
        next get() instead of triggering recomputation.
        """
        cache = self._cache()
        await cache.set("vertex-id", {"built_object": "old-serializable"})
        assert await cache.get("vertex-id") == {"built_object": "old-serializable"}

        # New value for the same key is unserializable -> write skipped...
        await cache.upsert("vertex-id", {"built_object": ssl.create_default_context()})

        # ...and the stale entry is gone, so the next access recomputes.
        assert await cache.get("vertex-id") is CACHE_MISS


def _settings_mock(config_dir: str, secret_key: str) -> MagicMock:
    """A settings service stub with a known CONFIG_DIR and SECRET_KEY."""
    settings = MagicMock()
    settings.auth_settings.CONFIG_DIR = config_dir
    settings.auth_settings.SECRET_KEY.get_secret_value.return_value = secret_key
    return settings


@pytest.mark.asyncio
class TestRedisCacheSigningKeySeparation:
    """Regression for H1-3982189 (variant of CVE-2026-8476).

    The cache HMAC signing key must derive from a dedicated secret stored
    separately from SECRET_KEY, so that disclosure of SECRET_KEY (e.g. via a
    file-read vulnerability) does not let an attacker forge integrity tags and
    reach dill.loads().
    """

    # Known value published in the H1-3982189 PoC (public, not a real credential).
    _STOLEN_SECRET_KEY = "k-lyUY0mU0cJTG1nJy6kdbLCp-jFe0e7pqBTx-OiiPY"  # noqa: S105  # pragma: allowlist secret

    async def test_signing_key_not_derived_from_secret_key(self, tmp_path):
        """The signing key must not equal sha256('langflow-redis-cache-hmac:' + SECRET_KEY)."""
        settings = _settings_mock(str(tmp_path), self._STOLEN_SECRET_KEY)
        with (
            patch("redis.asyncio.StrictRedis"),
            patch("langflow.services.deps.get_settings_service", return_value=settings),
        ):
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            signing_key = cache._get_signing_key()

        pre_fix_key = hashlib.sha256(b"langflow-redis-cache-hmac:" + self._STOLEN_SECRET_KEY.encode()).digest()
        assert signing_key != pre_fix_key
        # The dedicated secret was persisted in its own file, next to but
        # separate from the auth ``secret_key`` file.
        assert (tmp_path / "cache_secret_key").exists()

    async def test_secret_key_compromise_cannot_forge_tags(self, tmp_path):
        """Replay the H1-3982189 PoC: knowing SECRET_KEY must not suffice to forge a tag."""
        import dill

        settings = _settings_mock(str(tmp_path), self._STOLEN_SECRET_KEY)
        _MARKER_PATH_HOLDER.clear()
        with (
            patch("redis.asyncio.StrictRedis") as mock_redis_class,
            patch("langflow.services.deps.get_settings_service", return_value=settings),
        ):
            mock_client = AsyncMock()
            mock_redis_class.return_value = mock_client
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)

            # Attacker derives the signing key from the stolen SECRET_KEY using
            # the pre-fix derivation and signs a reduce-gadget payload.
            attacker_key = hashlib.sha256(b"langflow-redis-cache-hmac:" + self._STOLEN_SECRET_KEY.encode()).digest()
            payload = dill.dumps(_Gadget("gadget-ran"))
            ns_key = cache._key("rce_test")
            key_bytes = ns_key.encode("utf-8")
            mac = hmac.new(attacker_key, digestmod=hashlib.sha256)
            mac.update(len(key_bytes).to_bytes(8, "big"))
            mac.update(key_bytes)
            mac.update(payload)
            mock_client.get.return_value = mac.digest() + payload

            result = await cache.get("rce_test")

        assert result is CACHE_MISS  # forged tag rejected
        assert _MARKER_PATH_HOLDER == []  # gadget never executed

    async def test_signing_secret_shared_across_instances(self, tmp_path):
        """Workers sharing a CONFIG_DIR derive the same signing key (multi-worker deployments)."""
        settings = _settings_mock(str(tmp_path), self._STOLEN_SECRET_KEY)
        with (
            patch("redis.asyncio.StrictRedis"),
            patch("langflow.services.deps.get_settings_service", return_value=settings),
        ):
            cache_a = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            cache_b = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            assert cache_a._get_signing_key() == cache_b._get_signing_key()

    async def test_roundtrip_uses_dedicated_secret(self, tmp_path):
        """set()/get() still round-trip with the dedicated-secret signing key."""
        settings = _settings_mock(str(tmp_path), self._STOLEN_SECRET_KEY)
        with (
            patch("redis.asyncio.StrictRedis"),
            patch("langflow.services.deps.get_settings_service", return_value=settings),
        ):
            cache = RedisCache(expiration_time=3600)
            cache._client = fakeredis.FakeAsyncRedis()

            await cache.set("k", {"a": 1})
            assert await cache.get("k") == {"a": 1}

    async def test_ephemeral_secret_when_no_config_dir(self):
        """Without a CONFIG_DIR, an ephemeral per-process secret is used (no crash)."""
        settings = _settings_mock("", self._STOLEN_SECRET_KEY)
        with (
            patch("redis.asyncio.StrictRedis"),
            patch("langflow.services.deps.get_settings_service", return_value=settings),
        ):
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            signing_key = cache._get_signing_key()

        assert isinstance(signing_key, bytes)
        assert len(signing_key) == hashlib.sha256().digest_size


class TestCacheSigningKeyStability:
    """The signing key must be the same for every process that shares the cache.

    The key is not a secrecy problem here but an availability one: a worker that
    derives a different key cannot verify entries another worker signed, so the
    cache silently stops hitting. The first-use sequence was exists/generate/write,
    which is not atomic, and replicas do not share a CONFIG_DIR at all.
    """

    @staticmethod
    def _settings(config_dir, configured_key=None):
        settings = MagicMock()
        settings.auth_settings.CONFIG_DIR = str(config_dir)
        settings.auth_settings.CACHE_SIGNING_KEY = (
            SecretStr(configured_key) if configured_key is not None else SecretStr("")
        )
        return settings

    def _load(self, config_dir, configured_key=None):
        with patch(
            "langflow.services.deps.get_settings_service",
            return_value=self._settings(config_dir, configured_key),
        ):
            return _load_or_create_cache_signing_secret()

    def test_second_caller_adopts_the_persisted_key(self, tmp_path):
        first = self._load(tmp_path)
        second = self._load(tmp_path)
        assert first == second
        assert (tmp_path / "cache_secret_key").read_text(encoding="utf-8").strip() == first

    def test_check_then_act_race_returns_the_winner(self, tmp_path):
        """Deterministic replay of the race: the file appears after the existence check.

        The loser must end up with the winner's key, not the one it generated
        before discovering it had lost.
        """
        secret_path = tmp_path / "cache_secret_key"
        winner_key = "winner-key-from-the-other-worker"  # pragma: allowlist secret

        calls = {"n": 0}
        real_reader = _read_existing_cache_signing_secret

        def racing_reader(path):
            calls["n"] += 1
            if calls["n"] == 1:
                # The other worker has not created the file yet at this instant.
                return None
            return real_reader(path)

        # ... but by the time we try to create it, it exists with the winner's key.
        secret_path.write_text(winner_key, encoding="utf-8")

        with patch(
            "langflow.services.cache.service._read_existing_cache_signing_secret",
            side_effect=racing_reader,
        ):
            resolved = _claim_cache_signing_secret(secret_path)

        assert resolved == winner_key
        assert secret_path.read_text(encoding="utf-8") == winner_key

    def test_file_created_but_not_yet_written_is_retried(self, tmp_path):
        """An empty file means "the winner is mid-write", not "no key exists"."""
        secret_path = tmp_path / "cache_secret_key"
        secret_path.touch()
        winner_key = "winner-key-written-a-moment-later"  # pragma: allowlist secret

        reads = {"n": 0}

        def finishing_writer(_path):
            reads["n"] += 1
            if reads["n"] < 3:
                return None  # file present but still empty
            return winner_key

        with patch(
            "langflow.services.cache.service._read_existing_cache_signing_secret",
            side_effect=finishing_writer,
        ):
            assert _claim_cache_signing_secret(secret_path) == winner_key

    def test_concurrent_first_use_agrees_on_one_key(self, tmp_path):
        """Every worker starting at once must end with the same key.

        The patch is entered once, in the main thread: ``patch`` saves and restores
        a module attribute, so eight workers entering and exiting it concurrently
        can restore each other's MagicMock and leave the attribute mocked for
        later tests.
        """
        resolved: list[str] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(8)

        def worker():
            try:
                barrier.wait()
                resolved.append(_load_or_create_cache_signing_secret())
            except BaseException as exc:  # surfaced below, not swallowed
                errors.append(exc)

        with patch(
            "langflow.services.deps.get_settings_service",
            return_value=self._settings(tmp_path),
        ):
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        assert not errors, f"worker raised: {errors[0]!r}"
        assert len(resolved) == 8
        assert len(set(resolved)) == 1
        assert set(resolved) == {(tmp_path / "cache_secret_key").read_text(encoding="utf-8").strip()}

    def test_replicas_with_separate_config_dirs_diverge_without_a_shared_key(self, tmp_path):
        """The control: this is the case LANGFLOW_CACHE_SIGNING_KEY exists to fix."""
        replica_a = tmp_path / "replica-a"
        replica_b = tmp_path / "replica-b"
        replica_a.mkdir()
        replica_b.mkdir()
        assert self._load(replica_a) != self._load(replica_b)

    def test_replicas_with_separate_config_dirs_share_a_configured_key(self, tmp_path):
        replica_a = tmp_path / "replica-a"
        replica_b = tmp_path / "replica-b"
        replica_a.mkdir()
        replica_b.mkdir()
        shared = "deployment-wide-cache-signing-key"  # pragma: allowlist secret
        assert self._load(replica_a, shared) == self._load(replica_b, shared) == shared
        # The configured key wins outright: no file is consulted or created.
        assert not (replica_a / "cache_secret_key").exists()

    def test_entries_signed_by_one_instance_verify_in_another(self, tmp_path):
        """The end-to-end property: a tag produced on replica A verifies on replica B."""
        import dill

        replica_a = tmp_path / "replica-a"
        replica_b = tmp_path / "replica-b"
        replica_a.mkdir()
        replica_b.mkdir()
        shared = "deployment-wide-cache-signing-key"  # pragma: allowlist secret
        namespaced_key = "langflow:cache:some-key"
        payload = dill.dumps({"value": 1})

        with patch("redis.asyncio.StrictRedis"):
            with patch(
                "langflow.services.deps.get_settings_service",
                return_value=self._settings(replica_a, shared),
            ):
                cache_a = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
                tag_a = cache_a._integrity_tag(namespaced_key, payload)
            with patch(
                "langflow.services.deps.get_settings_service",
                return_value=self._settings(replica_b, shared),
            ):
                cache_b = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
                assert cache_b._get_signing_key() == cache_a._get_signing_key()
                assert hmac.compare_digest(cache_b._integrity_tag(namespaced_key, payload), tag_a)

    def test_separate_config_dirs_cannot_verify_each_other_without_a_shared_key(self, tmp_path):
        """The failure mode being fixed: valid entries read as misses on the other replica."""
        import dill

        replica_a = tmp_path / "replica-a"
        replica_b = tmp_path / "replica-b"
        replica_a.mkdir()
        replica_b.mkdir()
        namespaced_key = "langflow:cache:some-key"
        payload = dill.dumps({"value": 1})

        with patch("redis.asyncio.StrictRedis"):
            with patch(
                "langflow.services.deps.get_settings_service",
                return_value=self._settings(replica_a),
            ):
                tag_a = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)._integrity_tag(
                    namespaced_key, payload
                )
            with patch(
                "langflow.services.deps.get_settings_service",
                return_value=self._settings(replica_b),
            ):
                tag_b = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)._integrity_tag(
                    namespaced_key, payload
                )

        assert not hmac.compare_digest(tag_a, tag_b)

    def test_tamper_rejection_survives_the_shared_key(self, tmp_path):
        """Sharing the key must not weaken verification: a flipped byte still fails."""
        import dill

        shared = "deployment-wide-cache-signing-key"  # pragma: allowlist secret
        namespaced_key = "langflow:cache:some-key"
        payload = bytearray(dill.dumps({"value": 1}))

        with (
            patch("redis.asyncio.StrictRedis"),
            patch(
                "langflow.services.deps.get_settings_service",
                return_value=self._settings(tmp_path, shared),
            ),
        ):
            cache = RedisCache(host="localhost", port=6379, db=0, expiration_time=3600)
            tag = cache._integrity_tag(namespaced_key, bytes(payload))
            payload[-1] ^= 0xFF
            assert not hmac.compare_digest(tag, cache._integrity_tag(namespaced_key, bytes(payload)))
            # A tag is still bound to its key, too.
            assert not hmac.compare_digest(tag, cache._integrity_tag("langflow:cache:other", bytes(payload)))

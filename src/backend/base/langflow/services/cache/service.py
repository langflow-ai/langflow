import asyncio
import atexit
import contextlib
import hashlib
import hmac
import os
import secrets
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Generic, Union

import dill
from lfx.log.logger import logger
from lfx.services.cache.utils import CACHE_MISS
from lfx.services.settings.utils import read_secret_from_file, set_secure_permissions
from typing_extensions import override

from langflow.services.cache.base import (
    AsyncBaseCacheService,
    AsyncLockType,
    CacheService,
    ExternalAsyncBaseCacheService,
    LockType,
)

_redis_cache_experimental_warning_lock = threading.Lock()
_redis_cache_experimental_warning_emitted = False

# File (inside the Langflow config dir) holding the dedicated secret used to
# sign external cache (Redis, Aerospike) payloads. Kept separate from the auth ``secret_key`` file so
# that disclosure of SECRET_KEY alone does not let an attacker forge cache
# integrity tags (H1-3982189).
_CACHE_SIGNING_SECRET_FILENAME = "cache_secret_key"  # noqa: S105 - file name, not a secret  # pragma: allowlist secret


# How long a process that lost the first-use race waits for the winner to finish
# writing the secret file. The winner creates the file and writes immediately, so
# this only has to cover a single small write.
_CACHE_SECRET_CLAIM_ATTEMPTS = 20
_CACHE_SECRET_CLAIM_DELAY_S = 0.05


def _read_existing_cache_signing_secret(secret_path: Path) -> str | None:
    """Return the persisted secret, or None if it is absent or not yet written."""
    try:
        if not secret_path.exists():
            return None
        return read_secret_from_file(secret_path).strip() or None
    except OSError:
        return None


def _claim_cache_signing_secret(secret_path: Path) -> str | None:
    """Create the secret file exclusively, or read whichever process won.

    ``exists()`` then ``write`` is not atomic: two workers starting together both
    see the file missing, both generate a secret, and both keep their own in
    memory even though only one write survives. Entries signed by one worker
    then fail verification in the other, which shows up as a cache that never
    hits rather than as an error.

    ``O_CREAT | O_EXCL`` makes exactly one process the writer. A loser may still
    observe the file after creation but before the write lands, so it retries
    for a bounded time rather than treating an empty file as "no secret".
    """
    for _ in range(_CACHE_SECRET_CLAIM_ATTEMPTS):
        if (existing := _read_existing_cache_signing_secret(secret_path)) is not None:
            return existing
        candidate = secrets.token_urlsafe(32)
        try:
            descriptor = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # Another process created it between the read above and here; it is
            # writing now, so loop and read what it wrote.
            time.sleep(_CACHE_SECRET_CLAIM_DELAY_S)
            continue
        except OSError:
            logger.exception("Cache: could not persist the cache signing secret, using an ephemeral one")
            return None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(candidate)
        except OSError:
            logger.exception("Cache: could not persist the cache signing secret, using an ephemeral one")
            Path(secret_path).unlink(missing_ok=True)
            return None
        try:
            set_secure_permissions(secret_path)
        except Exception:  # noqa: BLE001 - permissions are best-effort, the secret is already written
            logger.exception("Cache: failed to set secure permissions on the cache signing secret")
        return candidate
    # Every attempt saw a file that never became readable.
    return _read_existing_cache_signing_secret(secret_path)


def _load_or_create_cache_signing_secret() -> str:
    """Return the dedicated secret used to sign external cache payloads.

    Resolution order:

    1. ``LANGFLOW_CACHE_SIGNING_KEY``. This is the only source that works across
       *replicas*: separate pods share the cache but not a config directory, so a
       file-derived key differs per replica and entries written by one are
       unverifiable by the others. Operators running more than one instance
       against one cache must set it.
    2. A key persisted in ``CONFIG_DIR``, claimed atomically on first use so all
       workers sharing that directory agree on it.
    3. An ephemeral per-process key, when neither is available. Existing entries
       then become misses rather than errors.

    It is kept separate from the auth ``secret_key`` so that disclosure of
    SECRET_KEY alone does not let an attacker forge cache integrity tags.
    """
    from langflow.services.deps import get_settings_service

    auth_settings = get_settings_service().auth_settings
    configured = getattr(auth_settings, "CACHE_SIGNING_KEY", None)
    if configured is not None:
        configured_value = configured.get_secret_value() if hasattr(configured, "get_secret_value") else configured
        # isinstance, not truthiness: a settings stub can hand back a non-string
        # sentinel, and treating that as the key would silently sign with it.
        if isinstance(configured_value, str) and configured_value.strip():
            return configured_value.strip()

    config_dir = auth_settings.CONFIG_DIR
    if not config_dir:
        logger.warning(
            "Cache: no CONFIG_DIR and no LANGFLOW_CACHE_SIGNING_KEY; using a per-process cache signing "
            "key. Cached entries will not be shared between processes."
        )
        return secrets.token_urlsafe(32)

    secret_path = Path(config_dir) / _CACHE_SIGNING_SECRET_FILENAME
    if (secret := _claim_cache_signing_secret(secret_path)) is not None:
        return secret
    return secrets.token_urlsafe(32)


def _warn_redis_experimental_once() -> None:
    """Emit the RedisCache experimental warning only once per server run."""
    global _redis_cache_experimental_warning_emitted  # noqa: PLW0603

    with _redis_cache_experimental_warning_lock:
        if _redis_cache_experimental_warning_emitted:
            return
        _redis_cache_experimental_warning_emitted = True

    # Cross-process deduplication: all workers forked from the same master
    # share the same getppid() value, so they all target the same sentinel.
    sentinel = Path(tempfile.gettempdir()) / f"langflow_redis_cache_warned_{os.getppid()}.sentinel"
    try:
        fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        return  # Another worker already logged the warning

    # Best-effort cleanup so we don't leave a stale file in /tmp after every restart.
    atexit.register(sentinel.unlink, missing_ok=True)

    logger.warning(
        "RedisCache is an experimental feature and may not work as expected."
        " Please report any issues to our GitHub repository."
    )


class ThreadingInMemoryCache(CacheService, Generic[LockType]):
    """A simple in-memory cache using an OrderedDict.

    This cache supports setting a maximum size and expiration time for cached items.
    When the cache is full, it uses a Least Recently Used (LRU) eviction policy.
    Thread-safe using a threading Lock.

    Attributes:
        max_size (int, optional): Maximum number of items to store in the cache.
        expiration_time (int, optional): Time in seconds after which a cached item expires. Default is 1 hour.

    Example:
        cache = InMemoryCache(max_size=3, expiration_time=5)

        # setting cache values
        cache.set("a", 1)
        cache.set("b", 2)
        cache["c"] = 3

        # getting cache values
        a = cache.get("a")
        b = cache["b"]
    """

    def __init__(self, max_size=None, expiration_time=60 * 60) -> None:
        """Initialize a new InMemoryCache instance.

        Args:
            max_size (int, optional): Maximum number of items to store in the cache.
            expiration_time (int, optional): Time in seconds after which a cached item expires. Default is 1 hour.
        """
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
        self.max_size = max_size
        self.expiration_time = expiration_time

    def get(self, key, lock: Union[threading.Lock, None] = None):  # noqa: UP007
        """Retrieve an item from the cache.

        Args:
            key: The key of the item to retrieve.
            lock: A lock to use for the operation.

        Returns:
            The value associated with the key, or CACHE_MISS if the key is not found or the item has expired.
        """
        with lock or self._lock:
            return self._get_without_lock(key)

    def _get_without_lock(self, key):
        """Retrieve an item from the cache without acquiring the lock."""
        if item := self._cache.get(key):
            if self.expiration_time is None or time.time() - item["time"] < self.expiration_time:
                # Move the key to the end to make it recently used
                self._cache.move_to_end(key)
                # Return the value exactly as stored. Bytes must never be fed to
                # pickle.loads here: the cache has no integrity protection, so
                # deserializing them would be unauthenticated CWE-502 (H1-3982189).
                return item["value"]
            self.delete(key)
        return CACHE_MISS

    def set(self, key, value, lock: Union[threading.Lock, None] = None) -> None:  # noqa: UP007
        """Add an item to the cache.

        If the cache is full, the least recently used item is evicted.

        Args:
            key: The key of the item.
            value: The value to cache.
            lock: A lock to use for the operation.
        """
        with lock or self._lock:
            if key in self._cache:
                # Remove existing key before re-inserting to update order
                self.delete(key)
            elif self.max_size and len(self._cache) >= self.max_size:
                # Remove least recently used item
                self._cache.popitem(last=False)

            self._cache[key] = {"value": value, "time": time.time()}

    def upsert(self, key, value, lock: Union[threading.Lock, None] = None) -> None:  # noqa: UP007
        """Inserts or updates a value in the cache.

        If the existing value and the new value are both dictionaries, they are merged.

        Args:
            key: The key of the item.
            value: The value to insert or update.
            lock: A lock to use for the operation.
        """
        with lock or self._lock:
            existing_value = self._get_without_lock(key)
            if existing_value is not CACHE_MISS and isinstance(existing_value, dict) and isinstance(value, dict):
                existing_value.update(value)
                value = existing_value

            self.set(key, value)

    def get_or_set(self, key, value, lock: Union[threading.Lock, None] = None):  # noqa: UP007
        """Retrieve an item from the cache.

        If the item does not exist, set it with the provided value.

        Args:
            key: The key of the item.
            value: The value to cache if the item doesn't exist.
            lock: A lock to use for the operation.

        Returns:
            The cached value associated with the key.
        """
        with lock or self._lock:
            if key in self._cache:
                return self.get(key)
            self.set(key, value)
            return value

    def delete(self, key, lock: Union[threading.Lock, None] = None) -> None:  # noqa: UP007
        with lock or self._lock:
            self._cache.pop(key, None)

    def clear(self, lock: Union[threading.Lock, None] = None) -> None:  # noqa: UP007
        """Clear all items from the cache."""
        with lock or self._lock:
            self._cache.clear()

    def contains(self, key) -> bool:
        """Check if the key is in the cache."""
        return key in self._cache

    def __contains__(self, key) -> bool:
        """Check if the key is in the cache."""
        return self.contains(key)

    def __getitem__(self, key):
        """Retrieve an item from the cache using the square bracket notation."""
        return self.get(key)

    def __setitem__(self, key, value) -> None:
        """Add an item to the cache using the square bracket notation."""
        self.set(key, value)

    def __delitem__(self, key) -> None:
        """Remove an item from the cache using the square bracket notation."""
        self.delete(key)

    def __len__(self) -> int:
        """Return the number of items in the cache."""
        return len(self._cache)

    def __repr__(self) -> str:
        """Return a string representation of the InMemoryCache instance."""
        return f"InMemoryCache(max_size={self.max_size}, expiration_time={self.expiration_time})"


class _SignedPayloadMixin:
    """HMAC integrity tags for payloads stored in an external cache.

    An external datastore is an untrusted boundary (a co-tenant on a shared
    cluster, an exposed port, or anyone able to write under Langflow's keys could
    plant a payload), and ``dill.loads()`` executes embedded reduce gadgets. So
    every stored payload carries a tag computed with a dedicated server secret
    and bound to the key it was written under, and only bytes with a valid tag
    are ever deserialized (CWE-502).

    Each backend sets ``_SIGNING_KEY_LABEL`` so the same secret derives a
    different HMAC key per backend.
    """

    # Size of the HMAC-SHA256 tag prepended to every stored payload.
    _HMAC_DIGEST_SIZE = hashlib.sha256().digest_size
    _SIGNING_KEY_LABEL: bytes
    _signing_key: bytes | None = None

    def _get_signing_key(self) -> bytes:
        """Derive the HMAC key for cache payload integrity from a dedicated secret.

        The secret is generated and stored separately from the auth
        ``SECRET_KEY`` (see ``_load_or_create_cache_signing_secret``), so
        disclosure of ``SECRET_KEY`` alone does not allow forging cache
        integrity tags (H1-3982189). Cached after first use (the secret does
        not change at runtime).
        """
        if self._signing_key is None:
            secret = _load_or_create_cache_signing_secret()
            self._signing_key = hashlib.sha256(self._SIGNING_KEY_LABEL + secret.encode()).digest()
        return self._signing_key

    def _integrity_tag(self, namespaced_key: str, payload: bytes) -> bytes:
        """Compute the HMAC-SHA256 tag binding ``payload`` to ``namespaced_key``.

        The storage key is mixed in as associated authenticated data so a tag is
        only valid for the exact key the payload was written under. Without this
        binding, a payload signed for one key verifies under any other key,
        letting anyone with write access to the cache relocate/replay a
        validly-signed entry across keys (cross-key substitution → type
        confusion / stale-value injection) without ever knowing the secret. The
        key is length-prefixed so the (key, payload) framing is unambiguous and
        bytes cannot be shifted across the boundary while keeping a valid tag.
        """
        mac = hmac.new(self._get_signing_key(), digestmod=hashlib.sha256)
        key_bytes = namespaced_key.encode("utf-8")
        mac.update(len(key_bytes).to_bytes(8, "big"))
        mac.update(key_bytes)
        mac.update(payload)
        return mac.digest()


class RedisCache(_SignedPayloadMixin, ExternalAsyncBaseCacheService, Generic[LockType]):
    """A Redis-based cache implementation.

    This cache supports setting an expiration time for cached items.

    Attributes:
        expiration_time (int, optional): Time in seconds after which a cached item expires. Default is 1 hour.

    Example:
        cache = RedisCache(expiration_time=5)

        # setting cache values
        cache.set("a", 1)
        cache.set("b", 2)
        cache["c"] = 3

        # getting cache values
        a = cache.get("a")
        b = cache["b"]
    """

    KEY_PREFIX = "langflow:cache:"

    _SIGNING_KEY_LABEL = b"langflow-redis-cache-hmac:"

    def __init__(self, host="localhost", port=6379, db=0, url=None, expiration_time=60 * 60) -> None:
        """Initialize a new RedisCache instance.

        Args:
            host (str, optional): Redis host.
            port (int, optional): Redis port.
            db (int, optional): Redis DB.
            url (str, optional): Redis URL.
            expiration_time (int, optional): Time in seconds after which a
                cached item expires. Default is 1 hour.
        """
        # Redis is a main dependency, no need to import check
        from redis.asyncio import StrictRedis

        _warn_redis_experimental_once()
        if url:
            self._client = StrictRedis.from_url(url)
        else:
            self._client = StrictRedis(host=host, port=port, db=db)
        self.expiration_time = expiration_time
        self._signing_key: bytes | None = None

    def _key(self, key) -> str:
        """Return the namespaced Redis key."""
        return f"{self.KEY_PREFIX}{key}"

    async def is_connected(self) -> bool:
        """Check if the Redis client is connected."""
        import redis

        try:
            await self._client.ping()
        except redis.exceptions.ConnectionError:
            msg = "RedisCache could not connect to the Redis server"
            await logger.aexception(msg)
            return False
        return True

    @override
    async def get(self, key, lock=None):
        if key is None:
            return CACHE_MISS
        namespaced_key = self._key(key)
        value = await self._client.get(namespaced_key)
        if not value:
            return CACHE_MISS
        # Integrity check before deserializing. The Redis datastore is an
        # untrusted boundary (a co-tenant on a shared Redis, an exposed/un-ACL'd
        # port, or anyone able to write under the langflow:cache: namespace could
        # plant a payload). dill.loads() executes embedded reduce gadgets, so we
        # only deserialize bytes carrying a valid HMAC produced with the server
        # secret. Unsigned/tampered/legacy entries are treated as a miss and are
        # never passed to dill.loads (CWE-502).
        if len(value) < self._HMAC_DIGEST_SIZE:
            return CACHE_MISS
        tag, payload = value[: self._HMAC_DIGEST_SIZE], value[self._HMAC_DIGEST_SIZE :]
        expected = self._integrity_tag(namespaced_key, payload)
        if not hmac.compare_digest(tag, expected):
            await logger.awarning("RedisCache: discarding cache entry with an invalid integrity tag")
            return CACHE_MISS
        return dill.loads(payload)

    @override
    async def set(self, key, value, lock=None) -> None:
        # Serialize first, in isolation from the network write. Live objects built during
        # a flow run -- LLM clients holding an ``ssl.SSLContext``, httpx clients, thread
        # locks, dynamically-created pydantic models -- are inherently unpicklable, and
        # dill signals this with a variety of exception types (a bare ``TypeError`` for an
        # SSLContext, ``AttributeError`` for dynamic classes, ``RecursionError`` for deep
        # graphs, etc.) -- not only ``pickle.PicklingError``. Failing to serialize must not
        # crash the caller (e.g. the vertex build); skip the cache write instead, which
        # just means the value is recomputed on the next access. See issue #13764.
        try:
            pickled = dill.dumps(value, recurse=True)
        except Exception as exc:  # noqa: BLE001
            await logger.awarning(
                f"RedisCache skipping cache for key '{key}': value is not serializable ({type(exc).__name__}: {exc})."
            )
            # Drop any previously-cached value for this key. ``upsert`` does
            # get -> merge -> set, so leaving an older entry in place would let a
            # later get() serve stale data instead of recomputing. (DEL of a
            # missing key is a harmless no-op.)
            await self._client.delete(self._key(key))
            return
        if pickled:
            # Prefix an HMAC tag so get() can reject tampered/forged payloads
            # before deserialization (see get()). The tag is bound to the
            # namespaced key so it cannot be replayed under a different key.
            namespaced_key = self._key(key)
            tag = self._integrity_tag(namespaced_key, pickled)
            result = await self._client.setex(namespaced_key, self.expiration_time, tag + pickled)
            if not result:
                msg = "RedisCache could not set the value."
                raise ValueError(msg)

    @override
    async def upsert(self, key, value, lock=None) -> None:
        """Inserts or updates a value in the cache.

        If the existing value and the new value are both dictionaries, they are merged.

        Args:
            key: The key of the item.
            value: The value to insert or update.
            lock: A lock to use for the operation.
        """
        if key is None:
            return
        existing_value = await self.get(key)
        if existing_value is not None and isinstance(existing_value, dict) and isinstance(value, dict):
            existing_value.update(value)
            value = existing_value

        await self.set(key, value)

    @override
    async def delete(self, key, lock=None) -> None:
        await self._client.delete(self._key(key))

    @override
    async def clear(self, lock=None) -> None:
        """Clear all items from the cache using a key-prefix scan to avoid nuking unrelated data."""
        cursor = 0
        pattern = f"{self.KEY_PREFIX}*"
        while True:
            cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
            if keys:
                await self._client.delete(*keys)
            if cursor == 0:
                break

    async def contains(self, key) -> bool:
        """Check if the key is in the cache."""
        if key is None:
            return False
        return bool(await self._client.exists(self._key(key)))

    @override
    async def teardown(self) -> None:
        """Close the Redis client connection to prevent socket leaks across fork."""
        await self._client.aclose()

    def __repr__(self) -> str:
        """Return a string representation of the RedisCache instance."""
        return f"RedisCache(expiration_time={self.expiration_time})"


# Aerospike's per-record TTL for "keep until overwritten or deleted".
AEROSPIKE_NEVER_EXPIRE = -1


def parse_aerospike_hosts(hosts: str, default_port: int = 3000) -> list[tuple[str, int]]:
    """Parse ``"host1:3000,host2"`` into the ``[(host, port), ...]`` list the client expects."""
    parsed: list[tuple[str, int]] = []
    for raw in hosts.split(","):
        entry = raw.strip()
        if not entry:
            continue
        host, sep, port = entry.rpartition(":")
        if sep and port.isdigit():
            parsed.append((host, int(port)))
        else:
            parsed.append((entry, default_port))
    if not parsed:
        msg = "AerospikeCache requires at least one host"
        raise ValueError(msg)
    return parsed


class AerospikeCache(_SignedPayloadMixin, ExternalAsyncBaseCacheService, Generic[LockType]):
    """An Aerospike-based cache implementation.

    Each cache key is one record in ``namespace``/``set_name``. The value is
    dill-pickled, prefixed with an HMAC tag (see ``_SignedPayloadMixin``) and
    stored in a single bin; it expires through the record TTL. ``clear()``
    truncates only ``set_name``, so the namespace can be shared with other data.

    The Aerospike Python client is synchronous, so every call runs in a worker
    thread to keep the event loop free. It is an optional dependency
    (``langflow-base[aerospike]``), imported only when this backend is selected.

    ``set`` takes an optional per-key ``expiration_time`` (``-1`` never
    expires); ``supports_per_key_ttl`` advertises it so callers can use it
    without knowing the backend.

    The namespace must allow TTLs (``nsup-period`` > 0 on the server), otherwise
    writes with an expiration are rejected.
    """

    _SIGNING_KEY_LABEL = b"langflow-aerospike-cache-hmac:"
    _VALUE_BIN = "v"
    supports_per_key_ttl = True

    def __init__(
        self,
        hosts: str = "localhost:3000",
        namespace: str = "langflow",
        set_name: str = "cache",
        user: str | None = None,
        password: str | None = None,
        expiration_time: int = 60 * 60,
    ) -> None:
        """Initialize a new AerospikeCache instance.

        Args:
            hosts (str, optional): Comma-separated seed nodes, ``host[:port]``.
            namespace (str, optional): Aerospike namespace holding the cache set.
            set_name (str, optional): Set holding Langflow's cache records.
            user (str, optional): User for clusters with security enabled.
            password (str, optional): Password for ``user``.
            expiration_time (int, optional): Default record TTL in seconds.
        """
        try:
            import aerospike  # noqa: F401
        except ImportError as exc:
            msg = "AerospikeCache requires the 'aerospike' package. Install langflow-base[aerospike]."
            raise ImportError(msg) from exc

        self._config: dict = {"hosts": parse_aerospike_hosts(hosts)}
        if user:
            self._config["user"] = user
            self._config["password"] = password or ""
        self.namespace = namespace
        self.set_name = set_name
        self.expiration_time = expiration_time
        self._signing_key: bytes | None = None
        # Connected lazily: connect() blocks, and the master process tears the
        # client down before forking workers (see preload.py), so each worker
        # opens its own connection.
        self._client = None
        self._client_lock = threading.Lock()

    def _get_client(self):
        with self._client_lock:
            if self._client is None or not self._client.is_connected():
                import aerospike

                self._client = aerospike.client(self._config).connect()
            return self._client

    def _key(self, key) -> tuple[str, str, str]:
        return (self.namespace, self.set_name, str(key))

    def _tag_key(self, key) -> str:
        """The string the integrity tag is bound to: namespace, set and key."""
        return f"{self.namespace}/{self.set_name}/{key}"

    async def ping(self) -> bool:
        """Connect if needed and report whether the cluster is reachable.

        Raises on a connection failure and logs nothing, so callers that render
        their own result (e.g. the CLI preflight) can probe without noise.
        """
        client = await asyncio.to_thread(self._get_client)
        return bool(client.is_connected())

    async def is_connected(self) -> bool:
        """Check that the cluster is reachable."""
        try:
            return await self.ping()
        except Exception:  # noqa: BLE001
            await logger.aexception("AerospikeCache could not connect to the Aerospike cluster")
            return False

    def _get_sync(self, key) -> bytes | None:
        from aerospike import exception as ex

        try:
            _, _, bins = self._get_client().get(self._key(key))
        except ex.RecordNotFound:
            return None
        value = bins.get(self._VALUE_BIN) if bins else None
        return bytes(value) if value else None

    @override
    async def get(self, key, lock=None):
        if key is None:
            return CACHE_MISS
        value = await asyncio.to_thread(self._get_sync, key)
        if not value or len(value) < self._HMAC_DIGEST_SIZE:
            return CACHE_MISS
        # Integrity check before deserializing; see _SignedPayloadMixin.
        # Unsigned/tampered/legacy entries are a miss and never reach dill.loads.
        tag, payload = value[: self._HMAC_DIGEST_SIZE], value[self._HMAC_DIGEST_SIZE :]
        if not hmac.compare_digest(tag, self._integrity_tag(self._tag_key(key), payload)):
            await logger.awarning("AerospikeCache: discarding cache entry with an invalid integrity tag")
            return CACHE_MISS
        return dill.loads(payload)

    def _put_sync(self, key, blob: bytes, ttl: int) -> None:
        self._get_client().put(self._key(key), {self._VALUE_BIN: bytearray(blob)}, meta={"ttl": ttl})

    @override
    async def set(self, key, value, lock=None, *, expiration_time: int | None = None) -> None:
        """Store ``value``; ``expiration_time`` overrides the default TTL for this key only.

        ``AEROSPIKE_NEVER_EXPIRE`` (-1) keeps the record until it is overwritten
        or deleted. Check ``supports_per_key_ttl`` before passing it: the other
        cache backends do not accept the argument.
        """
        ttl = self.expiration_time if expiration_time is None else expiration_time
        if ttl != AEROSPIKE_NEVER_EXPIRE:
            # 0 means "namespace default" to Aerospike, so a sub-second lifetime
            # becomes one second rather than that or "never".
            ttl = max(int(ttl), 1)
        # Same contract as RedisCache.set: an unpicklable value skips the cache
        # (and drops any older entry, so upsert cannot serve stale data) rather
        # than failing the caller. See issue #13764.
        try:
            pickled = dill.dumps(value, recurse=True)
        except Exception as exc:  # noqa: BLE001
            await logger.awarning(
                f"AerospikeCache skipping cache for key '{key}': value is not serializable "
                f"({type(exc).__name__}: {exc})."
            )
            await self.delete(key)
            return
        if pickled:
            blob = self._integrity_tag(self._tag_key(key), pickled) + pickled
            await asyncio.to_thread(self._put_sync, key, blob, ttl)

    @override
    async def upsert(self, key, value, lock=None) -> None:
        """Inserts or updates a value in the cache.

        If the existing value and the new value are both dictionaries, they are merged.
        """
        if key is None:
            return
        existing_value = await self.get(key)
        if existing_value is not None and isinstance(existing_value, dict) and isinstance(value, dict):
            existing_value.update(value)
            value = existing_value

        await self.set(key, value)

    def _delete_sync(self, key) -> None:
        from aerospike import exception as ex

        with contextlib.suppress(ex.RecordNotFound):
            self._get_client().remove(self._key(key))

    @override
    async def delete(self, key, lock=None) -> None:
        await asyncio.to_thread(self._delete_sync, key)

    @override
    async def clear(self, lock=None) -> None:
        """Truncate only the cache set, leaving the rest of the namespace untouched."""
        await asyncio.to_thread(lambda: self._get_client().truncate(self.namespace, self.set_name, 0))

    def _contains_sync(self, key) -> bool:
        from aerospike import exception as ex

        try:
            _, meta = self._get_client().exists(self._key(key))
        except ex.RecordNotFound:
            return False
        return meta is not None

    async def contains(self, key) -> bool:
        """Check if the key is in the cache."""
        if key is None:
            return False
        return await asyncio.to_thread(self._contains_sync, key)

    def _close_sync(self) -> None:
        with self._client_lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    @override
    async def teardown(self) -> None:
        """Close the client so its sockets are not shared across fork."""
        await asyncio.to_thread(self._close_sync)

    def __repr__(self) -> str:
        """Return a string representation of the AerospikeCache instance."""
        return (
            f"AerospikeCache(namespace={self.namespace}, set={self.set_name}, expiration_time={self.expiration_time})"
        )


class AsyncInMemoryCache(AsyncBaseCacheService, Generic[AsyncLockType]):
    def __init__(self, max_size=None, expiration_time=3600) -> None:
        self.cache: OrderedDict = OrderedDict()

        self.lock = asyncio.Lock()
        self.max_size = max_size
        self.expiration_time = expiration_time

    async def get(self, key, lock: asyncio.Lock | None = None):
        async with lock or self.lock:
            return await self._get(key)

    async def _get(self, key):
        item = self.cache.get(key, None)
        if item:
            if time.time() - item["time"] < self.expiration_time:
                self.cache.move_to_end(key)
                # Return the value exactly as stored. Bytes must never be fed to
                # pickle.loads here: the cache has no integrity protection, so
                # deserializing them would be unauthenticated CWE-502 (H1-3982189).
                return item["value"]
            await logger.ainfo(f"Cache item for key '{key}' has expired and will be deleted.")
            await self._delete(key)  # Log before deleting the expired item
        return CACHE_MISS

    async def set(self, key, value, lock: asyncio.Lock | None = None) -> None:
        async with lock or self.lock:
            await self._set(
                key,
                value,
            )

    async def _set(self, key, value) -> None:
        if self.max_size and len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = {"value": value, "time": time.time()}
        self.cache.move_to_end(key)

    async def delete(self, key, lock: asyncio.Lock | None = None) -> None:
        async with lock or self.lock:
            await self._delete(key)

    async def _delete(self, key) -> None:
        if key in self.cache:
            del self.cache[key]

    async def clear(self, lock: asyncio.Lock | None = None) -> None:
        async with lock or self.lock:
            await self._clear()

    async def _clear(self) -> None:
        self.cache.clear()

    async def upsert(self, key, value, lock: asyncio.Lock | None = None) -> None:
        await self._upsert(key, value, lock)

    async def _upsert(self, key, value, lock: asyncio.Lock | None = None) -> None:
        existing_value = await self.get(key, lock)
        if existing_value is not None and isinstance(existing_value, dict) and isinstance(value, dict):
            existing_value.update(value)
            value = existing_value
        await self.set(key, value, lock)

    async def contains(self, key) -> bool:
        return key in self.cache

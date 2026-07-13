"""Telemetry writer service implementation.

Decouples ``transaction`` and ``vertex_build`` writes from the request-handling
database pool. Producers call :py:meth:`TelemetryWriterService.enqueue_transaction`
or :py:meth:`TelemetryWriterService.enqueue_vertex_build`, which append the row
to an in-memory :class:`collections.deque`. A single background writer task
drains the buffer into the database in batched ``INSERT`` statements using a
dedicated :class:`AsyncEngine` with a tiny pool (1 connection for SQLite, 2 for
Postgres) so telemetry traffic cannot starve request traffic. A second
background task amortizes retention pruning (max-N-per-flow, max-per-vertex,
global cap) so it no longer runs inside every insert.

Durability across process restart is provided by a small SQLite outbox per PID
(``outbox.sqlite`` in WAL mode, JSON payloads in a TEXT column): rows still in
memory at shutdown spill to disk, and rows from any orphan PID directory (left
by a crashed worker) are adopted into the in-memory buffer on startup.

The trade-off: hard process kills (SIGKILL, OOM) lose whatever is in memory at
the moment of death. Telemetry visibility is eventually-consistent rather than
transactional, which matches the operational character of these tables (debug
logs and execution history; queried interactively, not on the hot path).
"""

from __future__ import annotations

import asyncio
import collections
import json
import os
import socket
import sqlite3
import tempfile
import time
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.log.logger import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import col

from langflow.services.base import Service
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable

if TYPE_CHECKING:
    from collections.abc import Iterator

    from langflow.services.settings.service import SettingsService


_DEFAULT_OUTBOX_ROOT = Path(tempfile.gettempdir()) / "langflow_telemetry_outbox"
_OUTBOX_DB_NAME = "outbox.sqlite"
_OWNER_FILE_NAME = "owner.json"
# Marker keys used to round-trip ``datetime`` and ``UUID`` through JSON
# without losing type fidelity — SQLAlchemy's DateTime/Uuid columns reject
# plain strings. Other types (Path, Decimal, ...) fall back to ``str`` since
# they only appear inside JSON payload columns where strings are fine.
_DATETIME_TAG = "__lftw_dt__"
_UUID_TAG = "__lftw_uuid__"
# After this many consecutive batch failures, escalate from per-batch logging
# to a loud error so operators see sustained data-loss risk.
_FAILURE_ESCALATION_THRESHOLD = 6


def _host_boot_identity() -> tuple[str, str]:
    """Return ``(hostname, boot_marker)`` for the current host.

    The boot marker prevents adopting an orphan PID directory across host
    reboots or container restarts, which would otherwise let a recycled PID
    pull in a stranger's spill data. Linux exposes a kernel-provided boot
    id; on platforms without one we fall back to ``time() - monotonic()``
    rounded to seconds, which is identical across processes within a boot.
    """
    host = socket.gethostname()
    try:
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        try:
            boot = str(int(time.time() - time.monotonic()))
        except Exception:  # noqa: BLE001
            boot = "unknown"
    return host, boot


def _write_owner_file(own_dir: Path) -> None:
    host, boot = _host_boot_identity()
    payload = {"host": host, "boot": boot, "pid": os.getpid(), "started_at": time.time()}
    own_dir.mkdir(parents=True, exist_ok=True)
    (own_dir / _OWNER_FILE_NAME).write_text(json.dumps(payload))


def _read_owner_file(pid_dir: Path) -> dict[str, Any] | None:
    try:
        return json.loads((pid_dir / _OWNER_FILE_NAME).read_text())
    except (OSError, ValueError):
        return None


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return {_DATETIME_TAG: value.isoformat()}
    if isinstance(value, UUID):
        return {_UUID_TAG: str(value)}
    return str(value)


def _json_object_hook(obj: dict[str, Any]) -> Any:
    if len(obj) == 1:
        if _DATETIME_TAG in obj:
            try:
                return datetime.fromisoformat(obj[_DATETIME_TAG])
            except (TypeError, ValueError):
                return obj
        if _UUID_TAG in obj:
            try:
                return UUID(obj[_UUID_TAG])
            except (TypeError, ValueError):
                return obj
    return obj


class _Outbox:
    """Append-only SQLite outbox for one ``kind`` (transactions/vertex_builds).

    Encapsulates schema, connection lifecycle, and the JSON encode/decode so the
    spill, restore, and orphan-adoption flows in :class:`TelemetryWriterService`
    can share a single durable storage shape with no pickle path.
    """

    def __init__(self, spill_dir: Path) -> None:
        self._spill_dir = spill_dir
        self._db_path = spill_dir / _OUTBOX_DB_NAME

    def exists(self) -> bool:
        return self._db_path.exists()

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        """Open the outbox DB, ensure schema, commit on success, always close."""
        self._spill_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            # FULL (rather than NORMAL) so the spill at shutdown and the
            # delete on drain hit the platter before the connection closes —
            # NORMAL only fsyncs on WAL checkpoint, which may never run if
            # the process exits immediately after we commit.
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)"
            )
            yield conn
            conn.commit()
        finally:
            conn.close()

    def append_all(self, buffer: collections.deque[dict[str, Any]], *, max_rows: int | None = None) -> tuple[int, int]:
        """Drain ``buffer`` into the on-disk outbox in a single transaction.

        Encodes every row up front so that a mid-flight SQLite failure cannot
        leave the deque half-drained: the buffer is only cleared after the
        transaction has committed. When ``max_rows`` is set and the buffer
        exceeds it, the *oldest* rows are dropped before encoding — matching
        the producer-side overflow policy and keeping shutdown bounded.

        Returns ``(spilled, dropped)``.
        """
        if not buffer:
            return 0, 0
        dropped = 0
        if max_rows is not None and len(buffer) > max_rows:
            dropped = len(buffer) - max_rows
            for _ in range(dropped):
                buffer.popleft()
        encoded = [(json.dumps(row, default=_json_default),) for row in buffer]
        with self._session() as conn:
            conn.executemany("INSERT INTO outbox(payload) VALUES (?)", encoded)
        buffer.clear()
        return len(encoded), dropped

    def drain(self) -> list[dict[str, Any]]:
        """Return all well-formed rows and delete every row from the outbox.

        Rows whose JSON cannot be decoded are logged and discarded inside this
        method so callers only ever see usable payloads.
        """
        if not self.exists():
            return []
        payloads: list[dict[str, Any]] = []
        with self._session() as conn:
            for row_id, raw in conn.execute("SELECT id, payload FROM outbox ORDER BY id").fetchall():
                try:
                    payloads.append(json.loads(raw, object_hook=_json_object_hook))
                except (TypeError, ValueError):
                    logger.warning(f"telemetry_writer: discarding malformed outbox row id={row_id}")
            conn.execute("DELETE FROM outbox")
        return payloads


def _pid_alive(pid: int) -> bool:
    """Return True if ``pid`` corresponds to a live process."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class TelemetryWriterService(Service):
    """Batched, off-pool writer for transaction + vertex_build rows."""

    name = "telemetry_writer_service"

    def __init__(self, settings_service: SettingsService) -> None:
        self.settings_service = settings_service
        self._started: bool = False
        self._shutdown_event: asyncio.Event | None = None
        self._writer_task: asyncio.Task | None = None
        self._sweeper_task: asyncio.Task | None = None
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker | None = None
        # In-memory hot path. deque.append / popleft are O(1) and don't touch disk.
        self._tx_buffer: collections.deque[dict[str, Any]] = collections.deque()
        self._vb_buffer: collections.deque[dict[str, Any]] = collections.deque()
        # Parallel byte-size deques. Populated only when size_strategy != "count" so
        # the legacy hot path pays nothing. Sized in lockstep with the payload deques.
        self._tx_sizes: collections.deque[int] = collections.deque()
        self._vb_sizes: collections.deque[int] = collections.deque()
        self._tx_bytes: int = 0
        self._vb_bytes: int = 0
        # PID directory used for shutdown spill + startup recovery.
        self._own_outbox_dir: Path | None = None
        self._dirty_tx_flows: set[str] = set()
        self._dirty_vb_flows: set[str] = set()
        # Metrics.
        self.dropped_transactions: int = 0
        self.dropped_vertex_builds: int = 0
        self.dropped_transactions_bytes: int = 0
        self.dropped_vertex_builds_bytes: int = 0
        self.failed_batches: int = 0
        self.flushed_rows: int = 0
        self.enqueued_transactions: int = 0
        self.enqueued_vertex_builds: int = 0

    # ------------------------------------------------------------------ public

    def is_enabled(self) -> bool:
        return getattr(self.settings_service.settings, "telemetry_writer_enabled", False)

    def is_running(self) -> bool:
        return self._started

    def enqueue_transaction(self, payload: dict[str, Any]) -> bool:
        """Append a transaction row to the in-memory buffer.

        Returns ``True`` if the row was accepted (caller should not write
        directly). Returns ``False`` if the writer isn't running — caller may
        fall back to the legacy direct-write path.
        """
        if not self._started:
            return False
        self._enqueue(self._tx_buffer, payload, kind="transactions")
        self.enqueued_transactions += 1
        return True

    def enqueue_vertex_build(self, payload: dict[str, Any]) -> bool:
        """Append a vertex_build row. See :py:meth:`enqueue_transaction`."""
        if not self._started:
            return False
        self._enqueue(self._vb_buffer, payload, kind="vertex_builds")
        self.enqueued_vertex_builds += 1
        return True

    # ----------------------------------------------------------------- start/stop

    async def start(self) -> None:
        """Recover pending rows from disk, create the dedicated engine, spawn tasks."""
        if self._started:
            return
        if not self.is_enabled():
            logger.debug("telemetry_writer: disabled by settings; skipping start")
            return

        outbox_root = self._outbox_root()
        outbox_root.mkdir(parents=True, exist_ok=True)
        own_dir = outbox_root / str(os.getpid())
        own_dir.mkdir(parents=True, exist_ok=True)
        # Outbox payloads contain sanitized but still-sensitive run history.
        # Restrict access to the owner so a multi-tenant host can't expose
        # them cross-user. chmod is a no-op on Windows but harmless.
        with suppress(OSError):
            outbox_root.chmod(0o700)
            own_dir.chmod(0o700)
        self._own_outbox_dir = own_dir
        # Stamp host + boot identity so a future process on a different host
        # (or after reboot) will not adopt this PID's spill data if the PID
        # happens to be recycled.
        try:
            _write_owner_file(own_dir)
        except OSError as e:
            logger.error(
                f"telemetry_writer: failed to write owner file to {own_dir}; "
                f"disk-spilled rows from this process will not be recoverable on restart: {e}"
            )

        # Drain any rows that were spilled by a previous run of *this* PID and
        # adopt the contents of any orphan (dead-PID) directories.
        self._restore_from_disk(own_dir, kind="transactions", buffer=self._tx_buffer)
        self._restore_from_disk(own_dir, kind="vertex_builds", buffer=self._vb_buffer)
        self._adopt_orphan_outboxes(outbox_root, own_pid=os.getpid())
        self._prune_stale_foreign_outboxes(outbox_root)

        self._engine = self._create_dedicated_engine()
        # Use SQLAlchemy's AsyncSession (not SQLModel's). This service issues only
        # Core-style bulk statements via ``session.execute()`` (Table.insert(),
        # delete(), select().scalars()); it never needs SQLModel's ``exec()``.
        # SQLModel's AsyncSession marks ``execute()`` as deprecated, so using it
        # here floods runtime logs with a multi-line DeprecationWarning on every
        # batch flush and retention sweep.
        self._session_maker = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
        self._shutdown_event = asyncio.Event()
        self._writer_task = asyncio.create_task(self._run_writer(), name="telemetry-writer")
        self._sweeper_task = asyncio.create_task(self._run_sweeper(), name="telemetry-sweeper")
        self._started = True
        logger.info(
            f"telemetry_writer started (outbox={own_dir}, tx_pending={len(self._tx_buffer)}, "
            f"vb_pending={len(self._vb_buffer)})"
        )

    async def teardown(self) -> None:
        """Drain in-flight rows, persist remaining buffer, dispose engine. Idempotent."""
        if not self._started:
            return
        self._started = False
        if self._shutdown_event is not None:
            self._shutdown_event.set()

        drain_timeout = float(getattr(self.settings_service.settings, "telemetry_writer_shutdown_drain_s", 5.0))
        # The sweeper cancel, disk spill, and engine dispose live in ``finally`` so
        # they still run when teardown() is itself cancelled (e.g. the outer lifespan
        # task is killed). On that cancelled path ``wait_for`` cancels and awaits the
        # writer task before re-raising, so the writer's CancelledError handler has
        # already pushed in-flight rows back into the buffer by the time we spill.
        try:
            if self._writer_task is not None:
                try:
                    await asyncio.wait_for(self._writer_task, timeout=drain_timeout)
                except asyncio.TimeoutError:
                    # Drain budget exceeded. Whatever's still in the in-memory
                    # buffer survives via the disk spill below; rows that were
                    # popped into the in-flight batch are pushed back by the
                    # writer's CancelledError handler before it exits.
                    pending = len(self._tx_buffer) + len(self._vb_buffer)
                    logger.warning(
                        f"telemetry_writer: shutdown drain exceeded {drain_timeout}s with "
                        f"{pending} rows still pending — spilling to disk. Consider raising "
                        f"telemetry_writer_shutdown_drain_s."
                    )
                    self._writer_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await self._writer_task
        finally:
            if self._sweeper_task is not None:
                self._sweeper_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._sweeper_task

            # Spill anything still in memory to disk so a future process picks it up.
            if self._own_outbox_dir is not None:
                self._spill_to_disk(self._own_outbox_dir, kind="transactions", buffer=self._tx_buffer)
                self._spill_to_disk(self._own_outbox_dir, kind="vertex_builds", buffer=self._vb_buffer)

            if self._engine is not None:
                await self._engine.dispose()
                self._engine = None
            logger.info("telemetry_writer stopped")

    # ------------------------------------------------------------------ internals

    def _outbox_root(self) -> Path:
        configured = getattr(self.settings_service.settings, "telemetry_writer_outbox_dir", None)
        return Path(configured) if configured else _DEFAULT_OUTBOX_ROOT

    def _create_dedicated_engine(self) -> AsyncEngine:
        from langflow.services.deps import get_db_service

        db_service = get_db_service()
        url = db_service.database_url
        pool_size = 1 if url.startswith("sqlite") else 2
        connect_args = db_service._get_connect_args()  # noqa: SLF001
        return create_async_engine(
            url,
            connect_args=connect_args,
            pool_size=pool_size,
            max_overflow=0,
            pool_pre_ping=True,
        )

    def _enqueue(
        self,
        buffer: collections.deque[dict[str, Any]],
        payload: dict[str, Any],
        *,
        kind: str,
    ) -> None:
        settings = self.settings_service.settings
        strategy = getattr(settings, "telemetry_writer_size_strategy", "count")
        track_bytes = strategy in ("bytes", "either")
        sizes = self._tx_sizes if kind == "transactions" else self._vb_sizes

        size = len(json.dumps(payload, default=_json_default).encode()) if track_bytes else 0
        max_q = int(getattr(settings, "telemetry_writer_max_queue", 100_000))
        max_bytes = int(getattr(settings, "telemetry_writer_max_queue_bytes", 209_715_200))

        # Drop oldest on overflow — bounds memory, biases retention toward newest.
        # Strategy decides which threshold(s) apply. Account for the incoming row
        # so the post-append state stays under the byte cap, not just the
        # pre-append state.
        while self._should_drop_oldest(buffer, len(sizes), strategy, max_q, max_bytes, incoming_bytes=size):
            try:
                buffer.popleft()
            except IndexError:
                break
            dropped_size = sizes.popleft() if track_bytes and sizes else 0
            if kind == "transactions":
                self.dropped_transactions += 1
                self.dropped_transactions_bytes += dropped_size
                self._tx_bytes -= dropped_size
            else:
                self.dropped_vertex_builds += 1
                self.dropped_vertex_builds_bytes += dropped_size
                self._vb_bytes -= dropped_size
        buffer.append(payload)
        if track_bytes:
            sizes.append(size)
            if kind == "transactions":
                self._tx_bytes += size
            else:
                self._vb_bytes += size

    def _should_drop_oldest(
        self,
        buffer: collections.deque[dict[str, Any]],
        sizes_len: int,
        strategy: str,
        max_q: int,
        max_bytes: int,
        incoming_bytes: int = 0,
    ) -> bool:
        # Snapshot byte totals after we updated them on the previous pop.
        current_bytes = self._tx_bytes if buffer is self._tx_buffer else self._vb_bytes
        count_exceeded = len(buffer) >= max_q
        # Only enforce the byte cap when we've actually tracked sizes. Mixed-mode
        # transitions (size_strategy flipped at runtime) would otherwise drop
        # everything because sizes_len is 0. ``incoming_bytes`` lets the caller
        # ensure post-append state stays under the cap, not just pre-append.
        bytes_exceeded = sizes_len > 0 and (current_bytes + incoming_bytes) > max_bytes
        if strategy == "count":
            return count_exceeded
        if strategy == "bytes":
            return bytes_exceeded
        # 'either': whichever trips first
        return count_exceeded or bytes_exceeded

    async def _wait_or_shutdown(self, timeout: float, *, name: str) -> None:
        """Sleep up to ``timeout`` or return early if shutdown is signaled.

        Wraps ``Event.wait()`` in a named task so pyleak (and operators
        inspecting ``asyncio.all_tasks()``) can distinguish telemetry-writer
        ticks from anonymous ``wait_for`` wrappers. Swallows ``TimeoutError``
        so callers can write a plain ``await self._wait_or_shutdown(...)``.
        """
        if self._shutdown_event is None:
            return
        wait_task = asyncio.create_task(self._shutdown_event.wait(), name=name)
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(wait_task, timeout=timeout)

    def _drain_batch(self, kind: str, max_n: int, max_bytes: int | None) -> list[dict]:
        """Drain rows respecting both row count and (optional) byte budget.

        Pops from the payload buffer and the parallel size deque in lockstep,
        decrementing the running byte counter as rows leave. Stops when either
        ``max_n`` rows or ``max_bytes`` worth of payload has been pulled — but
        always emits at least one row to make progress when a single row
        exceeds the byte budget.
        """
        if kind == "transactions":
            buffer, sizes = self._tx_buffer, self._tx_sizes
        else:
            buffer, sizes = self._vb_buffer, self._vb_sizes
        batch: list[dict] = []
        batch_bytes = 0
        track_bytes = max_bytes is not None and sizes
        for _ in range(max_n):
            try:
                row = buffer.popleft()
            except IndexError:
                break
            batch.append(row)
            if track_bytes:
                size = sizes.popleft()
                if kind == "transactions":
                    self._tx_bytes -= size
                else:
                    self._vb_bytes -= size
                batch_bytes += size
                if batch_bytes >= max_bytes:
                    break
        return batch

    def _return_batch_to_buffer(self, kind: str, batch: list[dict]) -> None:
        """Push an in-flight batch back to the front of its buffer on cancel/retry.

        Re-encodes sizes so the parallel size deque stays consistent. Skips
        size accounting when the byte-tracking strategy isn't active.
        """
        if not batch:
            return
        if kind == "transactions":
            buffer, sizes = self._tx_buffer, self._tx_sizes
        else:
            buffer, sizes = self._vb_buffer, self._vb_sizes
        strategy = getattr(self.settings_service.settings, "telemetry_writer_size_strategy", "count")
        track_bytes = strategy in ("bytes", "either")
        for row in reversed(batch):
            buffer.appendleft(row)
            if track_bytes:
                size = len(json.dumps(row, default=_json_default).encode())
                sizes.appendleft(size)
                if kind == "transactions":
                    self._tx_bytes += size
                else:
                    self._vb_bytes += size

    def _spill_to_disk(self, own_dir: Path, *, kind: str, buffer: collections.deque[dict[str, Any]]) -> None:
        """Append remaining in-memory rows to the on-disk SQLite outbox for replay.

        Honors ``telemetry_writer_max_queue`` so a pathological backlog at
        shutdown cannot fill disk or stall teardown — older rows beyond the
        cap are dropped and counted, matching the producer-side overflow
        policy.
        """
        max_rows = int(getattr(self.settings_service.settings, "telemetry_writer_max_queue", 100_000))
        try:
            spilled, dropped = _Outbox(own_dir / kind).append_all(buffer, max_rows=max_rows)
        except (sqlite3.Error, OSError):
            logger.exception(f"telemetry_writer: failed to spill {kind} buffer to disk")
            return
        if dropped:
            if kind == "transactions":
                self.dropped_transactions += dropped
            else:
                self.dropped_vertex_builds += dropped
            logger.warning(f"telemetry_writer: dropped {dropped} oldest {kind} rows at shutdown (over {max_rows} cap)")
        if spilled:
            logger.info(f"telemetry_writer: spilled {spilled} {kind} rows to disk at shutdown")
        # ``append_all`` drained the buffer; reset the parallel size tracking so
        # a future enqueue under the same writer instance starts fresh.
        if kind == "transactions":
            self._tx_sizes.clear()
            self._tx_bytes = 0
        else:
            self._vb_sizes.clear()
            self._vb_bytes = 0

    def _restore_from_disk(self, own_dir: Path, *, kind: str, buffer: collections.deque[dict[str, Any]]) -> None:
        """Load any disk-spilled rows from the previous run of this PID.

        Honors ``telemetry_writer_max_queue`` so a pathologically large spill
        from a previous run cannot OOM the new process — older rows beyond the
        cap are dropped and counted.
        """
        try:
            payloads = _Outbox(own_dir / kind).drain()
        except (sqlite3.Error, OSError):
            logger.exception(f"telemetry_writer: failed to restore {kind} spill from disk")
            return
        for payload in payloads:
            self._enqueue(buffer, payload, kind=kind)
        if payloads:
            logger.info(f"telemetry_writer: restored {len(payloads)} {kind} rows from disk")

    def _adopt_orphan_outboxes(self, outbox_root: Path, *, own_pid: int) -> None:
        """Replay outboxes from dead workers into the current in-memory buffer.

        Only adopts directories whose ``owner.json`` matches the current host
        and boot — a recycled PID on a different host (e.g. container restart
        with reset low PIDs) must not pull in a stranger's spill data.
        Pre-owner-file directories from older versions are skipped, not
        silently adopted.
        """
        try:
            entries = list(outbox_root.iterdir())
        except FileNotFoundError:
            return
        current_host, current_boot = _host_boot_identity()
        for entry in entries:
            if not entry.is_dir():
                continue
            try:
                pid = int(entry.name)
            except ValueError:
                continue
            if pid == own_pid or _pid_alive(pid):
                continue
            owner = _read_owner_file(entry)
            if owner is None:
                logger.info(f"telemetry_writer: skipping orphan outbox pid={pid} — no owner file")
                continue
            if owner.get("host") != current_host or owner.get("boot") != current_boot:
                logger.info(
                    f"telemetry_writer: skipping cross-host orphan outbox pid={pid} "
                    f"(host={owner.get('host')!r} boot={owner.get('boot')!r})"
                )
                continue
            for kind, buffer in (("transactions", self._tx_buffer), ("vertex_builds", self._vb_buffer)):
                try:
                    payloads = _Outbox(entry / kind).drain()
                except (sqlite3.Error, OSError):
                    logger.exception(f"telemetry_writer: failed to adopt orphan outbox {entry / kind}")
                    continue
                # Route through _enqueue so a huge orphan spill can't blow
                # past telemetry_writer_max_queue and OOM the process.
                for payload in payloads:
                    self._enqueue(buffer, payload, kind=kind)
                if payloads:
                    logger.info(f"telemetry_writer: adopted {len(payloads)} orphan {kind} from pid={pid}")
            # Best-effort cleanup of the dead-PID directory.
            try:
                for child in sorted(entry.rglob("*"), reverse=True):
                    if child.is_file():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        with suppress(OSError):
                            child.rmdir()
                entry.rmdir()
            except OSError as e:
                logger.debug(f"telemetry_writer: could not remove orphan dir {entry}: {e}")

    def _prune_stale_foreign_outboxes(self, outbox_root: Path) -> None:
        """Delete cross-host orphan dirs whose owner file has gone stale.

        Same-host orphans go through :py:meth:`_adopt_orphan_outboxes` and have
        their rows replayed before the dir is removed. Cross-host orphans (e.g.
        dead pods on a shared volume) are not safely adoptable because the rows
        carry the dead host's identity, so they would otherwise leak forever.
        We rely on :py:meth:`_heartbeat_owner_file` to keep the owner file's
        mtime fresh while the writer is alive; once the mtime ages past
        ``telemetry_writer_orphan_max_age_s`` the dir is treated as abandoned.
        """
        max_age = float(getattr(self.settings_service.settings, "telemetry_writer_orphan_max_age_s", 3600.0))
        current_host, _ = _host_boot_identity()
        now = time.time()
        try:
            entries = list(outbox_root.iterdir())
        except FileNotFoundError:
            return
        for entry in entries:
            if not entry.is_dir():
                continue
            owner = _read_owner_file(entry)
            if owner is None or owner.get("host") == current_host:
                continue
            owner_file = entry / _OWNER_FILE_NAME
            try:
                age = now - owner_file.stat().st_mtime
            except OSError:
                continue
            if age < max_age:
                continue
            logger.info(
                f"telemetry_writer: pruning stale cross-host outbox {entry} "
                f"(host={owner.get('host')!r}, age={age:.0f}s)"
            )
            try:
                for child in sorted(entry.rglob("*"), reverse=True):
                    if child.is_file():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        with suppress(OSError):
                            child.rmdir()
                entry.rmdir()
            except OSError as e:
                logger.debug(f"telemetry_writer: could not remove stale foreign outbox {entry}: {e}")

    def _heartbeat_owner_file(self) -> None:
        """Refresh the owner file's mtime so foreign hosts can age us out cleanly."""
        if self._own_outbox_dir is None:
            return
        with suppress(OSError):
            (self._own_outbox_dir / _OWNER_FILE_NAME).touch()

    async def _run_writer(self) -> None:
        if self._shutdown_event is None:
            return  # not started
        settings = self.settings_service.settings
        batch_size = int(getattr(settings, "telemetry_writer_batch_size", 200))
        flush_interval = float(getattr(settings, "telemetry_writer_flush_interval_s", 0.5))
        strategy = getattr(settings, "telemetry_writer_size_strategy", "count")
        batch_size_bytes: int | None = (
            int(getattr(settings, "telemetry_writer_batch_size_bytes", 262_144))
            if strategy in ("bytes", "either")
            else None
        )
        consecutive_failures = 0
        while True:
            should_stop = self._shutdown_event.is_set()
            tx_batch = self._drain_batch("transactions", batch_size, batch_size_bytes)
            vb_batch = self._drain_batch("vertex_builds", batch_size, batch_size_bytes)

            if not tx_batch and not vb_batch:
                if should_stop:
                    return
                await self._wait_or_shutdown(flush_interval, name="telemetry-writer-tick")
                continue

            try:
                await self._flush(tx_batch, vb_batch)
                consecutive_failures = 0
                self.flushed_rows += len(tx_batch) + len(vb_batch)
            except asyncio.CancelledError:
                # Shutdown cancelled us mid-flush. Put the in-flight batch back
                # in the buffer so teardown's spill_to_disk catches it.
                self._return_batch_to_buffer("transactions", tx_batch)
                self._return_batch_to_buffer("vertex_builds", vb_batch)
                raise
            except Exception:  # noqa: BLE001
                self.failed_batches += 1
                consecutive_failures += 1
                logger.exception("telemetry_writer: batch flush failed; will retry")
                # Put rows back at the front so the next iteration retries.
                self._return_batch_to_buffer("transactions", tx_batch)
                self._return_batch_to_buffer("vertex_builds", vb_batch)
                # Exponential-ish backoff capped at 30s. Avoids hot-looping on a
                # broken DB while still preserving telemetry across the failure.
                backoff = min(30.0, 0.5 * (2 ** min(consecutive_failures, 6)))
                if consecutive_failures >= _FAILURE_ESCALATION_THRESHOLD:
                    logger.error(
                        f"telemetry_writer: {consecutive_failures} consecutive batch failures, "
                        f"buffer depth tx={len(self._tx_buffer)} vb={len(self._vb_buffer)}"
                    )
                await self._wait_or_shutdown(backoff, name="telemetry-writer-backoff")

    async def _flush(self, tx_batch: list[dict], vb_batch: list[dict]) -> None:
        if not tx_batch and not vb_batch:
            return
        if self._session_maker is None:
            return
        async with self._session_maker() as session:
            if tx_batch:
                await session.execute(TransactionTable.__table__.insert(), params=tx_batch)
                for row in tx_batch:
                    flow_id = row.get("flow_id")
                    if flow_id is not None:
                        self._dirty_tx_flows.add(str(flow_id))
            if vb_batch:
                await session.execute(VertexBuildTable.__table__.insert(), params=vb_batch)
                for row in vb_batch:
                    flow_id = row.get("flow_id")
                    if flow_id is not None:
                        self._dirty_vb_flows.add(str(flow_id))
            await session.commit()

    async def _run_sweeper(self) -> None:
        """Amortized retention sweep + cross-host orphan janitor + own-dir heartbeat."""
        if self._shutdown_event is None:
            return
        while not self._shutdown_event.is_set():
            interval = float(getattr(self.settings_service.settings, "telemetry_writer_cleanup_interval_s", 60))
            await self._wait_or_shutdown(interval, name="telemetry-sweeper-tick")
            if self._shutdown_event.is_set():
                return
            self._heartbeat_owner_file()
            try:
                await self._run_retention_pass()
            except Exception:  # noqa: BLE001
                logger.exception("telemetry_writer: retention sweep failed")
            try:
                self._prune_stale_foreign_outboxes(self._outbox_root())
            except Exception:  # noqa: BLE001
                logger.exception("telemetry_writer: cross-host orphan prune failed")

    async def _run_retention_pass(self) -> None:
        if self._session_maker is None:
            return
        settings = self.settings_service.settings
        max_transactions = int(getattr(settings, "max_transactions_to_keep", 3000))
        max_vertex_builds = int(getattr(settings, "max_vertex_builds_to_keep", 3000))
        max_per_vertex = int(getattr(settings, "max_vertex_builds_per_vertex", 50))

        # Hand off ownership of the current dirty sets to this sweep. New
        # flush activity during the sweep accumulates into the now-empty live
        # sets and gets picked up on the next pass. On failure we restore the
        # snapshot so the next sweep retries these flows. Dirty flow ids were
        # stringified at flush time for set hashing; convert back to UUID for
        # SQLAlchemy parameter binding.
        def _as_uuid(value: str) -> UUID:
            return value if isinstance(value, UUID) else UUID(value)

        tx_flow_snapshot = set(self._dirty_tx_flows)
        vb_flow_snapshot = set(self._dirty_vb_flows)
        self._dirty_tx_flows -= tx_flow_snapshot
        self._dirty_vb_flows -= vb_flow_snapshot
        tx_flows = [_as_uuid(f) for f in tx_flow_snapshot]
        vb_flows = [_as_uuid(f) for f in vb_flow_snapshot]

        try:
            async with self._session_maker() as session:
                for flow_id in tx_flows:
                    keep_subq = (
                        select(TransactionTable.id)
                        .where(TransactionTable.flow_id == flow_id)
                        .order_by(col(TransactionTable.timestamp).desc())
                        .limit(max_transactions)
                    )
                    await session.execute(
                        delete(TransactionTable).where(
                            TransactionTable.flow_id == flow_id,
                            col(TransactionTable.id).not_in(keep_subq),
                        )
                    )

                for flow_id in vb_flows:
                    vertex_ids = (
                        (
                            await session.execute(
                                select(VertexBuildTable.id).where(VertexBuildTable.flow_id == flow_id).distinct()
                            )
                        )
                        .scalars()
                        .all()
                    )
                    for vertex_id in vertex_ids:
                        keep_vertex_subq = (
                            select(VertexBuildTable.build_id)
                            .where(
                                VertexBuildTable.flow_id == flow_id,
                                VertexBuildTable.id == vertex_id,
                            )
                            .order_by(
                                col(VertexBuildTable.timestamp).desc(),
                                col(VertexBuildTable.build_id).desc(),
                            )
                            .limit(max_per_vertex)
                        )
                        await session.execute(
                            delete(VertexBuildTable).where(
                                VertexBuildTable.flow_id == flow_id,
                                VertexBuildTable.id == vertex_id,
                                col(VertexBuildTable.build_id).not_in(keep_vertex_subq),
                            )
                        )

                keep_global_subq = (
                    select(VertexBuildTable.build_id)
                    .order_by(
                        col(VertexBuildTable.timestamp).desc(),
                        col(VertexBuildTable.build_id).desc(),
                    )
                    .limit(max_vertex_builds)
                )
                await session.execute(
                    delete(VertexBuildTable).where(col(VertexBuildTable.build_id).not_in(keep_global_subq))
                )
                await session.commit()
        except Exception:
            # Sweep failed before commit — restore the handed-off snapshot so
            # the next sweep retries these flows. Without this the per-flow
            # caps could overshoot indefinitely until those flows see new
            # writes.
            self._dirty_tx_flows |= tx_flow_snapshot
            self._dirty_vb_flows |= vb_flow_snapshot
            raise

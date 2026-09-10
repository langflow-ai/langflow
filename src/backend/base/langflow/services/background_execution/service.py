"""BackgroundExecutionService: the facade over the background-run primitives.

Composes the existing durable store (``JobService``) with the in-process
executor, the in-memory live bus, and the per-job runner. Methods:

* ``submit(flow_id, request, user) -> job_id``
* ``events(job_id, last_event_id, user) -> AsyncIterator[bytes]``
* ``status(job_id, user)`` / ``result(job_id, user)``
* ``stop_job(job_id, user)``

This single-node slice always runs jobs on the in-process executor + in-memory
bus implemented here. ``LANGFLOW_JOB_QUEUE_TYPE=redis`` still selects the v1
``RedisJobQueueService`` elsewhere; this facade has no scaled backend on this
branch and runs in-process regardless.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from filelock import FileLock, Timeout
from lfx.log.logger import logger

from langflow.services.background_execution.executor import InProcessExecutor
from langflow.services.background_execution.live_bus import InMemoryLiveBus, LiveFrame
from langflow.services.background_execution.runner import JobRunner
from langflow.services.base import Service
from langflow.services.database.models.jobs.model import JobStatus, JobType, SignalType
from langflow.services.deps import get_job_service
from langflow.services.jobs.exceptions import DuplicateJobError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from uuid import UUID

    from lfx.services.settings.service import SettingsService

    from langflow.services.database.models.jobs.model import Job, JobEvent
    from langflow.services.database.models.user.model import UserRead

    # A frame-source factory returns the async-generator callable the runner drives.
    # Default wiring (Task 2.7) returns ``_stream_event_frames`` bound to the run's
    # adapter + flow; tests inject a scripted generator.
    #
    # Defined under TYPE_CHECKING on purpose: as a module-level runtime value,
    # ``Callable[..., Any]`` is a GenericAlias that passes ``isinstance(obj, type)``
    # but makes ``issubclass(obj, Service)`` raise on Python 3.10/3.14. The service
    # factory scans this module for ``Service`` subclasses (services/factory.py), so a
    # runtime alias here crashes service initialization on those interpreters.
    FrameSourceFactory = Callable[..., Any]

# Durable statuses that mean the run is over. ``events()`` keys off these (not the
# process-local live bus) so a reattach to a finished job replays and returns
# instead of tailing a bus that will never produce another frame.
_TERMINAL_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT})
_REQUEST_OVERRIDES_FORMAT_KEY = "request_overrides_format"
_REQUEST_OVERRIDES_KEY = "request_overrides"
_REQUEST_OVERRIDES_FORMAT = "fernet-json-v1"
_REQUEST_OVERRIDES_VERSION = 1
_REQUEST_OVERRIDE_FIELDS = frozenset({"globals", "tweaks"})
_REQUEST_OVERRIDES_CONTAINER_FIELD = "overrides"
_REQUEST_OVERRIDES_ERROR = {"type": "request_overrides_unavailable"}
_MAX_OVERRIDE_JSON_DEPTH = 64
_MAX_OVERRIDE_INTEGER_BITS = 14_000


class RequestOverridesUnavailableError(RuntimeError):
    """Retryable signal for request overrides blocked by unavailable cryptographic state."""

    def __init__(self) -> None:
        super().__init__("Background request overrides are unavailable.")


class RequestOverridesCorruptedError(RequestOverridesUnavailableError):
    """Fail-closed signal for an authenticated or structurally malformed persisted envelope."""


class InvalidRequestOverridesError(ValueError):
    """Caller-supplied request overrides do not match the supported JSON grammar."""

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"Invalid request override field: {field}")


class BackgroundExecutionService(Service):
    name = "background_execution_service"

    def __init__(
        self,
        settings_service: SettingsService,
        *,
        frame_source_factory: FrameSourceFactory | None = None,
        backend: Any | None = None,
    ) -> None:
        self.settings_service = settings_service
        self._settings = settings_service.settings
        self._is_redis = self._settings.background_backend_is_scaled
        # Scaled backend: the redis claim queue + Streams live bus + DB replay.
        # Injected in tests; otherwise built lazily from settings. In the default
        # (asyncio) path it stays None and the in-process executor runs jobs here.
        if backend is None and self._is_redis:
            backend = self._build_scaled_backend()
        self._backend = backend
        self._executor = InProcessExecutor(max_concurrency=self._settings.background_max_concurrency)
        self._bus = InMemoryLiveBus()
        # Process-unique owner token stamped on the heartbeat of jobs this API
        # process runs. Lets a liveness-aware sweep tell a job this live process
        # is running from a genuinely orphaned one.
        self._owner = f"api:{os.getpid()}:{uuid4().hex[:8]}"
        self._frame_source_factory = frame_source_factory
        self._deadline_task: asyncio.Task | None = None
        self._orphan_task: asyncio.Task | None = None
        self.set_ready()

    @property
    def _scaled(self) -> bool:
        """True when a redis-backed scaled backend is wired behind this facade."""
        return self._backend is not None

    def _build_scaled_backend(self) -> Any:
        """Build the redis-backed scaled backend from settings.

        Reuses the worker's redis-client resolution (URL -> host/port/db with the
        cache-redis fallbacks) so the API enqueues to the exact redis a worker
        drains, and ``select_background_backend`` so selection follows
        ``background_backend_is_scaled``. Returns None in the default path.
        """
        try:
            from langflow.services.background_execution.factory import select_background_backend
            from langflow.services.background_execution.worker import _build_redis_client
        except ImportError:
            # The scaled modules (worker/redis_backend) are not shipped on this branch;
            # degrade to the in-process executor instead of crashing the facade.
            logger.warning(
                "job_queue_type=redis requested but the scaled background backend is not "
                "available; falling back to the in-process executor."
            )
            return None
        from langflow.services.deps import get_job_service

        client = _build_redis_client(self._settings)
        return select_background_backend(self._settings, client=client, job_service=get_job_service())

    async def start(self) -> None:
        # Scaled mode: the external worker owns execution and its watchdogs.
        if self._scaled:
            return
        await self._executor.start()
        self._start_deadline_watchdog()
        self._start_orphan_watchdog()

    async def stop(self) -> None:
        watchdogs = [task for task in (self._deadline_task, self._orphan_task) if task is not None]
        for task in watchdogs:
            task.cancel()
        self._deadline_task = None
        self._orphan_task = None
        if watchdogs:
            await asyncio.gather(*watchdogs, return_exceptions=True)
        await self._executor.stop()

    def _start_deadline_watchdog(self) -> None:
        """Run the input-deadline sweep on the watchdog interval (only when the budget is set).

        Without this, a never-restarting process would enforce the deadline only on the
        startup sweep. The loop is skipped entirely when ``background_input_deadline_s`` is
        None, so default deployments spawn no extra task.
        """
        if self._settings.background_input_deadline_s is None or self._deadline_task is not None:
            return
        interval = self._settings.background_watchdog_interval_s

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval)
                with contextlib.suppress(Exception):
                    await self.sweep_input_deadlines()

        self._deadline_task = asyncio.create_task(_loop())

    def _start_orphan_watchdog(self) -> None:
        """Periodically reconcile dead owners when Redis mode fell back in-process.

        The release branch intentionally omits the scaled worker modules. Redis
        queue configuration therefore falls back to the in-process executor, but
        still sets ``_is_redis``. The startup path historically returned early in
        that state, leaving a dead replica's IN_PROGRESS rows stranded forever.
        Keep the fallback fleet self-healing without competing with a real scaled
        backend, whose worker owns its own retry-aware watchdog.
        """
        if not self._is_redis or self._scaled or self._orphan_task is not None:
            return
        interval = self._settings.background_watchdog_interval_s
        lease_ttl = self._settings.background_lease_ttl_s

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval)
                try:
                    await get_job_service().sweep_orphans(lease_ttl_s=lease_ttl)
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 -- a later watchdog tick must still run
                    await logger.aexception("Periodic background orphan sweep failed")

        self._orphan_task = asyncio.create_task(_loop())

    async def teardown(self) -> None:
        await self.stop()
        # Scaled mode: close the redis client this facade built so the API replica
        # does not leak its connection pool on shutdown. No-op in default mode.
        backend = self._backend
        if backend is not None and hasattr(backend, "teardown"):
            await backend.teardown()

    # ------------------------------------------------------------------ submit

    @staticmethod
    def _effective_session(job: Job) -> str:
        """The session/thread a job ran under, normalized the way the runner normalizes it.

        ``submit`` persists the submit request under ``job_metadata['request']`` and the
        runner threads ``request['session_id'] or str(flow_id)`` into the stream adapter
        (``_build_adapter``), so the same fallback keys the supersede scope. Legacy rows
        written before the request was persisted keep a flat ``job_metadata['session_id']``
        — read it the way ``_reconstruct_request`` does rather than mis-scoping them.
        """
        meta = job.job_metadata or {}
        persisted = meta.get("request")
        source = persisted if isinstance(persisted, dict) and persisted else meta
        return source.get("session_id") or str(job.flow_id)

    async def supersede_suspended_runs(
        self, *, flow_id: UUID, user_id: UUID, session_id: str | None = None
    ) -> list[UUID]:
        """Cancel this user's SUSPENDED runs of the flow so a rerun replaces the stale pause.

        A suspended run holds a pause nobody will answer once its owner reruns that
        conversation; left alive it piles up in every pending surface (badge, cards, trace
        bar). Scope is flow + user + effective session (``session_id``, falling back to the
        flow id — the runner's own normalization): a rerun replaces the stale pause of the
        SAME session/thread, while SUSPENDED runs of OTHER sessions stay untouched so one
        flow can serve many independent callers (#14599). Another user's pause on the same
        flow is never touched, and running jobs are untouched so parallel runs stay
        supported.
        """
        from sqlmodel import select

        from langflow.services.database.models.jobs.model import Job
        from langflow.services.deps import session_scope

        effective_session = session_id or str(flow_id)
        job_service = get_job_service()
        async with session_scope() as session:
            result = await session.exec(
                select(Job).where(
                    Job.flow_id == flow_id,
                    Job.user_id == user_id,
                    Job.status == JobStatus.SUSPENDED,
                    Job.type == JobType.WORKFLOW,
                )
            )
            # The session lives in job_metadata, so narrow to matching rows INSIDE the
            # scope: reading a JSON column off a row already detached from its session
            # would depend on the engine's expire_on_commit setting.
            stale_job_ids = [job.job_id for job in result.all() if self._effective_session(job) == effective_session]
        cancelled: list[UUID] = []
        for stale_job_id in stale_job_ids:
            if self._scaled:
                await self._backend.stop(str(stale_job_id))
                cancelled.append(stale_job_id)
            elif await self._cancel_suspended(stale_job_id, job_service):
                cancelled.append(stale_job_id)
        return cancelled

    async def submit(self, *, flow_id: UUID, request: dict[str, Any], user: UserRead) -> UUID:
        # Lazy-start the executor so the facade works whether or not the app
        # lifespan called start() first. start() is idempotent.
        await self.start()
        job_service = get_job_service()
        job_id = uuid4()
        dedupe_key = request.get("idempotency_key")
        # Construct and encrypt the durable payload BEFORE creating the row. The
        # QUEUED insert then commits the marker, plaintext-safe request, and
        # authenticated override envelope together; no worker can claim a row in
        # the old create-then-patch gap.
        initial_metadata = self._persisted_request_metadata(job_id=job_id, flow_id=flow_id, request=request)
        try:
            await job_service.create_job(
                job_id=job_id,
                flow_id=flow_id,
                user_id=user.id,
                dedupe_key=dedupe_key,
                # Serving end user (if any) rides the persisted request; record it so
                # status/stop/resume isolate on it. user_id stays the SID so the worker's
                # _user_stub(job.user_id) still fetches the SID-owned flow on re-enqueue.
                end_user_id=request.get("end_user_id"),
                initial_metadata=initial_metadata,
            )
        except DuplicateJobError:
            # Idempotent retry: a non-terminal job already exists for this key,
            # so return that job_id instead of queuing duplicate work. Falls
            # through to a fresh submit only if the existing row vanished in the
            # race between create_job's check and this lookup.
            existing = await self._existing_job_for_dedupe(dedupe_key, user.id)
            if existing is not None:
                return existing
            raise
        # After create_job so an idempotent retry returns the existing job instead of
        # cancelling it; the new job is QUEUED, so the suspended-only query skips it.
        await self.supersede_suspended_runs(flow_id=flow_id, user_id=user.id, session_id=request.get("session_id"))
        if self._scaled:
            # Scaled mode: hand the QUEUED job id to a worker via the redis claim
            # queue; the worker hydrates the request from the job row.
            await self._backend.enqueue(str(job_id))
        else:
            await self._enqueue(job_id=job_id, flow_id=flow_id, request=request, user=user)
        return job_id

    @staticmethod
    def _redact_request(request: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of ``request`` with secret-bearing overrides removed.

        Returns a shallow copy so the caller's dict (used for the live run) is not
        mutated. ``globals`` and ``tweaks`` are dropped from this plaintext blob;
        an authenticated encrypted envelope carries them for durable replay.
        """
        if "globals" not in request and "tweaks" not in request:
            return request
        redacted = dict(request)
        redacted.pop("globals", None)
        redacted.pop("tweaks", None)
        return redacted

    @classmethod
    def _validate_json_value(
        cls,
        value: Any,
        *,
        field: str,
        seen: set[int] | None = None,
        depth: int = 0,
    ) -> None:
        """Validate the deliberately narrow JSON value grammar used by overrides."""
        if depth > _MAX_OVERRIDE_JSON_DEPTH:
            raise InvalidRequestOverridesError(field)
        if value is None or isinstance(value, bool):
            return
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                raise InvalidRequestOverridesError(field) from None
            return
        if isinstance(value, int):
            # Bound decimal conversion below Python's default 4,300-digit
            # protection so behavior is stable on every supported interpreter.
            if value.bit_length() > _MAX_OVERRIDE_INTEGER_BITS:
                raise InvalidRequestOverridesError(field)
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                raise InvalidRequestOverridesError(field)
            return
        if not isinstance(value, (dict, list)):
            raise InvalidRequestOverridesError(field)
        if seen is None:
            seen = set()
        value_id = id(value)
        if value_id in seen:
            raise InvalidRequestOverridesError(field)
        seen.add(value_id)
        try:
            if isinstance(value, dict):
                for key, nested in value.items():
                    if not isinstance(key, str):
                        raise InvalidRequestOverridesError(field)
                    try:
                        key.encode("utf-8")
                    except UnicodeEncodeError:
                        raise InvalidRequestOverridesError(field) from None
                    cls._validate_json_value(nested, field=field, seen=seen, depth=depth + 1)
            else:
                for nested in value:
                    cls._validate_json_value(nested, field=field, seen=seen, depth=depth + 1)
        finally:
            seen.remove(value_id)

    @classmethod
    def _validated_overrides(cls, value: Any) -> dict[str, dict[str, Any]]:
        """Return validated globals/tweaks only, rejecting all other envelope shapes."""
        if not isinstance(value, dict) or not set(value).issubset(_REQUEST_OVERRIDE_FIELDS):
            raise InvalidRequestOverridesError(_REQUEST_OVERRIDES_CONTAINER_FIELD)
        overrides: dict[str, dict[str, Any]] = {}
        for key, nested in value.items():
            if not isinstance(nested, dict):
                raise InvalidRequestOverridesError(key)
            cls._validate_json_value(nested, field=key)
            overrides[key] = nested
        return overrides

    def _persisted_request_metadata(self, *, job_id: UUID, flow_id: UUID, request: dict[str, Any]) -> dict[str, Any]:
        """Build the atomic metadata payload for a background workflow row."""
        supplied_overrides = self._validated_overrides(
            {key: request[key] for key in _REQUEST_OVERRIDE_FIELDS if key in request}
        )
        # The API models default both fields to {}, so treat empty mappings as no
        # override rather than encrypting an envelope for every ordinary run.
        overrides = {key: value for key, value in supplied_overrides.items() if value}
        metadata: dict[str, Any] = {"request": self._redact_request(request)}
        if overrides:
            from langflow.services.auth.utils import get_fernet

            envelope = {
                "version": _REQUEST_OVERRIDES_VERSION,
                "job_id": str(job_id),
                "flow_id": str(flow_id),
                "overrides": overrides,
            }
            try:
                plaintext = json.dumps(
                    envelope,
                    allow_nan=False,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            except (RecursionError, TypeError, UnicodeError, ValueError, OverflowError) as exc:
                logger.warning(
                    "Background request override serialization failed",
                    job_id=str(job_id),
                    flow_id=str(flow_id),
                    stage="serialize",
                    error_type=type(exc).__name__,
                )
                raise InvalidRequestOverridesError(_REQUEST_OVERRIDES_CONTAINER_FIELD) from None
            except Exception as exc:  # noqa: BLE001 -- resource/server failures remain retryable
                logger.error(
                    "Background request override serialization unavailable",
                    job_id=str(job_id),
                    flow_id=str(flow_id),
                    stage="serialize",
                    error_type=type(exc).__name__,
                )
                raise RequestOverridesUnavailableError from None
            try:
                ciphertext = get_fernet(self.settings_service).encrypt(plaintext).decode("ascii")
            except Exception as exc:  # noqa: BLE001 -- every crypto/config failure becomes the same safe error
                logger.error(
                    "Background request override encryption failed",
                    job_id=str(job_id),
                    flow_id=str(flow_id),
                    stage="encrypt",
                    error_type=type(exc).__name__,
                )
                raise RequestOverridesUnavailableError from None
            metadata[_REQUEST_OVERRIDES_FORMAT_KEY] = _REQUEST_OVERRIDES_FORMAT
            metadata[_REQUEST_OVERRIDES_KEY] = ciphertext
        return metadata

    def _decrypt_request_overrides(self, job: Job, metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Authenticate, decrypt, bind, and validate a job's override envelope."""
        has_marker = _REQUEST_OVERRIDES_FORMAT_KEY in metadata
        has_ciphertext = _REQUEST_OVERRIDES_KEY in metadata
        if not has_marker and not has_ciphertext:
            # New no-override rows and safe legacy rows intentionally carry neither
            # key. Plaintext values are rejected separately by reconstruction.
            return {}
        if not has_marker or not has_ciphertext or metadata[_REQUEST_OVERRIDES_FORMAT_KEY] != _REQUEST_OVERRIDES_FORMAT:
            raise RequestOverridesCorruptedError
        ciphertext = metadata[_REQUEST_OVERRIDES_KEY]
        if not isinstance(ciphertext, str) or not ciphertext:
            raise RequestOverridesCorruptedError

        from langflow.services.auth.utils import get_fernet_for_decryption

        try:
            encoded_ciphertext = ciphertext.encode("ascii")
        except UnicodeEncodeError as exc:
            logger.error(
                "Background request override ciphertext validation failed",
                job_id=str(job.job_id),
                flow_id=str(job.flow_id),
                stage="validate",
                error_type=type(exc).__name__,
            )
            raise RequestOverridesCorruptedError from None
        except Exception as exc:  # noqa: BLE001 -- resource/server failures remain retryable
            logger.error(
                "Background request override ciphertext encoding unavailable",
                job_id=str(job.job_id),
                flow_id=str(job.flow_id),
                stage="encode",
                error_type=type(exc).__name__,
            )
            raise RequestOverridesUnavailableError from None

        try:
            plaintext = get_fernet_for_decryption(self.settings_service).decrypt(encoded_ciphertext)
        except Exception as exc:  # noqa: BLE001 -- Fernet auth failure cannot distinguish bad key from tampering
            logger.error(
                "Background request override decryption failed",
                job_id=str(job.job_id),
                flow_id=str(job.flow_id),
                stage="decrypt",
                error_type=type(exc).__name__,
            )
            raise RequestOverridesUnavailableError from None

        try:
            envelope = json.loads(plaintext)
            if not isinstance(envelope, dict) or set(envelope) != {"version", "job_id", "flow_id", "overrides"}:
                raise RequestOverridesCorruptedError
            if type(envelope["version"]) is not int or envelope["version"] != _REQUEST_OVERRIDES_VERSION:
                raise RequestOverridesCorruptedError
            if envelope["job_id"] != str(job.job_id) or envelope["flow_id"] != str(job.flow_id):
                raise RequestOverridesCorruptedError
            try:
                overrides = self._validated_overrides(envelope["overrides"])
            except InvalidRequestOverridesError:
                raise RequestOverridesCorruptedError from None
            if not overrides:
                raise RequestOverridesCorruptedError
        except RequestOverridesCorruptedError as exc:
            logger.error(
                "Background request override envelope validation failed",
                job_id=str(job.job_id),
                flow_id=str(job.flow_id),
                stage="validate",
                error_type=type(exc).__name__,
            )
            raise
        except (RecursionError, TypeError, UnicodeError, ValueError, OverflowError) as exc:
            logger.error(
                "Background request override parsing failed",
                job_id=str(job.job_id),
                flow_id=str(job.flow_id),
                stage="parse",
                error_type=type(exc).__name__,
            )
            raise RequestOverridesCorruptedError from None
        except Exception as exc:  # noqa: BLE001 -- resource/server failures remain retryable
            logger.error(
                "Background request override parsing unavailable",
                job_id=str(job.job_id),
                flow_id=str(job.flow_id),
                stage="parse",
                error_type=type(exc).__name__,
            )
            raise RequestOverridesUnavailableError from None
        else:
            return overrides

    @staticmethod
    async def _existing_job_for_dedupe(dedupe_key: str | None, user_id: UUID | None) -> UUID | None:
        """Return the active job_id sharing ``dedupe_key`` for this user, if any.

        Mirrors ``create_job``'s non-terminal set (QUEUED / IN_PROGRESS /
        COMPLETED) so a retried POST resolves to the same job a terminal job
        with the same key would not block (allowing a genuine re-run).
        """
        if dedupe_key is None:
            return None
        from sqlmodel import col, select

        from langflow.services.database.models.jobs.model import Job as JobModel
        from langflow.services.deps import session_scope

        async with session_scope() as session:
            stmt = (
                select(JobModel)
                .where(JobModel.dedupe_key == dedupe_key)
                # Why: SUSPENDED included so a retry while paused at a HITL node can't bypass dedupe.
                .where(
                    col(JobModel.status).in_(
                        [JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.SUSPENDED, JobStatus.COMPLETED]
                    )
                )
            )
            if user_id is not None:
                stmt = stmt.where(JobModel.user_id == user_id)
            result = await session.exec(stmt)
            row = result.first()
            return row.job_id if row is not None else None

    async def _enqueue(self, *, job_id: UUID, flow_id: UUID, request: dict[str, Any], user: UserRead | None) -> None:
        """Build a runner for the job and submit it to the in-process executor."""
        job_service = get_job_service()
        adapter = self._build_adapter(request, job_id, flow_id)
        source = self._frame_source_factory(request=request, flow_id=flow_id, user=user, adapter=adapter)
        runner = JobRunner(
            job_service=job_service,
            live_bus=self._bus,
            adapter=adapter,
            frame_source=source,
            job_timeout=self._settings.background_job_timeout,
            owner=self._owner,
            heartbeat_interval_s=self._settings.background_heartbeat_interval_s,
            input_deadline_s=self._settings.background_input_deadline_s,
        )

        async def _coro() -> None:
            # job_id reaches the frame source via source_kwargs so the default
            # build-loop source can tag its memory-base hook with the run's job.
            await runner.run(job_id=job_id, source_kwargs={"job_id": job_id})

        await self._executor.submit(str(job_id), _coro)

    # ------------------------------------------------------------------ events

    async def events(
        self,
        job_id: UUID,
        last_event_id: str | None,
        user: UserRead,
    ) -> AsyncIterator[bytes]:
        job = await self._validate(job_id, user)
        job_service = get_job_service()
        last_seq = self._parse_last_event_id(last_event_id)
        # The durable replay must serialize with the SAME separators the live
        # adapter used (agui = compact, langflow = spaced) so replayed bytes are
        # byte-identical. The protocol is on the persisted submit request.
        protocol = self._job_protocol(job)

        async def read_durable(after_seq: int) -> list[LiveFrame]:
            rows = await job_service.read_events(job_id, after_seq=after_seq)
            return [LiveFrame(seq=r.seq, data=self._row_to_frame(r, protocol=protocol)) for r in rows]

        # Terminal jobs must be answered from the DURABLE log alone. The live bus
        # is process-local: after a restart it is fresh and its ``_closed`` marker
        # is empty, so ``reattach`` would replay durable rows then block forever on
        # ``while True: queue.get()`` waiting for a live tail that will never come.
        # Decide "finished" off the persisted status (the cross-restart source of
        # truth), replay, and return.
        # SUSPENDED is parked awaiting human input: no live tail to wait on, so answer
        # from the durable log alone (like a terminal status) instead of blocking.
        if job.status in _TERMINAL_STATUSES or job.status == JobStatus.SUSPENDED:
            for frame in await read_durable(last_seq):
                yield frame.data
            return

        # Scaled mode: any API replica serves reattach by replaying durable
        # job_events (from the DB) then tailing the shared redis Stream.
        if self._scaled:
            async for item in self._backend.events(str(job_id), last_event_id=last_seq):
                seq = getattr(item, "seq", None)
                if seq is not None:
                    yield self._row_to_frame(item, protocol=protocol)
                else:
                    yield item.payload
            return

        async def _is_terminal() -> bool:
            # SUSPENDED ends the tail too: a run that connected while IN_PROGRESS and
            # then suspended has no live tail to wait on (the pause isn't published live).
            current = await job_service.get_job_by_job_id(job_id)
            return current is not None and (
                current.status in _TERMINAL_STATUSES or current.status == JobStatus.SUSPENDED
            )

        async for frame in self._bus.reattach(
            str(job_id), last_seq=last_seq, read_durable=read_durable, is_done=_is_terminal
        ):
            yield frame.data

    # ------------------------------------------------------------------ status

    async def status(self, job_id: UUID, user: UserRead) -> dict[str, Any]:
        job = await self._validate(job_id, user)
        payload: dict[str, Any] = {
            "job_id": str(job.job_id),
            "flow_id": str(job.flow_id),
            "status": job.status,
        }
        # Surface durable result/error additively.
        if job.result is not None:
            payload["result"] = job.result
        if job.error is not None:
            payload["error"] = job.error
        if job.status == JobStatus.SUSPENDED:
            pending = await get_job_service().get_pending_human_request(job_id)
            if pending is not None:
                payload["pending_request"] = pending
        return payload

    async def result(self, job_id: UUID, user: UserRead) -> Any:
        job = await self._validate(job_id, user)
        return job.result

    async def stop_job(self, job_id: UUID, user: UserRead) -> None:
        job = await self._validate(job_id, user)
        if self._scaled:
            # Scaled mode: the owning worker runs in another process; backend.stop
            # writes the durable STOP signal its JobRunner polls at vertex boundaries.
            await self._backend.stop(str(job_id))
            return
        job_service = get_job_service()
        # A lost claim means a resume flipped it IN_PROGRESS mid-call — fall
        # through to the running-job stop path instead of doing nothing.
        if job.status == JobStatus.SUSPENDED and await self._cancel_suspended(job_id, job_service):
            return
        await job_service.write_signal(job_id, SignalType.STOP)
        await self._executor.cancel(str(job_id))

    async def resume_job(self, job_id: UUID, user: UserRead, *, request_id: str, decision: Any) -> bool:  # noqa: ARG002
        """Carry a human decision back into a SUSPENDED run and re-enqueue it.

        Returns True when the run was accepted for resume, False on a conflict
        (not suspended, stale request_id, or lost the single-flight flip) — the
        route maps False to 409. Ownership (owner-or-superuser) is enforced at the
        HTTP route, so this fetches by id alone and trusts the already-validated user.
        """
        job_service = get_job_service()
        job = await job_service.get_job_by_job_id(job_id)
        if job is None or job.type != JobType.WORKFLOW or job.status != JobStatus.SUSPENDED:
            return False
        pending = (job.job_metadata or {}).get("pending_request_id")
        if pending is not None and request_id != pending:
            return False
        # Decrypt and validate before the single-flight claim or signal write. A
        # key-rotation/configuration error must leave the pause and decision seam
        # untouched so the caller can retry after restoring the key.
        request = self._reconstruct_request(job)
        # Win the single-flight flip BEFORE writing the RESUME signal, so exactly one
        # RESUME row exists per suspend and a loser never strands a stray decision.
        if not await job_service.claim_suspended_for_resume(job_id, owner=self._owner):
            return False
        await job_service.write_signal(job_id, SignalType.RESUME, {"decision": decision, "request_id": request_id})
        try:
            await self._enqueue(
                job_id=job_id,
                flow_id=job.flow_id,
                request=request,
                user=self._user_stub(job.user_id),
            )
        except Exception:
            # Why: claim already flipped SUSPENDED→IN_PROGRESS; a failed enqueue would strand the job
            # and lose the decision — roll back to SUSPENDED (clearing RESUME) so it can be retried.
            with contextlib.suppress(Exception):
                await job_service.consume_signals(job_id, SignalType.RESUME)
            await job_service.update_job_status(job_id, JobStatus.SUSPENDED)
            raise
        return True

    async def _cancel_suspended(self, job_id: UUID, job_service) -> bool:
        """Cancel a SUSPENDED job; False when a concurrent resume already claimed it.

        The conditional claim is what makes supersede-vs-resume safe: cleanup
        (checkpoint delete, metadata clear, terminal event) runs only for the row
        this caller actually flipped, never for a run a resume just revived.
        """
        if not await job_service.claim_suspended_for_cancel(job_id):
            return False
        from langflow.api.v2.hitl import mark_card_superseded

        await mark_card_superseded(job_id)
        with contextlib.suppress(Exception):
            await job_service.delete_checkpoint(job_id, "graph")
        await job_service.update_job_metadata(job_id, {"pending_request_id": None})
        await job_service.append_event(job_id, "run_cancelled", {"type": "cancelled"})
        await job_service.consume_signals(job_id, SignalType.STOP)
        await self._bus.close(str(job_id))
        return True

    # ----------------------------------------------------------- startup sweep

    async def sweep_orphans_on_startup(self) -> None:
        """Reconcile jobs left mid-flight by a crashed process.

        Single-flight across workers: this runs in the per-worker lifespan on
        every uvicorn/gunicorn boot, so it is guarded by a file lock (the same
        primitive ``main.py`` uses for starter projects). Only ONE booting worker
        runs the IN_PROGRESS reconcile; the others skip it. The reconcile is also
        liveness-aware (``sweep_orphans`` only fails rows whose heartbeat is
        stale/absent), so even without the lock a booting worker can never flip a
        sibling's actively-running, freshly-heartbeated job FAILED.

        ``JobService.sweep_orphans`` does the durable reconcile (FAILED +
        worker_lost + terminal event). QUEUED workflow rows never started, so
        under at-least-once we re-enqueue them onto this worker's executor with a
        reconstructed request. Best-effort per job so one bad row can't block the
        rest. A real scaled Redis backend reconciles via its own watchdog; when
        those modules are unavailable, the in-process fallback starts its local
        periodic watchdog and performs this initial sweep.
        """
        await self.start()
        job_service = get_job_service()
        lease_ttl = self._settings.background_lease_ttl_s
        if self._is_redis:
            if not self._scaled:
                await job_service.sweep_orphans(lease_ttl_s=lease_ttl)
            return
        # Single-flight the IN_PROGRESS reconcile: only the worker that wins the
        # lock fails orphans; the others skip (a non-blocking try-acquire). The
        # QUEUED re-enqueue below stays per-worker because each row is lease-claimed
        # atomically (claim_queued_lease), so two workers cannot double-run it.
        lock_file = Path(tempfile.gettempdir()) / "langflow_bg_orphan_sweep.lock"
        lock = FileLock(lock_file, timeout=0)
        try:
            with lock:
                # Fail genuinely-orphaned IN_PROGRESS rows (stale/absent heartbeat).
                await job_service.sweep_orphans(lease_ttl_s=lease_ttl)
        except Timeout:
            # Another worker is running the reconcile; skip ours.
            await logger.adebug("Another worker is sweeping orphans, skipping")
        # Re-enqueue QUEUED workflow rows (at-least-once for not-yet-started work).
        # Each row is LEASE-claimed (single-flight) WITHOUT flipping it to
        # IN_PROGRESS, so two workers booting against the same DB cannot both
        # re-run it (only the claim whose rowcount==1 enqueues), AND a re-enqueue
        # that crashes before the runner starts leaves the row QUEUED and
        # re-runnable on the next boot rather than a stranded IN_PROGRESS the next
        # sweep would fail worker_lost. The runner's execute_with_status performs
        # the real QUEUED->IN_PROGRESS flip once it actually starts emitting.
        for job in await self._queued_workflow_jobs():
            lease_heartbeat = datetime.now(timezone.utc).isoformat()
            if not await job_service.claim_queued_lease(
                job.job_id,
                owner=self._owner,
                lease_ttl_s=lease_ttl,
                heartbeat_at=lease_heartbeat,
            ):
                continue
            try:
                request_dict = self._reconstruct_request(job)
            except RequestOverridesCorruptedError:
                await job_service.fail_queued_job(
                    job.job_id,
                    owner=self._owner,
                    heartbeat_at=lease_heartbeat,
                    error=dict(_REQUEST_OVERRIDES_ERROR),
                    event_type="run_failed",
                )
                continue
            except RequestOverridesUnavailableError as exc:
                await logger.aerror(
                    "Background request overrides unavailable during startup recovery",
                    job_id=str(job.job_id),
                    flow_id=str(job.flow_id),
                    stage="startup_restore",
                    error_type=type(exc).__name__,
                )
                await job_service.release_queued_lease(
                    job.job_id,
                    owner=self._owner,
                    heartbeat_at=lease_heartbeat,
                )
                continue
            user = self._user_stub(job.user_id)
            with contextlib.suppress(Exception):
                await self._enqueue(
                    job_id=job.job_id,
                    flow_id=job.flow_id,
                    request=request_dict,
                    user=user,
                )
        # Give up on runs that have sat suspended past their human-input deadline.
        with contextlib.suppress(Exception):
            await self.sweep_input_deadlines()

    async def sweep_input_deadlines(self) -> list[UUID]:
        """Enforce the input deadline (LE-1452): FAIL overdue SUSPENDED runs, close their bus.

        The durable FAIL + terminal event is JobService's; this also closes any live bus
        still held open for a same-process suspended run so a reattaching client ends
        cleanly. A no-op (and never queries the DB) when the deadline is disabled.
        """
        if self._settings.background_input_deadline_s is None:
            return []
        failed = await get_job_service().sweep_input_deadlines()
        for job_id in failed:
            with contextlib.suppress(Exception):
                await self._bus.close(str(job_id))
        return failed

    @staticmethod
    async def _queued_workflow_jobs() -> list[Job]:
        from sqlmodel import select

        from langflow.services.database.models.jobs.model import Job as JobModel
        from langflow.services.deps import session_scope

        async with session_scope() as session:
            stmt = select(JobModel).where(
                JobModel.status == JobStatus.QUEUED,
                JobModel.type == JobType.WORKFLOW,
            )
            result = await session.exec(stmt)
            return list(result.all())

    def _reconstruct_request(self, job: Job) -> dict[str, Any]:
        """Rebuild the request dict for a re-enqueued QUEUED job.

        ``submit`` persists replay-safe fields under ``job_metadata["request"]``
        and globals/tweaks in an authenticated Fernet envelope beside it. Legacy
        rows with no overrides keep their old fallback; legacy plaintext overrides
        and malformed encrypted rows fail closed.
        """
        meta = job.job_metadata or {}
        persisted = meta.get("request")
        if isinstance(persisted, dict) and persisted:
            request = dict(persisted)
        else:
            request = {
                "flow_id": str(job.flow_id),
                "mode": "background",
                "stream_protocol": meta.get("stream_protocol", "langflow"),
                "session_id": meta.get("session_id"),
                "input_value": meta.get("input_value", ""),
            }
        # Pre-fix v2 requests always included empty override defaults. They carry
        # no value and are safe to normalize away; every other plaintext shape
        # remains a fail-closed downgrade attempt.
        for key in _REQUEST_OVERRIDE_FIELDS.intersection(request):
            value = request.pop(key)
            if not isinstance(value, dict) or value:
                raise RequestOverridesCorruptedError
        return {**request, **self._decrypt_request_overrides(job, meta)}

    @staticmethod
    def _user_stub(user_id: UUID | None) -> UserRead | None:
        """A minimal UserRead carrying only ``id``.

        The default frame source only reads ``user.id`` (to fetch the flow), so
        a partial object is sufficient. Returns None for legacy ownerless jobs.
        """
        if user_id is None:
            return None
        from langflow.services.database.models.user.model import UserRead

        return UserRead.model_construct(id=user_id)

    # ----------------------------------------------------------------- helpers

    async def _validate(self, job_id: UUID, user: UserRead) -> Job:
        job_service = get_job_service()
        try:
            job = await job_service._validate_ownership(job_id, user.id)  # noqa: SLF001
        except ValueError as exc:
            raise PermissionError(str(exc)) from exc
        if job.type != JobType.WORKFLOW:
            msg = f"Job {job_id} is not a workflow job"
            raise PermissionError(msg)
        return job

    @staticmethod
    def _job_protocol(job: Job) -> str:
        """The stream protocol the run used, read off the persisted submit request.

        ``submit`` persists the request (incl. ``stream_protocol``) under
        ``job_metadata['request']``. Replay needs it so it serializes durable
        rows with the SAME separators the live adapter used. Defaults to
        ``langflow`` for legacy rows written before the request was persisted.
        """
        meta = job.job_metadata or {}
        request = meta.get("request")
        if isinstance(request, dict):
            return request.get("stream_protocol") or "langflow"
        return meta.get("stream_protocol") or "langflow"

    def _build_adapter(self, request: dict[str, Any], job_id: UUID, flow_id: UUID):
        from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter

        protocol = request.get("stream_protocol", "langflow")
        return get_stream_adapter(
            protocol,
            StreamAdapterContext(
                run_id=str(job_id),
                thread_id=request.get("session_id") or str(flow_id),
            ),
        )

    @staticmethod
    def _parse_last_event_id(last_event_id: str | None) -> int:
        if not last_event_id:
            return 0
        try:
            return int(last_event_id)
        except ValueError:
            return 0

    @staticmethod
    def _row_to_frame(row: JobEvent, *, protocol: str = "langflow") -> bytes:
        # Re-frame the durable payload through the SAME SSE formatter the live
        # path uses (``format_sse_event(data_str=..., id=str(seq))``) so replayed
        # bytes are byte-compatible with live frames and a client's
        # ``Last-Event-ID`` resume works across the replay/tail boundary. The
        # live path passes the payload's JSON string as ``data_str``; ``seq`` is
        # the durable row seq, matching the live frame's ``id``.
        #
        # The JSON separators must match the LIVE adapter or the replayed bytes
        # are not byte-identical: the ``langflow`` adapter serializes via
        # ``json.dumps`` (default spaced separators) while the ``agui`` adapter
        # serializes via pydantic ``model_dump_json`` (compact separators). Pick
        # the matching separators by protocol so replay == live for both wires.
        from fastapi.sse import format_sse_event

        separators = (",", ":") if protocol == "agui" else None
        return format_sse_event(data_str=json.dumps(row.payload, separators=separators), id=str(row.seq))

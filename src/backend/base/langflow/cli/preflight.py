"""Production deployment preflight checks.

When Langflow boots with ``--deployment-profile prod`` (or
``LANGFLOW_DEPLOYMENT_PROFILE=prod``), this module runs a set of fail-loud
infrastructure checks in the CLI parent process *before* any worker is spawned:

- **Required** checks (database, file storage, encryption secret key, pgVector)
  abort the boot when they fail — the process exits non-zero and no worker
  starts, so a misconfigured production deployment never comes up "half working".
- **Degraded** checks (telemetry, cache, shared queue) surface reduced
  capabilities. Telemetry only ever warns. Cache and shared queue warn when they
  fall back to their in-process default, but *abort* when an external backend is
  explicitly selected (e.g. LANGFLOW_CACHE_TYPE=redis) yet is unreachable — a
  deployment that asked for a shared backend and did not get one is misconfigured,
  not merely degraded. The operator can unset the backend to boot degraded.

Design notes:

- Every probe is fork-safe. Sync database engines are disposed after use, and
  the cache / queue / storage services are built through their factories as
  *throwaway* instances (never registered in the global service manager) and
  torn down before returning. This matters because on Linux the Gunicorn master
  forks workers *after* ``run()`` completes — a lingering open socket in the
  parent would be inherited by every worker.
- Checks run once, all of them, before any abort: the operator sees every
  problem in a single pass instead of fix-one / restart / hit-the-next.
- ``dev`` (the default profile) never invokes any of this.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import click
from lfx.log.logger import logger

from langflow.cli.progress import ProgressIndicator

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from lfx.services.settings.service import SettingsService

# Env sentinel: set once the preflight has run in this process tree so forked
# workers (which inherit the environment) skip re-running it. This is what keeps
# a multi-worker ``langflow run`` from probing infrastructure N times.
PREFLIGHT_COMPLETED_ENV = "LANGFLOW_PREFLIGHT_COMPLETED"

Status = Literal["ok", "warn", "fail"]
Severity = Literal["required", "degraded"]

# In-process cache/queue backends: selecting one of these (or leaving the
# default) is a degraded-but-allowed configuration. Anything else names an
# external backend (e.g. redis) whose reachability is then required.
_IN_MEMORY_CACHE_TYPES = frozenset({"async", "memory"})
_IN_PROCESS_QUEUE_TYPES = frozenset({"asyncio"})

# Probe timeouts (seconds). ``_PROBE_CONNECT_TIMEOUT`` is handed to the database
# driver (libpq ``connect_timeout``) so a black-holed host fails fast at the
# socket layer instead of hanging on the OS default. ``_PROBE_TIMEOUT`` is the
# outer asyncio ceiling wrapped around each probe (the whole connect + query, or
# the cache ping) so no single probe can stall the boot indefinitely even if a
# driver ignores its own timeout.
_PROBE_CONNECT_TIMEOUT = 10
_PROBE_TIMEOUT = 15


class PreflightAbortError(Exception):
    """Raised when a required production preflight check fails.

    Callers convert this into a clean process exit: the CLI prints the rendered
    summary and exits non-zero; the FastAPI lifespan hard-exits the worker.
    """


# Map a check status to the ProgressIndicator terminal status used for rendering.
_PROGRESS_STATUS: dict[Status, str] = {"ok": "completed", "warn": "warning", "fail": "failed"}

# Platform-safe summary glyphs (mirror ProgressIndicator's icon set).
if platform.system() == "Windows":
    _OK_ICON, _FAIL_ICON = "+", "x"
else:
    _OK_ICON, _FAIL_ICON = "✓", "✗"


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single preflight probe."""

    status: Status
    detail: str
    remediation: str = ""


@dataclass(frozen=True)
class PreflightCheck:
    """A named preflight check bound to its async probe function."""

    key: str
    label: str
    severity: Severity
    probe: Callable[[SettingsService], Awaitable[CheckResult]]


@dataclass(frozen=True)
class CheckOutcome:
    """A check paired with the result of running it."""

    check: PreflightCheck
    result: CheckResult


def _short_exc(exc: BaseException) -> str:
    """Return a concise, single-line description of an exception for display."""
    text = str(exc).strip()
    first_line = text.splitlines()[0] if text else exc.__class__.__name__
    return first_line[:200]


def _sanitize_dsn(dsn: str) -> str:
    """Render a database DSN with the password redacted, best-effort."""
    try:
        import sqlalchemy as sa

        return sa.make_url(dsn).render_as_string(hide_password=True)
    except Exception:  # noqa: BLE001 — display helper must never raise
        return dsn


# ---------------------------------------------------------------------------
# Required checks
# ---------------------------------------------------------------------------


async def probe_database(settings_service: SettingsService) -> CheckResult:
    """Require a reachable PostgreSQL application database.

    In prod the database must be PostgreSQL: SQLite is single-node, not shared
    across replicas, and unsupported for production Langflow, so a SQLite (or
    otherwise non-Postgres) ``LANGFLOW_DATABASE_URL`` fails the check *before*
    any connection is attempted. When the URL is Postgres, a throwaway
    connection is opened and closed to prove reachability.
    """
    import sqlalchemy as sa

    from langflow.services.database.service import _normalize_sync_postgres_url

    database_url = settings_service.settings.database_url
    if not database_url:
        return CheckResult(
            "fail",
            "no database configured",
            "Set LANGFLOW_DATABASE_URL to your production PostgreSQL connection string.",
        )

    sync_url = _normalize_sync_postgres_url(database_url)
    try:
        backend = sa.make_url(sync_url).get_backend_name()
    except Exception:  # noqa: BLE001 — an unparseable URL is a failed check, not a crash
        backend = ""
    if backend != "postgresql":
        described = backend or "an unrecognized database"
        return CheckResult(
            "fail",
            f"production requires a PostgreSQL database, but LANGFLOW_DATABASE_URL is {described}",
            "Set LANGFLOW_DATABASE_URL to a PostgreSQL connection string (postgresql://...). SQLite is "
            "single-node and not shared across replicas, so it is not supported in prod.",
        )

    def _connect() -> str:
        engine = sa.create_engine(sync_url, connect_args={"connect_timeout": _PROBE_CONNECT_TIMEOUT})
        try:
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
        finally:
            engine.dispose()
        return _sanitize_dsn(database_url)

    remediation = (
        "Verify the database is running and LANGFLOW_DATABASE_URL is correct (host, port, credentials, network)."
    )
    try:
        target = await asyncio.wait_for(asyncio.to_thread(_connect), timeout=_PROBE_TIMEOUT)
    except asyncio.TimeoutError:
        return CheckResult("fail", f"could not connect (timed out after {_PROBE_TIMEOUT}s)", remediation)
    except Exception as exc:  # noqa: BLE001 — any driver/network error is a failed check
        return CheckResult("fail", f"could not connect ({_short_exc(exc)})", remediation)
    return CheckResult("ok", f"reachable ({target})")


async def probe_storage(settings_service: SettingsService) -> CheckResult:
    """Require an external object store in prod and probe its readiness.

    Backend-agnostic: builds the configured storage backend through its factory
    (as a throwaway, off the global service manager) and delegates to
    ``StorageService.check_readiness()``.
    """
    raw_storage_type = settings_service.settings.storage_type or "local"
    if raw_storage_type.strip().lower() == "local":
        return CheckResult(
            "fail",
            "local filesystem storage is not allowed in prod",
            "Set LANGFLOW_STORAGE_TYPE=s3 (or another external object store) so files "
            "persist and are shared across replicas.",
        )

    from langflow.services.session.service import SessionService
    from langflow.services.storage.factory import StorageServiceFactory
    from langflow.services.storage.local import LocalStorageService

    # session_service is unused by check_readiness; a throwaway keeps this probe
    # off the global service manager so nothing is inherited across fork.
    storage_service = StorageServiceFactory().create(
        session_service=SessionService(cache_service=None),
        settings_service=settings_service,
    )
    try:
        # The factory does not raise on an unrecognized storage_type: it logs a
        # warning and silently returns LocalStorageService (gcs, a typo, "s3 "
        # with a stray space, etc. all land here). In prod that fallback must
        # fail loud rather than pass the check as a writable local directory.
        if isinstance(storage_service, LocalStorageService):
            return CheckResult(
                "fail",
                f"unsupported storage backend '{raw_storage_type}' — the storage factory fell back to "
                "local filesystem storage, which is not allowed in prod",
                "Set LANGFLOW_STORAGE_TYPE to a supported external object store (e.g. s3). Check for "
                "typos or stray whitespace in the value.",
            )
        readiness = await storage_service.check_readiness()
    finally:
        with contextlib.suppress(Exception):
            await storage_service.teardown()

    if readiness.ok:
        return CheckResult("ok", f"{readiness.backend} {readiness.detail}")

    remediations = {
        "no-credentials": "Provide credentials via environment variables or an instance role.",
        "bucket-missing": "Create the bucket or fix LANGFLOW_OBJECT_STORAGE_BUCKET_NAME.",
        "access-denied": "Grant the credentials read/write access to the bucket.",
        "unreachable": "Verify network egress to the object storage endpoint.",
        "unwritable": "Ensure the configured storage path is writable.",
    }
    return CheckResult(
        "fail",
        readiness.detail,
        remediations.get(readiness.reason, "Verify the storage backend configuration and credentials."),
    )


async def probe_secret_key(settings_service: SettingsService) -> CheckResult:
    """Require a usable operator-supplied encryption secret key (not auto-generated).

    Reads provenance from the environment because the materialized settings
    value is indistinguishable between env-supplied, file-loaded, and
    per-boot auto-generated keys.
    """
    secret_key = os.environ.get("LANGFLOW_SECRET_KEY", "")
    if secret_key.strip():
        from cryptography.fernet import Fernet

        from langflow.services.auth.utils import ensure_fernet_key

        try:
            Fernet(ensure_fernet_key(secret_key))
        except ValueError as exc:
            return CheckResult(
                "fail",
                f"operator-supplied but unusable ({_short_exc(exc)})",
                "Set LANGFLOW_SECRET_KEY to a URL-safe base64-encoded 32-byte key, such as the output of "
                "Fernet.generate_key(), and use the same value in every replica.",
            )
        return CheckResult("ok", "operator-supplied (LANGFLOW_SECRET_KEY)")

    config_dir = settings_service.settings.config_dir
    secret_file = Path(config_dir) / "secret_key" if config_dir else None
    if secret_file is not None and secret_file.exists():
        return CheckResult(
            "fail",
            "secret key is node-local (config_dir/secret_key), not shared across replicas",
            "Set LANGFLOW_SECRET_KEY to a fixed value in every replica so JWTs and encrypted "
            "variables stay valid across pods and restarts.",
        )
    return CheckResult(
        "fail",
        "secret key is auto-generated per boot",
        "Set LANGFLOW_SECRET_KEY to a URL-safe base64-encoded 32-byte key, such as the output of "
        "Fernet.generate_key(), and use the same value in every replica.",
    )


class _VectorExtensionMissingError(Exception):
    """Raised internally when Postgres is reachable but the pgvector extension is absent."""


async def probe_pgvector(_settings_service: SettingsService) -> CheckResult:
    """Verify pgVector: connection string present, reachable, and extension installed.

    pgVector is a mandated, Langflow-owned production dependency, so this is an
    active probe rather than a presence check.
    """
    from lfx.base.knowledge_bases.backends.postgres import (
        _normalize_driver,
        read_connection_string_from_env,
    )

    dsn = read_connection_string_from_env()
    if not dsn:
        return CheckResult(
            "fail",
            "PGVECTOR_CONNECTION_STRING is not set",
            "Set PGVECTOR_CONNECTION_STRING to the pgvector Postgres connection string (required in prod).",
        )

    def _probe() -> None:
        import sqlalchemy as sa

        engine = sa.create_engine(_normalize_driver(dsn), connect_args={"connect_timeout": _PROBE_CONNECT_TIMEOUT})
        try:
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
                row = conn.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first()
                if row is None:
                    raise _VectorExtensionMissingError
        finally:
            engine.dispose()

    try:
        await asyncio.wait_for(asyncio.to_thread(_probe), timeout=_PROBE_TIMEOUT)
    except _VectorExtensionMissingError:
        return CheckResult(
            "fail",
            "reachable, but the 'vector' extension is not installed",
            "Enable pgvector on the target database: CREATE EXTENSION vector;",
        )
    except asyncio.TimeoutError:
        return CheckResult(
            "fail",
            f"could not reach pgvector Postgres (timed out after {_PROBE_TIMEOUT}s)",
            "Verify PGVECTOR_CONNECTION_STRING (host, port, credentials, network).",
        )
    except Exception as exc:  # noqa: BLE001 — any driver/network error is a failed check
        return CheckResult(
            "fail",
            f"could not reach pgvector Postgres ({_short_exc(exc)})",
            "Verify PGVECTOR_CONNECTION_STRING (host, port, credentials, network).",
        )
    return CheckResult("ok", "reachable, 'vector' extension present")


# ---------------------------------------------------------------------------
# Degraded checks (warn only)
# ---------------------------------------------------------------------------


_MCP_SERVING_POSTURE: tuple[tuple[str, bool, str], ...] = (
    ("skip_mcp_auto_init", True, "LANGFLOW_SKIP_MCP_AUTO_INIT"),
    ("add_projects_to_mcp_servers", False, "LANGFLOW_ADD_PROJECTS_TO_MCP_SERVERS"),
    ("mcp_composer_enabled", False, "LANGFLOW_MCP_COMPOSER_ENABLED"),
    ("mcp_servers_locked", True, "LANGFLOW_MCP_SERVERS_LOCKED"),
    ("mcp_sse_enabled", False, "LANGFLOW_MCP_SSE_ENABLED"),
    ("mcp_server_interpreter_hardening", True, "LANGFLOW_MCP_SERVER_INTERPRETER_HARDENING"),
    ("mcp_server_docker_hardening", True, "LANGFLOW_MCP_SERVER_DOCKER_HARDENING"),
    ("ssrf_protection_enabled", True, "LANGFLOW_SSRF_PROTECTION_ENABLED"),
    ("connector_ssrf_validation_enabled", True, "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED"),
    ("connector_ssrf_allow_loopback", False, "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK"),
    ("disable_track_apikey_usage", True, "LANGFLOW_DISABLE_TRACK_APIKEY_USAGE"),
)


async def probe_mcp_posture(settings_service: SettingsService) -> CheckResult:
    """Report MCP knobs left at a single-tenant default on a production boot.

    Each of these defaults to the permissive value, so a multi-tenant serving plane must
    override eleven settings by hand and nothing tells the operator when one is missed.
    Degraded rather than required on purpose: promoting it to a boot failure would break
    every existing ``prod`` deployment that has not adopted the list. The deploy job is
    the right place to make the same list a hard precondition.
    """
    settings = settings_service.settings
    if not settings.mcp_server_enabled:
        return CheckResult("ok", "MCP server disabled (LANGFLOW_MCP_SERVER_ENABLED=false)")

    unsafe = [env for attr, expected, env in _MCP_SERVING_POSTURE if getattr(settings, attr, expected) != expected]
    if settings.mcp_server_allowed_packages is None:
        unsafe.append("LANGFLOW_MCP_SERVER_ALLOWED_PACKAGES")
    # Unset means the built-in runtime-family env policy is the only env control. That policy is
    # deny-by-default and blocks the known loader/interpreter/package-source families, but a
    # multi-tenant plane should pin the exact env names its servers may set.
    if getattr(settings, "mcp_server_env_allowlist", None) is None:
        unsafe.append("LANGFLOW_MCP_SERVER_ENV_ALLOWLIST")

    if not unsafe:
        return CheckResult("ok", "hardened for multi-tenant serving")

    return CheckResult(
        "warn",
        f"{len(unsafe)} setting(s) at a single-tenant default: {', '.join(unsafe)}",
        remediation="Set each listed variable to its multi-tenant-safe value, or set "
        "LANGFLOW_MCP_SERVER_ENABLED=false if this plane does not serve MCP.",
    )


async def probe_telemetry(settings_service: SettingsService) -> CheckResult:
    """Config-only telemetry check (no outbound network call at boot)."""
    if settings_service.settings.do_not_track:
        return CheckResult(
            "warn",
            "disabled (LANGFLOW_DO_NOT_TRACK) — usage analytics will not be reported",
        )
    return CheckResult("ok", "enabled")


async def probe_cache(settings_service: SettingsService) -> CheckResult:
    """Cache reachability.

    - In-memory default (async/memory) → warn (single-instance fallback).
    - External backend selected (redis) and reachable → ok.
    - External backend selected but unreachable → fail (aborts the boot). The
      operator must fix the backend or unset LANGFLOW_CACHE_TYPE to fall back.

    The Redis cache is built as a throwaway and torn down before returning so
    no fork-unsafe connection is retained in the parent.
    """
    cache_type = (settings_service.settings.cache_type or "async").lower()
    if cache_type in _IN_MEMORY_CACHE_TYPES:
        return CheckResult(
            "warn",
            f"no external cache selected — falls back to an in-memory cache ('{cache_type}'); "
            "not shared across pods, so multi-replica deployments run with isolated, "
            "single-instance cache semantics",
            "Set LANGFLOW_CACHE_TYPE=redis (with LANGFLOW_REDIS_* / LANGFLOW_REDIS_URL) for a "
            "cache shared across replicas.",
        )

    from langflow.services.cache.factory import CacheServiceFactory
    from langflow.services.cache.service import RedisCache

    cache_service = CacheServiceFactory().create(settings_service)
    # Ping the Redis client directly rather than via is_connected(): the latter
    # logs a full traceback on failure, which is noise here since we render our
    # own concise result below.
    connected = False
    try:
        client = getattr(cache_service, "_client", None)
        if isinstance(cache_service, RedisCache) and client is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(client.ping(), timeout=_PROBE_TIMEOUT)
                connected = True
    finally:
        teardown = getattr(cache_service, "teardown", None)
        if teardown is not None:
            with contextlib.suppress(Exception):
                await teardown()

    if connected:
        return CheckResult("ok", f"{cache_type} reachable")
    return CheckResult(
        "fail",
        f"cache backend '{cache_type}' selected (LANGFLOW_CACHE_TYPE) but unreachable",
        "Start the cache backend / fix LANGFLOW_REDIS_* settings, or unset LANGFLOW_CACHE_TYPE "
        "to boot with a degraded in-memory cache.",
    )


async def probe_shared_queue(settings_service: SettingsService) -> CheckResult:
    """Shared job-queue reachability.

    - In-process default (asyncio) → warn (per-pod fallback).
    - External backend selected (redis) and reachable → ok.
    - External backend selected but unreachable → fail (aborts the boot). The
      operator must fix the backend or unset LANGFLOW_JOB_QUEUE_TYPE to fall back.
    """
    queue_type = (settings_service.settings.job_queue_type or "asyncio").lower()
    if queue_type in _IN_PROCESS_QUEUE_TYPES:
        return CheckResult(
            "warn",
            f"no external queue selected — falls back to the in-process '{queue_type}' queue; "
            "jobs are per-pod, so horizontal scaling will not distribute work across replicas",
            "Set LANGFLOW_JOB_QUEUE_TYPE=redis (with LANGFLOW_REDIS_QUEUE_* settings) so jobs are "
            "shared across replicas.",
        )

    from langflow.services.job_queue.factory import JobQueueServiceFactory
    from langflow.services.job_queue.service import RedisJobQueueService

    # is_connected() on an unstarted service uses a temporary client it closes
    # itself, so this throwaway retains no connection.
    queue_service = JobQueueServiceFactory().create(settings_service)
    if isinstance(queue_service, RedisJobQueueService):
        if await queue_service.is_connected():
            return CheckResult("ok", f"redis reachable ({queue_service.connection_target})")
        return CheckResult(
            "fail",
            f"queue backend 'redis' selected (LANGFLOW_JOB_QUEUE_TYPE) but unreachable at "
            f"{queue_service.connection_target}",
            "Start Redis / fix LANGFLOW_REDIS_QUEUE_* settings, or unset LANGFLOW_JOB_QUEUE_TYPE "
            "to boot with the degraded in-process queue.",
        )
    return CheckResult("ok", f"reachable ({queue_type})")


# ---------------------------------------------------------------------------
# Registry + runner
# ---------------------------------------------------------------------------

REQUIRED_CHECKS: list[PreflightCheck] = [
    PreflightCheck("database", "Database service", "required", probe_database),
    PreflightCheck("storage", "File storage", "required", probe_storage),
    PreflightCheck("secret_key", "Encryption secret key", "required", probe_secret_key),
    PreflightCheck("pgvector", "Vector backend (pgVector)", "required", probe_pgvector),
]

DEGRADED_CHECKS: list[PreflightCheck] = [
    PreflightCheck("mcp_posture", "MCP serving posture", "degraded", probe_mcp_posture),
    PreflightCheck("telemetry", "Telemetry", "degraded", probe_telemetry),
    PreflightCheck("cache", "Cache service", "degraded", probe_cache),
    PreflightCheck("shared_queue", "Shared queue (Redis)", "degraded", probe_shared_queue),
]

ALL_CHECKS: list[PreflightCheck] = REQUIRED_CHECKS + DEGRADED_CHECKS


async def _probe_safely(check: PreflightCheck, settings_service: SettingsService) -> CheckResult:
    """Run a probe, converting an *unexpected* crash into a result by severity.

    The abort decision is driven by the returned status: any ``fail`` aborts the
    boot, whichever section the check lives in (this is what lets a degraded
    check like cache/queue hard-fail when its external backend is unreachable).

    Severity only governs the fallback for an unexpected exception: a required
    check that crashes fails the boot, while a degraded check that crashes is
    downgraded to a warning — an internal probe bug should not abort on a
    subsystem that is merely advisory.
    """
    try:
        return await check.probe(settings_service)
    except Exception as exc:  # noqa: BLE001 — a probe crash must not crash the runner
        await logger.adebug(f"Preflight check '{check.key}' raised: {exc!r}")
        status: Status = "fail" if check.severity == "required" else "warn"
        return CheckResult(status, f"check error ({_short_exc(exc)})", "See logs for details.")


async def collect_outcomes(
    settings_service: SettingsService,
    *,
    checks: list[PreflightCheck] | None = None,
) -> list[CheckOutcome]:
    """Run the given checks (default: all) and return their outcomes. No rendering."""
    selected = checks if checks is not None else ALL_CHECKS
    return [CheckOutcome(check, await _probe_safely(check, settings_service)) for check in selected]


def summarize(outcomes: list[CheckOutcome]) -> bool:
    """Return True when no check failed (boot may continue).

    Any ``fail`` aborts — required checks, and degraded checks whose explicitly
    selected external backend is unreachable.
    """
    return not any(o.result.status == "fail" for o in outcomes)


def _render_summary(outcomes: list[CheckOutcome]) -> bool:
    """Print the final verdict and remediation list. Returns True if boot may continue."""
    fails = [o for o in outcomes if o.result.status == "fail"]
    passed = sum(1 for o in outcomes if o.result.status == "ok")
    warnings = sum(1 for o in outcomes if o.result.status == "warn")

    click.echo()
    if not fails:
        icon = click.style(_OK_ICON, fg="green", bold=True)
        click.echo(f"{icon} Preflight passed — {passed} OK, {warnings} warning(s). Continuing boot.")
        return True

    icon = click.style(_FAIL_ICON, fg="red", bold=True)
    count = len(fails)
    plural = "s" if count > 1 else ""
    click.echo(
        click.style(
            f"{icon} Preflight failed — {count} check{plural} did not pass. Aborting boot.",
            fg="red",
            bold=True,
        )
    )
    for outcome in fails:
        remediation = outcome.result.remediation or "See logs for details."
        click.echo(click.style(f"  • {outcome.check.label}: {remediation}", fg="red"))
    return False


async def _execute_and_render(settings_service: SettingsService, *, verbose: bool) -> list[CheckOutcome]:
    """Run every check with the procedural display and return their outcomes."""
    profile = settings_service.settings.deployment_profile
    click.echo()
    click.echo(click.style(f"Deployment profile: {profile} — running production preflight", fg="cyan", bold=True))

    outcomes: list[CheckOutcome] = []
    for section_title, checks in (("Required services", REQUIRED_CHECKS), ("Degraded services", DEGRADED_CHECKS)):
        click.echo()
        click.echo(click.style(section_title, bold=True))
        indicator = ProgressIndicator(verbose=verbose)
        for check in checks:
            indicator.add_step(check.label, indent="  ")
        for idx, check in enumerate(checks):
            indicator.start_step(idx)
            result = await _probe_safely(check, settings_service)
            indicator.complete_step(idx, status=_PROGRESS_STATUS[result.status], detail=result.detail)
            outcomes.append(CheckOutcome(check, result))

    return outcomes


async def ensure_production_preflight(settings_service: SettingsService, *, verbose: bool = False) -> None:
    """Run the production preflight once, from any entrypoint.

    This is the single enforcement point reached by every startup route: the CLI
    ``run`` command calls it before forking, and the FastAPI lifespan calls it so
    routes that bypass the CLI (``make backend``, direct ``uvicorn --factory``,
    raw Gunicorn) are still covered.

    It is a no-op unless ``deployment_profile == 'prod'`` and is idempotent across
    a process tree: the first caller sets ``LANGFLOW_PREFLIGHT_COMPLETED=1`` in the
    environment, which forked workers inherit, so the checks run exactly once on a
    multi-worker ``langflow run`` deployment.

    Raises:
        PreflightAbortError: if any check fails — a required check, or a degraded
            check whose explicitly selected external backend is unreachable.
            Callers translate this into a clean process exit (the CLI prints and
            exits 1; the lifespan hard-exits).
    """
    if settings_service.settings.deployment_profile != "prod":
        return
    if os.environ.get(PREFLIGHT_COMPLETED_ENV) == "1":
        return

    outcomes = await _execute_and_render(settings_service, verbose=verbose)
    # Mark done before deciding: on the pass path forked workers must skip; on the
    # fail path the process exits anyway, so the flag is harmless.
    os.environ[PREFLIGHT_COMPLETED_ENV] = "1"

    if not _render_summary(outcomes):
        failed = [o.check.key for o in outcomes if o.result.status == "fail"]
        msg = f"Production preflight failed: {', '.join(failed)}"
        raise PreflightAbortError(msg)


def run_production_preflight(settings_service: SettingsService, *, verbose: bool = False) -> bool:
    """Synchronous entrypoint for the CLI.

    Runs the production preflight and returns True when boot may continue, or
    False when a required check failed (the caller should abort). Safe to call
    for any profile: it no-ops unless the profile is ``prod``.
    """
    try:
        asyncio.run(ensure_production_preflight(settings_service, verbose=verbose))
    except PreflightAbortError:
        return False
    return True

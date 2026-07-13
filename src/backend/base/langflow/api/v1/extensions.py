"""Extension System HTTP surface: reload.

Currently exposes a single endpoint, ``POST /extensions/{extension_id}/bundles/{bundle_name}/reload``,
which drives the atomic-swap reload pipeline against the process-default
:class:`~lfx.extension.bundle_registry.BundleRegistry`.

Future list / status / migrate endpoints will live alongside this one.
Mode A only -- in Mode B/C the path is to rebuild the Docker image, and
the runtime guard at the request layer short-circuits with 404 when
``LANGFLOW_ENABLE_EXTENSION_RELOAD`` is off.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from lfx.extension.bundle_registry import get_default_registry
from lfx.extension.errors import ExtensionError
from lfx.extension.reload import ReloadInProgressError, reload_bundle
from lfx.log.logger import logger
from lfx.services.deps import get_extension_events_service, get_settings_service
from pydantic import BaseModel

from langflow.api.utils.core import CurrentActiveUser

router = APIRouter(prefix="/extensions", tags=["Extensions"])


class ExtensionEventResponse(BaseModel):
    type: str
    timestamp: float
    payload: dict


class ExtensionEventsResponse(BaseModel):
    events: list[ExtensionEventResponse]
    settled: bool


def _typed_http_exception(*, status_code: int, error: ExtensionError) -> HTTPException:
    """Wrap an :class:`ExtensionError` in a FastAPI HTTPException.

    The ``detail`` body is the full ``{code, message, location, content,
    hint, ref_url}`` envelope, matching the typed-error contract documented
    in the extensions error guide.  Returning anything narrower here would
    drop the fix hint and the docs link from the client surface, which the
    palette + CLI consumers depend on.
    """
    return HTTPException(status_code=status_code, detail=error.to_dict())


def _require_extension_reload_enabled() -> None:
    """Per-request guard for the Mode A reload route.

    The route is always mounted (see ``langflow.api.router``) so that
    ``--env-file`` can opt in to it without forcing route registration
    to happen after the env file is loaded.  Operators on Mode B/C
    deployments leave ``LANGFLOW_ENABLE_EXTENSION_RELOAD`` unset; the
    guard returns 404 so the route is indistinguishable from "not
    mounted" for those operators, with the typed error body so the
    client renders the same envelope shape it does for any other
    reload error.
    """
    settings = get_settings_service().settings
    if not getattr(settings, "enable_extension_reload", False):
        raise _typed_http_exception(
            status_code=status.HTTP_404_NOT_FOUND,
            error=ExtensionError(
                code="extension-reload-disabled",
                message=(
                    "Extension reload is disabled on this server.  "
                    "Set LANGFLOW_ENABLE_EXTENSION_RELOAD=true to enable it on "
                    "a local-development install (Mode A)."
                ),
                hint=(
                    "Local development: ``lfx extension dev`` sets the flag "
                    "for you.  Self-hosted: export LANGFLOW_ENABLE_EXTENSION_RELOAD=true "
                    "or include it in your --env-file."
                ),
            ),
        )


@router.post(
    "/{extension_id}/bundles/{bundle_name}/reload",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(_require_extension_reload_enabled),
    ],
)
async def reload_extension_bundle(
    extension_id: str,
    bundle_name: str,
    current_user: CurrentActiveUser,
) -> dict:
    """Trigger an atomic-swap reload for a single Bundle.

    Returns the typed :class:`~lfx.extension.reload.ReloadResult` body on
    success.  Per the typed-error contract, structural failures
    (broken bundle, missing source path, name mismatch) surface as
    ``422 Unprocessable Entity`` with the first typed error in the body
    so clients can surface fix hints inline; the full ``ReloadResult``
    payload (with all errors and warnings) is returned via the FastAPI
    ``detail`` envelope.  Concurrency-control collisions surface as
    ``409 Conflict`` (``reload-in-progress``).  Non-2xx is the wire
    contract for every error path -- the body still carries the typed
    error so the client renders the same fix-hint envelope.
    """
    registry = get_default_registry()
    record = registry.get_bundle(bundle_name)
    if record is not None and record.extension_id != extension_id:
        # Bundle name is registered but under a different extension -- treat as
        # a 404 so a typo in the URL doesn't mutate someone else's bundle.
        raise _typed_http_exception(
            status_code=status.HTTP_404_NOT_FOUND,
            error=ExtensionError(
                code="reload-bundle-not-installed",
                message=(
                    f"Bundle {bundle_name!r} is registered to extension {record.extension_id!r}, not {extension_id!r}."
                ),
                location=f"{extension_id}/{bundle_name}",
                content=bundle_name,
                hint=(
                    "Use the bundle's actual extension id (typically the pip "
                    "distribution name); run ``lfx extension list`` to see the "
                    "registered (extension, bundle) pairs."
                ),
            ),
        )

    try:
        # reload_bundle is synchronous and does substantial blocking work
        # (disk I/O, importlib execution of arbitrary extension code, file
        # hashing, RLock acquisition).  Run it off the event loop so a slow
        # or large bundle import does not freeze the worker for every other
        # in-flight request.  ``asyncio.to_thread`` propagates the result
        # and any exception (including ReloadInProgressError) back to us.
        result = await asyncio.to_thread(
            reload_bundle,
            registry,
            bundle_name,
            user_id=str(current_user.id),
        )
    except ReloadInProgressError as exc:
        # 409 is the conventional "in-progress / conflicting state" code.
        logger.info("extension reload-in-progress collision for %s", exc.bundle)
        raise _typed_http_exception(
            status_code=status.HTTP_409_CONFLICT,
            error=ExtensionError(
                code="reload-in-progress",
                message=str(exc),
                location=exc.bundle,
                content=exc.bundle,
                hint=(
                    "Wait for the in-flight reload to finish before retrying; "
                    "another tab or worker is already swapping this bundle."
                ),
            ),
        ) from exc

    if not result.ok:
        # Structural failure: surface as 422 with the first typed error so
        # the body shape matches every other typed-error response in this
        # router.  The full ReloadResult body (including additional errors
        # and warnings) is preserved under the HTTPException ``detail``.
        primary = (
            result.errors[0]
            if result.errors
            else ExtensionError(
                code="reload-failed",
                message=f"Reload failed for bundle {bundle_name!r}.",
                location=f"{extension_id}/{bundle_name}",
                hint="Run `lfx extension validate` against the bundle source for details.",
            )
        )
        logger.warning(
            "extension reload failed: bundle=%s code=%s",
            bundle_name,
            primary.code,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                **primary.to_dict(),
                "result": result.to_dict(),
            },
        )

    return result.to_dict()


@router.get(
    "/events",
    response_model=ExtensionEventsResponse,
)
async def get_extension_events(
    current_user: CurrentActiveUser,
    since: Annotated[float, Query(description="UTC epoch timestamp; return events after this cursor")] = 0.0,
    keyspace: Annotated[
        str | None,
        Query(
            description=(
                "Reserved. Events are scoped server-side to the authenticated user; "
                "passing this parameter is rejected with 422."
            ),
            include_in_schema=False,
        ),
    ] = None,
) -> ExtensionEventsResponse:
    """Poll for extension lifecycle events the current user has triggered.

    Events are scoped to the authenticated user via a server-derived keyspace
    (``user:{user_id}``); there is no client-controllable keyspace, so an
    authenticated user cannot read another user's flow-migration or
    bundle-reload events. A client-supplied ``keyspace`` query parameter is
    rejected with 422 so the contract is explicit -- previously the value was
    silently dropped, which masked client bugs that assumed it had effect.

    svc.since() uses blocking sqlite3; run in a thread pool so the asyncio
    event loop is not held while waiting on disk I/O.
    """
    if keyspace is not None:
        raise _typed_http_exception(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error=ExtensionError(
                code="extension-events-keyspace-forbidden",
                message=(
                    "The 'keyspace' query parameter is not accepted on /extensions/events; "
                    "events are scoped to the authenticated user automatically."
                ),
                location="query.keyspace",
                content=keyspace,
                hint=(
                    "Remove the 'keyspace' query parameter from the request; the server "
                    "derives the keyspace from the authenticated user."
                ),
            ),
        )
    svc = get_extension_events_service()
    if svc is None:
        return ExtensionEventsResponse(events=[], settled=True)
    keyspace = f"user:{current_user.id}"
    events, settled = await asyncio.to_thread(svc.since, since, keyspace)
    return ExtensionEventsResponse(
        events=[ExtensionEventResponse(type=e.type, timestamp=e.timestamp, payload=e.payload) for e in events],
        settled=settled,
    )

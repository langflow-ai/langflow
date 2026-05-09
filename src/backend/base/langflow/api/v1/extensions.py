"""Extension System HTTP surface (LE-1018: reload).

Currently exposes a single endpoint, ``POST /extensions/{extension_id}/bundles/{bundle_name}/reload``,
which drives the LE-1018 atomic-swap pipeline against the process-default
:class:`~lfx.extension.bundle_registry.BundleRegistry`.

LE-1019 (UI) and LE-1020 (migration) will add list / status / migrate
endpoints alongside this one.  Mode A only -- in Mode B/C the path is to
rebuild the Docker image, and the runtime guard at the request layer
short-circuits with 404 when ``LANGFLOW_ENABLE_EXTENSION_RELOAD`` is off.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from lfx.extension.bundle_registry import get_default_registry
from lfx.extension.reload import ReloadInProgressError, reload_bundle
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service

from langflow.services.auth.utils import get_current_active_user

router = APIRouter(prefix="/extensions", tags=["Extensions"])


def _require_extension_reload_enabled() -> None:
    """Per-request guard for the Mode A reload route.

    The route is always mounted (see ``langflow.api.router``) so that
    ``--env-file`` can opt in to it without forcing route registration
    to happen after the env file is loaded.  Operators on Mode B/C
    deployments leave ``LANGFLOW_ENABLE_EXTENSION_RELOAD`` unset; the
    guard returns 404 so the route is indistinguishable from "not
    mounted" for those operators.
    """
    settings = get_settings_service().settings
    if not getattr(settings, "enable_extension_reload", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "extension-reload-disabled",
                "message": (
                    "Extension reload is disabled.  Set "
                    "LANGFLOW_ENABLE_EXTENSION_RELOAD=true to enable it on a "
                    "local-development install (Mode A)."
                ),
            },
        )


@router.post(
    "/{extension_id}/bundles/{bundle_name}/reload",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(_require_extension_reload_enabled),
        Depends(get_current_active_user),
    ],
)
async def reload_extension_bundle(extension_id: str, bundle_name: str) -> dict:
    """Trigger an atomic-swap reload for a single Bundle.

    Returns the typed :class:`~lfx.extension.reload.ReloadResult` body on
    success.  On structural failure (broken bundle, missing source path,
    name mismatch) returns ``200`` with ``ok=false`` and the typed errors
    in the body so clients can surface fix hints inline -- this matches
    the pattern used by other validate-style endpoints in this API and
    keeps a successful import error from looking like a server fault.

    Surfaces ``409 Conflict`` only for the concurrency-control case
    (``reload-in-progress``); the body still carries the typed error so
    the client can render the fix hint.
    """
    registry = get_default_registry()
    record = registry.get_bundle(bundle_name)
    if record is not None and record.extension_id != extension_id:
        # Bundle name is registered but under a different extension -- treat as
        # a 404 so a typo in the URL doesn't mutate someone else's bundle.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "reload-bundle-not-installed",
                "message": (
                    f"Bundle {bundle_name!r} is registered to extension {record.extension_id!r}, not {extension_id!r}."
                ),
            },
        )

    try:
        result = reload_bundle(registry, bundle_name)
    except ReloadInProgressError as exc:
        # 409 is the conventional "in-progress / conflicting state" code.
        logger.info("extension reload-in-progress collision for %s", exc.bundle)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "reload-in-progress",
                "message": str(exc),
                "bundle": exc.bundle,
            },
        ) from exc

    return result.to_dict()

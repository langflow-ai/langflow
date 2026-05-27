"""Tests for the runtime gate on the Extension reload route.

The route is always mounted (no import-time dependency on the env file
having been loaded yet); a per-request dependency reads the live
``settings.enable_extension_reload`` and returns ``404`` when off.  This
keeps Mode B/C deployments indistinguishable from "not mounted" while
allowing ``--env-file LANGFLOW_ENABLE_EXTENSION_RELOAD=true`` to opt
into the route at runtime.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status
from langflow.api.v1.extensions import _require_extension_reload_enabled


def _make_settings(*, enable: bool):
    settings = MagicMock()
    settings.enable_extension_reload = enable
    service = MagicMock()
    service.settings = settings
    return service


def test_guard_raises_404_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard must return 404 with the FULL typed-error envelope when the flag is off.

    The body must include ``code``, ``message``, ``hint``, and ``ref_url``
    fields so palette / CLI consumers render the same shape they do for
    every other reload error.  An ad-hoc ``{code, message}`` body would
    drop the hint that tells the user how to enable the flag.
    """
    monkeypatch.setattr(
        "langflow.api.v1.extensions.get_settings_service",
        lambda: _make_settings(enable=False),
    )

    with pytest.raises(HTTPException) as exc:
        _require_extension_reload_enabled()

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    detail = exc.value.detail
    assert isinstance(detail, dict)
    # Full ExtensionError envelope -- code + hint + docs link must all
    # survive the trip through HTTPException.
    assert detail["code"] == "extension-reload-disabled"
    assert "LANGFLOW_ENABLE_EXTENSION_RELOAD" in detail["message"]
    assert detail["hint"]
    assert detail["ref_url"].endswith("#extension-reload-disabled")


def test_guard_passes_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard must be a no-op when the flag is on."""
    monkeypatch.setattr(
        "langflow.api.v1.extensions.get_settings_service",
        lambda: _make_settings(enable=True),
    )

    # Must not raise.
    _require_extension_reload_enabled()


def test_guard_treats_missing_attribute_as_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defensive: a settings object missing the field must not enable the route."""
    settings = MagicMock(spec=[])  # no attributes
    service = MagicMock()
    service.settings = settings
    monkeypatch.setattr(
        "langflow.api.v1.extensions.get_settings_service",
        lambda: service,
    )

    with pytest.raises(HTTPException) as exc:
        _require_extension_reload_enabled()

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_route_is_mounted_unconditionally() -> None:
    """The reload route must be registered regardless of env-var state.

    Regression: an earlier implementation read ``LANGFLOW_ENABLE_EXTENSION_RELOAD``
    at import time, which meant ``--env-file`` could not turn the route on
    because ``langflow.__main__`` imports the router before ``load_dotenv``
    runs.  Mounting unconditionally + runtime guard fixes this.
    """
    from langflow.api.router import router

    def collect_paths(routes, prefix: str = "") -> list[str]:
        out: list[str] = []
        for route in routes:
            if hasattr(route, "routes"):
                out.extend(collect_paths(route.routes, prefix + getattr(route, "prefix", "")))
            elif hasattr(route, "path"):
                out.append(prefix + route.path)
        return out

    paths = collect_paths(router.routes)
    assert any("/extensions/" in p and "/reload" in p for p in paths), (
        f"Extension reload route must be mounted unconditionally; mounted paths: {paths}"
    )


def test_no_runtime_mutation_routes() -> None:
    """CI guard: no extension route may match install/uninstall/registry patterns.

    Invariant for the LE-905 first-delivery slice: runtime mutation
    (install/uninstall/registry changes) must never happen on a live server.

    Fix hint:
      Mode B/C (Docker/self-hosted): rebuild the image with the new package.
      Mode A (local dev): use ``lfx extension dev`` which sets
      LANGFLOW_ENABLE_EXTENSION_RELOAD=true.
    """
    from langflow.api.router import router

    def collect_paths(routes, prefix: str = "") -> list[str]:
        out: list[str] = []
        for route in routes:
            if hasattr(route, "routes"):
                out.extend(collect_paths(route.routes, prefix + getattr(route, "prefix", "")))
            elif hasattr(route, "path"):
                out.append(prefix + route.path)
        return out

    paths = collect_paths(router.routes)
    forbidden = {"install", "uninstall", "registry_add", "registry_remove"}
    violations = [p for p in paths if "/extensions" in p and any(f in p.lower() for f in forbidden)]
    assert not violations, (
        f"Extension router contains forbidden mutation routes: {violations}. "
        "Runtime install/uninstall/registry mutation is not permitted on a live server. "
        "Fix hint — Mode B/C (Docker/self-hosted): rebuild the image with the new package. "
        "Mode A (local dev): use `lfx extension dev` which sets "
        "LANGFLOW_ENABLE_EXTENSION_RELOAD=true."
    )

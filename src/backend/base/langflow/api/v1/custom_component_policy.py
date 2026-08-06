"""Shared catalog and custom-code policy for component source entry points."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from lfx.interface.components import component_cache
from lfx.utils.flow_validation import (
    CatalogPolicyIdentityUnavailableError,
    CatalogPolicyValidationError,
    code_hash_matches_any_template,
    get_component_hash_lookups_for_validation,
    get_trusted_code_for_validation,
    validate_catalog_policy_for_component_code,
    validate_catalog_policy_for_component_type,
)

if TYPE_CHECKING:
    from lfx.services.catalog_policy.base import CatalogPolicySnapshot

    from langflow.services.database.models.user.model import User


_TEMPLATES_INITIALIZING_MESSAGE = "Component templates are still initializing. Please try again in a few seconds."


class CatalogPolicyHTTPException(HTTPException):
    """HTTP denial raised specifically by custom-component catalog policy."""


def resolve_component_code_for_action(
    code: str,
    *,
    user: User,
    settings: object,
    snapshot: CatalogPolicySnapshot,
    disabled_detail: str,
    admin_only_detail: str,
) -> str:
    """Return executable/validated source after applying catalog and custom-code policy.

    Catalog denial is evaluated first and has no superuser bypass. Restricted
    custom-code modes continue to permit known server templates, but callers
    receive the trusted server copy instead of executing client-submitted bytes.
    """
    try:
        validate_catalog_policy_for_component_code(code, snapshot=snapshot)
    except CatalogPolicyValidationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except CatalogPolicyIdentityUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    admin_only = getattr(settings, "custom_component_admin_only", False) is True and not user.is_superuser
    custom_code_disabled = not getattr(settings, "allow_custom_components", True)
    if not custom_code_disabled and not admin_only:
        return code

    get_component_hash_lookups_for_validation()
    all_known = component_cache.all_known_hashes
    if all_known is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_TEMPLATES_INITIALIZING_MESSAGE,
        )

    if not code_hash_matches_any_template(code, all_known):
        detail = disabled_detail if custom_code_disabled else admin_only_detail
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    trusted_code = get_trusted_code_for_validation(code)
    if trusted_code is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=disabled_detail)
    return trusted_code


def enforce_catalog_policy_for_component_type(
    component_type: str,
    *,
    snapshot: CatalogPolicySnapshot,
) -> None:
    """Deny a materialized custom component whose canonical identity is blocked."""
    try:
        validate_catalog_policy_for_component_type(component_type, snapshot=snapshot)
    except CatalogPolicyValidationError as exc:
        raise CatalogPolicyHTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except CatalogPolicyIdentityUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

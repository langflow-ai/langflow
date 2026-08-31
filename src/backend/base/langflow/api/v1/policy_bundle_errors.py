"""Shared HTTP error mapping for policy-bundle-backed administration APIs."""

from fastapi import HTTPException, status

from langflow.services.policy_bundle import PolicyBundleRevisionConflictError


def policy_bundle_revision_conflict(exc: PolicyBundleRevisionConflictError) -> HTTPException:
    """Preserve the structured optimistic-concurrency response across policy APIs."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": "Policy bundle revision conflict",
            "expected_revision": exc.expected_revision,
            "active_revision": exc.active_revision,
        },
    )


__all__ = ["policy_bundle_revision_conflict"]

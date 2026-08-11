"""Schemas for the catalog-policy administration API."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

CATALOG_POLICY_KEY_MAX_LENGTH = 255
CATALOG_POLICY_KEYS_MAX_LENGTH = 1000

CatalogPolicyKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=CATALOG_POLICY_KEY_MAX_LENGTH,
    ),
]
CatalogPolicyKeyList = Annotated[list[CatalogPolicyKey], Field(max_length=CATALOG_POLICY_KEYS_MAX_LENGTH)]


def normalize_catalog_policy_keys(value: list[str]) -> list[str]:
    """Deduplicate validated catalog keys and sort them deterministically."""
    return sorted(set(value))


class CatalogPolicyBlockedSet(BaseModel):
    """A normalized whole-set catalog block policy."""

    blocked: CatalogPolicyKeyList = Field(
        ...,
        description="Complete set of blocked catalog keys for this resource kind.",
    )

    @field_validator("blocked")
    @classmethod
    def normalize_blocked_keys(cls, value: list[str]) -> list[str]:
        """Deduplicate and sort the already-trimmed, validated keys."""
        return normalize_catalog_policy_keys(value)


class CatalogPolicyRead(BaseModel):
    """Current catalog block policy and its ownership source."""

    # Response/history schemas intentionally remain unconstrained so a policy
    # written by an older release can still be read and repaired.
    blocked: list[str]
    managed_externally: bool


__all__ = [
    "CATALOG_POLICY_KEYS_MAX_LENGTH",
    "CATALOG_POLICY_KEY_MAX_LENGTH",
    "CatalogPolicyBlockedSet",
    "CatalogPolicyKey",
    "CatalogPolicyKeyList",
    "CatalogPolicyRead",
    "normalize_catalog_policy_keys",
]

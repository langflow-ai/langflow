"""Schemas for the catalog-policy administration API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CatalogPolicyBlockedSet(BaseModel):
    """A normalized whole-set catalog block policy."""

    blocked: list[str] = Field(
        ...,
        description="Complete set of blocked catalog keys for this resource kind.",
    )

    @field_validator("blocked")
    @classmethod
    def normalize_blocked_keys(cls, value: list[str]) -> list[str]:
        """Trim, reject empty values, deduplicate, and sort deterministically."""
        normalized: set[str] = set()
        for raw_key in value:
            key = raw_key.strip()
            if not key:
                msg = "Blocked catalog keys must not be empty"
                raise ValueError(msg)
            normalized.add(key)
        return sorted(normalized)


class CatalogPolicyRead(CatalogPolicyBlockedSet):
    """Current catalog block policy and its ownership source."""

    managed_externally: bool

"""A permission flow decides whether a tool call proceeds or needs human review."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Permission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["approve", "reject", "ask"] = "ask"
    reason: str = ""


class PermissionFlowError(ValueError):
    """The permission decision failed; the requested tool must not execute."""


class PermissionSourceChangedError(PermissionFlowError):
    """The permission source requires review before a new decision can execute."""

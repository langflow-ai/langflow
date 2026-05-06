"""Installer contract — Protocol + InstallOutcome + InstallStatus.

A small, structural protocol so each per-OS installer can live in its own module
and be selected by the factory without coupling them through inheritance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class InstallStatus(str, Enum):
    """Finite set of install outcomes."""

    SUCCESS = "success"
    DECLINED = "declined"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    ALREADY_INSTALLED = "already_installed"


@dataclass(frozen=True)
class InstallOutcome:
    """Typed result of an install attempt — frozen to prevent downstream mutation."""

    status: InstallStatus
    message: str = ""


# A consent callback is a small function injected by the caller (CLI prompt, UI
# modal). It receives a human-readable description of what is about to happen
# (e.g. the install URL) and returns True iff the user agreed.
ConsentCallback = Callable[[str], bool]


@runtime_checkable
class Installer(Protocol):
    """Structural protocol every per-OS installer must satisfy."""

    def install(self, consent_callback: ConsentCallback) -> InstallOutcome:
        """Attempt to install Ollama. Must NOT execute side effects without consent."""
        ...

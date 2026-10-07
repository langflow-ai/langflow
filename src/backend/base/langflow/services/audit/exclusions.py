"""Which audited actions an operator chose not to record (``LANGFLOW_AUDIT_EXCLUDE_EVENTS``).

An entry names actions the way the ``action`` column stores them: ``flow:write``
for one action, ``flow:*`` for every action on a resource, ``*:delete`` for one
action on every resource. An entry that matches nothing audited is ignored and
reported, never guessed at: a typo must record too much rather than too little,
and a value a newer release understands must not stop an older replica from starting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.audit.vocabulary import ACTIONS_BY_RESOURCE_TYPE
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from collections.abc import Iterable

WILDCARD = "*"
_ENTRY = re.compile(r"^(?P<resource>\*|[a-z][a-z0-9_]*):(?P<action>\*|[a-z][a-z0-9_]*)$")


@dataclass(frozen=True)
class IgnoredExclusion:
    entry: str
    reason: str


@dataclass(frozen=True)
class AuditExclusions:
    actions: frozenset[str]
    ignored: tuple[IgnoredExclusion, ...]


def _audited_actions() -> frozenset[str]:
    return frozenset().union(*ACTIONS_BY_RESOURCE_TYPE.values())


def _resources() -> frozenset[str]:
    return frozenset(resource.value for resource in ACTIONS_BY_RESOURCE_TYPE)


def _match(entry: str) -> frozenset[str]:
    parsed = _ENTRY.fullmatch(entry)
    if parsed is None:
        return frozenset()
    resource, action = parsed["resource"], parsed["action"]
    return frozenset(
        audited
        for audited in _audited_actions()
        if resource in {WILDCARD, audited.split(":", 1)[0]} and action in {WILDCARD, audited.split(":", 1)[1]}
    )


def _suggestion(entry: str) -> str | None:
    """The canonical spelling of a near miss such as ``projects.delete``."""
    resource, separator, action = entry.replace(".", ":").partition(":")
    if not separator:
        return None
    singular = resource[:-1] if resource.endswith("s") and resource[:-1] in _resources() else resource
    candidate = f"{singular}:{action}"
    return candidate if candidate != entry and _match(candidate) else None


def _reason(entry: str) -> str:
    if entry in {WILDCARD, f"{WILDCARD}:{WILDCARD}"}:
        return "it would exclude every audited action; set LANGFLOW_AUDIT_ENABLED=false instead"
    suggestion = _suggestion(entry)
    if suggestion is not None:
        return f"it matches no audited action; did you mean {suggestion!r}?"
    audited = ", ".join(sorted(_audited_actions()))
    return f"it matches no audited action; expected resource:action, resource:* or *:action from: {audited}"


def compile_exclusions(entries: Iterable[str]) -> AuditExclusions:
    actions: set[str] = set()
    ignored: list[IgnoredExclusion] = []
    for raw in entries:
        entry = raw.strip().lower()
        if not entry:
            continue
        matched = frozenset() if entry in {WILDCARD, f"{WILDCARD}:{WILDCARD}"} else _match(entry)
        if matched:
            actions.update(matched)
        else:
            ignored.append(IgnoredExclusion(entry=raw.strip(), reason=_reason(entry)))
    return AuditExclusions(actions=frozenset(actions), ignored=tuple(ignored))


@lru_cache(maxsize=8)
def _compiled(entries: tuple[str, ...]) -> AuditExclusions:
    return compile_exclusions(entries)


def current_exclusions() -> AuditExclusions:
    """Compiled once per distinct setting value, so a change applies without a restart."""
    return _compiled(tuple(get_settings_service().settings.audit_exclude_events))


def is_action_audited(action: str) -> bool:
    return action not in current_exclusions().actions


def ignored_exclusion_warnings() -> list[str]:
    return [
        f"LANGFLOW_AUDIT_EXCLUDE_EVENTS entry {ignored.entry!r} is ignored: {ignored.reason}"
        for ignored in current_exclusions().ignored
    ]


async def warn_about_ignored_exclusions() -> None:
    """Report ignored entries once at startup; a bad list must never stop the server."""
    try:
        if not get_settings_service().settings.audit_enabled:
            return
        for warning in ignored_exclusion_warnings():
            await logger.awarning(warning)
    except Exception as exc:  # noqa: BLE001
        await logger.awarning("op=warn_about_ignored_exclusions outcome=failed error=%s", type(exc).__name__)

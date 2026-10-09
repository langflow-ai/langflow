"""Which knowledge base each legacy ``<folder>/<name>`` directory holds, decided by evidence.

Versions before the SQLite upgrade kept each local base in ``<username>/<name>``, under the username its owner
had when the directory was written. Renaming an account does not move its directories, and another account can
take the name afterwards, so the folder alone does not say whose a directory is. From strongest to weakest:

1. The upgrade ledger's ``source_identity``, recorded when the upgrade first locates or adopts a base's directory.
2. The base id in the ``embedding_metadata.json`` sidecar that versions 1.8 to 1.11 wrote, when that base exists.
3. The folder name, for a base of that name whose owner holds that username now, or held it as the first two
   show for another of their bases.

A directory that the evidence gives to more than one base is contested, and a base with more than one directory
is ambiguous. Callers fail closed on both rather than guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from langflow.services.knowledge_base_storage.legacy_directories import (
    SIDECAR,
    TOMBSTONE,
    is_sqlite_store,
    read_sidecar,
    recorded_id,
)
from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError
from langflow.services.knowledge_base_storage.retained import MIGRATION_DIRECTORY

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping
    from pathlib import Path
    from uuid import UUID

STORE = "chroma.sqlite3"
MISSING = "legacy_source_missing"
AMBIGUOUS = "legacy_source_ambiguous"
_AWAITING_STATES = frozenset({"ready", "migrating", "needs_attention"})
_UNREADABLE = (OSError, RecursionError, TypeError, ValueError)


class LegacySourceUnresolvedError(MaintenanceRequiredError):
    """No single legacy directory can be tied to a base, so its upgrade waits for an administrator."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LegacyDirectory:
    """One ``<folder>/<name>`` directory under the storage root, and what it records about its base."""

    identity: str
    has_store: bool = False
    tombstoned: bool = False
    recorded_id: UUID | None = None
    """The base id its sidecar records."""
    created_at: datetime | None = None
    """When its sidecar says the base was created."""
    readable: bool = True
    """False for a symbolic link, or a directory or sidecar that could not be read."""

    @property
    def folder(self) -> str:
        return self.identity.partition("/")[0]

    @property
    def name(self) -> str:
        return self.identity.partition("/")[2]


@dataclass(frozen=True)
class Account:
    username: str
    joined: datetime | None


@dataclass(frozen=True)
class Base:
    user_id: UUID
    name: str
    recorded: str | None
    """The directory its active ledger run recorded."""
    awaits_source: bool = False
    """A local Chroma base that still reads its legacy directory."""
    holds_data: bool = False
    """Its row counts chunks, so a directory of that name may be its data."""


@dataclass(frozen=True)
class Evidence:
    """What the application database records: accounts, bases, and the directories ledger runs name."""

    accounts: Mapping[UUID, Account]
    bases: Mapping[UUID, Base]
    runs: Mapping[str, frozenset[UUID]]
    """The bases whose ledger runs name each directory, including bases that no longer exist."""


def evidence_from(
    accounts: Iterable[tuple[UUID, str, datetime | None]],
    bases: Iterable[tuple[UUID, UUID, str, UUID | None, str, dict[str, Any], str, int]],
    runs: Iterable[tuple[UUID, UUID, str]],
) -> Evidence:
    """Assemble evidence from the rows of the application database.

    Accounts are ``(id, username, created)``, bases ``(id, owner, name, active run, backend type, backend
    config, storage state, chunks)`` and ledger runs ``(run id, base id, source identity)``.
    """
    identities = {run_id: identity for run_id, _, identity in runs}
    named: dict[str, set[UUID]] = {}
    for _, kb_id, identity in runs:
        named.setdefault(identity, set()).add(kb_id)
    return Evidence(
        accounts={user_id: Account(username, _aware(joined)) for user_id, username, joined in accounts},
        bases={
            kb_id: Base(
                user_id,
                name,
                identities.get(run_id) if run_id else None,
                awaits_source=backend == "chroma"
                and (config or {}).get("mode", "local") == "local"
                and state in _AWAITING_STATES,
                holds_data=bool(chunks),
            )
            for kb_id, user_id, name, run_id, backend, config, state, chunks in bases
        },
        runs={identity: frozenset(kb_ids) for identity, kb_ids in named.items()},
    )


@dataclass(frozen=True)
class Attribution:
    """Every legacy directory, the bases the evidence gives it to, and the folders each account holds or held."""

    directories: Mapping[str, LegacyDirectory]
    claims: Mapping[str, frozenset[UUID]]
    """The bases each directory may hold. More than one makes it contested."""
    folders: Mapping[UUID, frozenset[str]]
    """The folder of each account's username, and of former usernames that the ledger or a sidecar shows."""
    recorded: Mapping[UUID, str]
    """The directory each base's ledger run recorded, while that directory is still there."""
    unreadable_folders: frozenset[str]
    evidence: Evidence

    def source_of(self, kb_id: UUID) -> str:
        """The one directory that holds a base. Raise when there is none, or more than one."""
        if recorded := self.recorded.get(kb_id):
            return recorded
        base = self.evidence.bases.get(kb_id)
        candidates = sorted(
            identity
            for identity, kb_ids in self.claims.items()
            if kb_id in kb_ids and identity in self.directories and not self.directories[identity].tombstoned
        )
        if any(len(self.claims[identity]) > 1 for identity in candidates):
            msg = "Another knowledge base may hold this knowledge base's legacy directory"
            raise LegacySourceUnresolvedError(AMBIGUOUS, msg)
        if len(candidates) > 1 and base is not None:
            # A copy of a directory keeps its sidecar, but not its name.
            named = [identity for identity in candidates if self.directories[identity].name == base.name]
            candidates = named or candidates
        if len(candidates) > 1:
            msg = "More than one legacy directory holds this knowledge base"
            raise LegacySourceUnresolvedError(AMBIGUOUS, msg)
        if candidates:
            return candidates[0]
        if base is not None and self.folder_unreadable(base.user_id):
            msg = "Legacy owner directory is a symbolic link or could not be read"
            raise MaintenanceRequiredError(msg)
        msg = "No legacy directory can be tied to this knowledge base"
        raise LegacySourceUnresolvedError(MISSING, msg)

    def sources_of(self, kb_id: UUID) -> frozenset[str]:
        """The directories that are a base's alone: its recorded one, and those no other base may hold."""
        recorded = {self.recorded[kb_id]} if kb_id in self.recorded else set()
        alone = {identity for identity, kb_ids in self.claims.items() if kb_ids == {kb_id}}
        return frozenset(recorded | (alone & self.directories.keys()))

    def unclaimed(self, user_id: UUID, name: str) -> list[str]:
        """Directories named ``name`` in the account's folders that no single base holds.

        Startup adoption may still register one for the holder of its folder, so the name is not free yet.
        """
        folders = self.folders.get(user_id, frozenset())
        return sorted(
            identity
            for identity, directory in self.directories.items()
            if directory.name == name and directory.folder in folders and len(self.claims.get(identity, ())) != 1
        )

    def folder_unreadable(self, user_id: UUID) -> bool:
        return bool(self.folders.get(user_id, frozenset()) & self.unreadable_folders)

    def holder(self, folder: str) -> UUID | None:
        """The account that holds a folder's name as its username now."""
        accounts = self.evidence.accounts.items()
        return next((user_id for user_id, account in accounts if account.username == folder), None)

    def adoption(self, identity: str, holder_id: UUID | None) -> tuple[UUID, UUID] | str:
        """The account and base id to adopt a directory as, or the inventory issue that prevents it.

        Only the folder name ties an unclaimed directory to an account. Adoption therefore also needs a base id
        in its sidecar, a recorded creation time no earlier than the holder's account, no sign that another
        account held the folder's name, and no base of that name with data that is still missing its
        directory. A sidecar id can be stale, since 1.12 gave the rows of older Memory Bases new ids.
        """
        if holder_id is None:
            return "missing_source_owner"
        directory = self.directories.get(identity)
        if directory is None or not directory.readable:
            return "unreadable_or_ambiguous_legacy_metadata"
        joined = self.evidence.accounts[holder_id].joined
        if directory.recorded_id is None or directory.created_at is None or joined is None:
            return "unattributed_legacy_source"
        held_elsewhere = any(
            directory.folder in folders for user_id, folders in self.folders.items() if user_id != holder_id
        )
        unlocated = _unlocated(self.evidence.bases, self.claims, self.recorded, directory.name)
        if directory.created_at < joined or held_elsewhere or unlocated:
            return "unattributed_legacy_source"
        return holder_id, directory.recorded_id


def attribute(
    directories: Iterable[LegacyDirectory], evidence: Evidence, *, unreadable_folders: frozenset[str] = frozenset()
) -> Attribution:
    """Give each directory to the bases that the ledger, its sidecar or its folder name ties it to."""
    found = {directory.identity: directory for directory in directories}
    recorded = {kb_id: base.recorded for kb_id, base in evidence.bases.items() if base.recorded in found}
    claims: dict[str, set[UUID]] = {identity: set(kb_ids) for identity, kb_ids in evidence.runs.items()}
    for directory in found.values():
        if (kb_id := directory.recorded_id) is not None and kb_id in evidence.bases:
            claims.setdefault(directory.identity, set()).add(kb_id)
    strong = set(claims)
    folders = {user_id: {account.username} for user_id, account in evidence.accounts.items()}
    for identity, kb_ids in claims.items():
        for kb_id in kb_ids:
            base = evidence.bases.get(kb_id)
            if base is not None and base.user_id in folders:
                folders[base.user_id].add(identity.partition("/")[0])
    # Only a base that still reads a legacy directory, and has not recorded which one, matches by name.
    seeking: dict[str, list[tuple[UUID, Base]]] = {}
    for kb_id, base in evidence.bases.items():
        if base.awaits_source and kb_id not in recorded:
            seeking.setdefault(base.name, []).append((kb_id, base))
    by_name = set()
    for identity, directory in found.items():
        if identity in strong or directory.tombstoned:
            continue
        named = {
            kb_id
            for kb_id, base in seeking.get(directory.name, ())
            if directory.folder in folders.get(base.user_id, ())
        }
        if named:
            claims[identity] = named
            by_name.add(identity)
    # A folder name is the weakest evidence. A base of the same name that holds data but found no directory
    # may have written this one under a username it held before, so the directory is contested.
    contested = {identity: _unlocated(evidence.bases, claims, recorded, found[identity].name) for identity in by_name}
    for identity, kb_ids in contested.items():
        claims[identity] |= kb_ids
    return Attribution(
        directories=found,
        claims={identity: frozenset(kb_ids) for identity, kb_ids in claims.items()},
        folders={user_id: frozenset(names) for user_id, names in folders.items()},
        recorded=recorded,
        unreadable_folders=unreadable_folders,
        evidence=evidence,
    )


def _unlocated(
    bases: Mapping[UUID, Base], claims: Mapping[str, Collection[UUID]], recorded: Mapping[UUID, str], name: str
) -> set[UUID]:
    """The bases of this name that hold data and await a legacy directory, but that no directory alone holds."""
    located = {kb_id for kb_ids in claims.values() if len(kb_ids) == 1 for kb_id in kb_ids}
    return {
        kb_id
        for kb_id, base in bases.items()
        if base.name == name
        and base.awaits_source
        and base.holds_data
        and kb_id not in recorded
        and kb_id not in located
    }


def scan_legacy_sources(root: Path) -> tuple[tuple[LegacyDirectory, ...], frozenset[str]]:
    """Every ``<folder>/<name>`` directory under ``root``, and the folders that could not be listed.

    Symbolic links are never followed. A directory or sidecar that cannot be read is reported as unreadable,
    so it never counts as evidence. The internal ``.migration`` folder and the SQLite stores are skipped, but
    a username may start with a dot or be ``sqlite``. A failure to list ``root`` itself is raised.
    """
    if not root.is_dir():
        return (), frozenset()
    directories: list[LegacyDirectory] = []
    unreadable: set[str] = set()
    for folder in sorted(root.iterdir()):
        if folder.name == MIGRATION_DIRECTORY:
            continue
        try:
            if folder.is_symlink():
                unreadable.add(folder.name)
                continue
            if not folder.is_dir():
                continue
            children = sorted(folder.iterdir())
        except OSError:
            unreadable.add(folder.name)
            continue
        for child in children:
            if is_sqlite_store(folder.name, child.name):
                continue
            identity = f"{folder.name}/{child.name}"
            try:
                directory = _survey(identity, child)
            except _UNREADABLE:
                directory = LegacyDirectory(identity, readable=False)
            if directory is not None:
                directories.append(directory)
    return tuple(directories), frozenset(unreadable)


def _survey(identity: str, path: Path) -> LegacyDirectory | None:
    if path.is_symlink():
        return LegacyDirectory(identity, readable=False)
    if not path.is_dir():
        return None
    names = {entry.name for entry in path.iterdir()}
    metadata: dict[str, Any] = read_sidecar(path / SIDECAR) if SIDECAR in names else {}
    return LegacyDirectory(
        identity,
        has_store=STORE in names,
        tombstoned=TOMBSTONE in names,
        recorded_id=recorded_id(metadata),
        created_at=_timestamp(metadata.get("created_at")),
    )


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _aware(datetime.fromisoformat(value))
    except ValueError:
        return None


def _aware(moment: datetime | None) -> datetime | None:
    """Read a naive timestamp, as SQLite returns them, as UTC."""
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=timezone.utc)

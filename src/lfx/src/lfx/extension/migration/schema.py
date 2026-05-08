"""Pydantic models for the append-only migration table.

The migration table maps legacy component references that may appear in saved
flows to the post-Phase-A namespaced ID ``ext:<bundle>:<Class>@<slot>``.  Three
legacy reference shapes are mapped:

    1. ``import_path`` -- the dotted path components used to live at, e.g.
       ``langflow.components.openai.OpenAIEmbeddings``.  Always added when a
       bundle is extracted.
    2. ``legacy_slot`` -- the pre-Phase-A namespaced shape, e.g.
       ``ext:openai:OpenAIEmbeddings@official-pre-a``.  Always added when the
       slot vocabulary changed.
    3. ``bare_class_name`` -- the unqualified class name (``OpenAIEmbeddings``).
       Added only if the class name is globally unique across every Bundle in
       this Langflow release; CI guards this with
       ``scripts/migrate/check_bare_names.py`` (LE-1023).

The table is a single JSON file at a canonical in-repo path.  Every Langflow
release adds entries; **no entry is ever removed**.  CI rejects removals so a
flow saved years ago against a long-extracted bundle still loads.

Why three legacy forms instead of one?

    Saved flows in the wild contain all three depending on when they were
    serialized.  The deserializer probes the table in the order
    (bare_class_name, import_path, legacy_slot) so a single pass rewrites
    every variant; ambiguity on bare names is caught at table-build time
    rather than at load time, but if the table somehow ships an ambiguous
    bare name the deserializer surfaces ``component-name-ambiguous``
    instead of silently picking a winner.

This module is the schema-only layer.  ``loader.py`` reads JSON from disk and
returns one of these models; ``rewrite.py`` consumes the model and walks a
flow payload.  Neither layer talks to the filesystem on its own.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from lfx.extension.manifest import BUNDLE_NAME_RE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIGRATION_SCHEMA_VERSION: int = 1
"""Integer version of the migration-table schema itself.  Bumped only on
breaking shape changes; entry additions never bump this."""

_NAMESPACED_ID_RE: re.Pattern[str] = re.compile(
    r"^ext:(?P<bundle>[a-z][a-z0-9_]{1,63}):(?P<klass>[A-Za-z_][A-Za-z0-9_]*)@(?P<slot>official|extra)$"
)
"""Canonical ``ext:<bundle>:<Class>@<slot>`` shape.

Bundle name uses the same regex as ``BUNDLE_NAME_RE``.  Class name is a
Python identifier.  Slot is one of ``official`` or ``extra`` (matches
``SLOT_VALUES`` in the loader).  Kept independent of the loader so the
schema layer has no runtime dependency on imports / filesystem code.
"""

_IMPORT_PATH_RE: re.Pattern[str] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
"""A valid Python dotted path with at least one dot.

We require the dot so a bare class name cannot be accidentally registered as
an import path (which would defeat ambiguity detection).
"""

_LEGACY_SLOT_RE: re.Pattern[str] = re.compile(r"^ext:[a-z][a-z0-9_]{1,63}:[A-Za-z_][A-Za-z0-9_]*@[a-z][a-z0-9_-]*$")
"""Pre-Phase-A namespaced shape: same skeleton as the canonical form but with
a slot vocabulary that is not yet ``official``/``extra``.  We keep the regex
permissive on the slot segment so historical slot names (``official-pre-a``,
``builtins``, etc.) round-trip without listing each one here."""

_BARE_CLASS_RE: re.Pattern[str] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
"""Bare Python class identifier (``OpenAIEmbeddings``)."""


# ---------------------------------------------------------------------------
# MigrationEntry
# ---------------------------------------------------------------------------


class MigrationEntry(BaseModel):
    """One legacy-reference -> namespaced-ID mapping.

    Exactly one of ``bare_class_name``, ``import_path``, ``legacy_slot`` is
    populated; the other two are ``None``.  This is enforced by the
    ``_exactly_one_legacy_form`` validator below.

    ``added_in`` records the Langflow release that introduced the entry.  It
    is informational at runtime but the CI append-only check (see
    ``scripts/migrate/check_migration_append_only.py``) uses it to attribute
    surprise removals to a specific release window.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    bare_class_name: StrictStr | None = Field(
        default=None,
        description=(
            "Unqualified Python class name (e.g. 'OpenAIEmbeddings'). "
            "Only valid when globally unique across all bundles in this release."
        ),
    )
    import_path: StrictStr | None = Field(
        default=None,
        description=(
            "Dotted Python import path the component lived at, e.g. 'langflow.components.openai.OpenAIEmbeddings'."
        ),
    )
    legacy_slot: StrictStr | None = Field(
        default=None,
        description="Pre-Phase-A namespaced ID, e.g. 'ext:openai:OpenAIEmbeddings@official-pre-a'.",
    )
    target: StrictStr = Field(
        ...,
        description="Canonical post-Phase-A namespaced ID, 'ext:<bundle>:<Class>@<slot>'.",
    )
    added_in: StrictStr = Field(
        ...,
        description="Langflow release that added this entry (informational; CI uses it for removal-attribution).",
    )

    @field_validator("bare_class_name")
    @classmethod
    def _validate_bare(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _BARE_CLASS_RE.fullmatch(value):
            msg = f"bare_class_name must be a Python identifier (got {value!r})"
            raise ValueError(msg)
        return value

    @field_validator("import_path")
    @classmethod
    def _validate_import_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _IMPORT_PATH_RE.fullmatch(value):
            msg = f"import_path must be a dotted Python path with at least one dot (got {value!r})"
            raise ValueError(msg)
        return value

    @field_validator("legacy_slot")
    @classmethod
    def _validate_legacy_slot(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _LEGACY_SLOT_RE.fullmatch(value):
            msg = f"legacy_slot must look like 'ext:<bundle>:<Class>@<slot>' (got {value!r})"
            raise ValueError(msg)
        return value

    @field_validator("target")
    @classmethod
    def _validate_target(cls, value: str) -> str:
        if not _NAMESPACED_ID_RE.fullmatch(value):
            msg = (
                f"target must be a canonical 'ext:<bundle>:<Class>@<slot>' ID "
                f"with slot in {{official,extra}} (got {value!r})"
            )
            raise ValueError(msg)
        # Defense-in-depth: pull the bundle out and re-check it against the
        # bundle-name pattern the manifest layer enforces, so a typo here can
        # never produce a target that the loader would refuse to register.
        match = _NAMESPACED_ID_RE.match(value)
        bundle_name = match.group("bundle") if match else ""
        if not BUNDLE_NAME_RE.fullmatch(bundle_name):
            msg = f"target bundle segment {bundle_name!r} does not match the bundle-name pattern"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _exactly_one_legacy_form(self) -> MigrationEntry:
        populated = [
            name
            for name, value in (
                ("bare_class_name", self.bare_class_name),
                ("import_path", self.import_path),
                ("legacy_slot", self.legacy_slot),
            )
            if value is not None
        ]
        if len(populated) != 1:
            msg = (
                "MigrationEntry must populate exactly one of "
                "{bare_class_name, import_path, legacy_slot}; "
                f"got: {populated or 'none'}"
            )
            raise ValueError(msg)
        return self

    @property
    def legacy_form_kind(self) -> Literal["bare_class_name", "import_path", "legacy_slot"]:
        """Which legacy shape this entry maps from."""
        if self.bare_class_name is not None:
            return "bare_class_name"
        if self.import_path is not None:
            return "import_path"
        return "legacy_slot"

    @property
    def legacy_value(self) -> str:
        """The (single) populated legacy reference string."""
        return self.bare_class_name or self.import_path or self.legacy_slot  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# MigrationTable
# ---------------------------------------------------------------------------


class MigrationTable(BaseModel):
    """The append-only migration table itself.

    Order is preserved as written in the JSON file (the deserializer does not
    care, but the CI append-only check compares the on-disk file against its
    git-history baseline using exact JSON to make removals trivially
    detectable).

    The table enforces two invariants beyond the per-entry ones:

        * No two entries map the same ``(legacy_form_kind, legacy_value)``
          pair.  Two entries with the same bare name pointing at different
          targets is a build-time bug; the deserializer would surface
          ``component-name-ambiguous`` at runtime, but we catch it at
          load-time so the issue lands on the PR that introduced it.
        * Bare-name entries must be globally unique across the table:
          a bare name may only appear once.  Import-path entries and
          legacy-slot entries are unique by construction (they are namespaced).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: StrictInt = Field(
        ...,
        description="Integer version of the migration table schema itself.",
    )
    entries: list[MigrationEntry] = Field(
        default_factory=list,
        description="Append-only list of legacy -> canonical mappings.",
    )

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MIGRATION_SCHEMA_VERSION:
            msg = (
                f"Unsupported migration table schema_version {value}; this Langflow expects {MIGRATION_SCHEMA_VERSION}."
            )
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_uniqueness(self) -> MigrationTable:
        seen: set[tuple[str, str]] = set()
        for entry in self.entries:
            key = (entry.legacy_form_kind, entry.legacy_value)
            if key in seen:
                msg = (
                    f"Duplicate migration entry for {entry.legacy_form_kind}="
                    f"{entry.legacy_value!r}; each legacy reference may appear at "
                    "most once in the table."
                )
                raise ValueError(msg)
            seen.add(key)
        return self

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def lookup_bare(self, name: str) -> MigrationEntry | None:
        """Return the entry whose ``bare_class_name`` equals ``name``."""
        for entry in self.entries:
            if entry.bare_class_name == name:
                return entry
        return None

    def lookup_import_path(self, path: str) -> MigrationEntry | None:
        for entry in self.entries:
            if entry.import_path == path:
                return entry
        return None

    def lookup_legacy_slot(self, slot: str) -> MigrationEntry | None:
        for entry in self.entries:
            if entry.legacy_slot == slot:
                return entry
        return None

    def all_known_legacy_values(self) -> list[str]:
        """Return every legacy value across all entries.

        Used to seed ``difflib.get_close_matches`` for the
        ``component-not-found-with-hint`` suggestion.
        """
        return [e.legacy_value for e in self.entries]

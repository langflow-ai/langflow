"""Pydantic models for the v0 Extension manifest schema (LE-1014).

A Langflow Extension is the distribution unit that gets pip-installed.  In v0
it ships exactly one Bundle (a named group of components) plus a manifest at
the distribution root.  The manifest tells Langflow:

    - which Bundle to register (``bundles[0]``),
    - what component-base-class API surface the Bundle was built against
      (``lfx.compat``),
    - what optional capabilities the Bundle declares
      (``capabilities.requiresCredentials`` is the only v0 slot).

Manifest source forms (both supported):

    1. ``extension.json`` at the package root.
    2. ``[tool.langflow.extension]`` in ``pyproject.toml``.

Use :func:`load_manifest` to discover and parse either form.

Deferred fields (``services``, ``routes``, ``hooks``, ``starter_projects``,
``userConfig``) are reserved here so that downstream tooling can detect their
presence and emit ``field-deferred-in-this-milestone`` rather than silently
dropping them.

Multi-bundle is similarly reserved: ``bundles`` is a list, but v0 rejects
length > 1 with ``multi-bundle-deferred-in-this-milestone``.  This is enforced
in two places (both checked in different tickets):

    - here, by :class:`ExtensionManifest` (validator-side, LE-1014).
    - in the loader (LE-1015) at install/discovery time.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

if sys.version_info >= (3, 11):
    import tomllib  # stdlib on 3.11+
else:
    import tomli as tomllib  # 3.10 fallback (lfx already depends on tomli)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION: int = 1
"""The integer version of the manifest schema.  Bumped only when a v0 manifest
becomes invalid against the new shape."""

EXTENSION_SCHEMA_URL: str = f"https://schemas.langflow.org/extension/v{SCHEMA_VERSION}.json"
"""Canonical hosting URL for the published JSON Schema.  Authors point their
``$schema`` field here for editor autocompletion."""

# Identifier patterns
_EXTENSION_ID_RE: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
"""Extension IDs are lowercase, hyphenated, must start with a letter, 2-64 chars.
Mirrors the npm-package / PyPI normalization rules."""

_BUNDLE_NAME_RE: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
"""Bundle names use snake_case so they can be addressed in the registry as
``ext:<bundle>:<Class>@<slot>`` without quoting."""

_SEMVER_RE: re.Pattern[str] = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:[0-9A-Za-z-]+)(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+(?:[0-9A-Za-z-]+)(?:\.[0-9A-Za-z-]+)*)?$"
)
"""SemVer 2.0.0 pattern (https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string)."""

# Deferred manifest fields.  Validators reject any non-null value with
# ``field-deferred-in-this-milestone``.  Listed here so tests can iterate and so
# the loader (LE-1015) shares the same source of truth.
DEFERRED_FIELDS: tuple[str, ...] = (
    "services",
    "routes",
    "hooks",
    "starter_projects",
    "userConfig",
)


# ---------------------------------------------------------------------------
# LangflowCompat
# ---------------------------------------------------------------------------


class LangflowCompat(BaseModel):
    """Declares which BUNDLE_API.md contract version(s) this Extension supports.

    Each integer in ``bundle_api`` corresponds to a frozen revision of
    BUNDLE_API.md.  Mismatch with the running Langflow surfaces as
    ``version-constraint-unsatisfied`` at install time.

    v0 ships only ``bundle_api=1``; the model is a list to allow future
    forward-compatible declarations like ``[1, 2]``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    bundle_api: list[int] = Field(
        ...,
        description="Supported BUNDLE_API.md major versions.  Must be non-empty.",
        min_length=1,
    )

    @field_validator("bundle_api")
    @classmethod
    def _bundle_api_positive(cls, value: list[int]) -> list[int]:
        for v in value:
            # ``bool`` is a subclass of ``int``; reject it explicitly so a
            # trailing ``[true]`` does not silently parse as ``[1]``.
            if not isinstance(v, int) or isinstance(v, bool):
                msg = "bundle_api entries must be integers"
                raise TypeError(msg)
            if v < 1:
                msg = "bundle_api entries must be >= 1"
                raise ValueError(msg)
        if len(set(value)) != len(value):
            msg = "bundle_api entries must be unique"
            raise ValueError(msg)
        return value


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class Capabilities(BaseModel):
    """Optional capabilities the Bundle declares.

    Phase-1 ships exactly one capability slot (``requiresCredentials``) so the
    shape exists for downstream tickets.  ``extra="forbid"`` ensures additional
    capability keys are rejected with a descriptive error rather than silently
    ignored.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    requiresCredentials: StrictBool = Field(  # noqa: N815 - manifest schema field name
        default=False,
        description=(
            "If true, the loader records that components in this bundle "
            "expect credential variables to be configured before use."
        ),
    )


# ---------------------------------------------------------------------------
# BundleRef
# ---------------------------------------------------------------------------


class BundleRef(BaseModel):
    """Pointer from the manifest to a Bundle directory inside the distribution.

    ``path`` is interpreted relative to the manifest file's parent directory
    and must remain inside it.  Path-safety (no ``..``, absolute paths, or
    symlink escape) is enforced by ``validate_extension`` -- :class:`BundleRef`
    only checks the syntactic shape so the model can be used for static
    analysis without filesystem access.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: StrictStr = Field(
        ...,
        pattern=_BUNDLE_NAME_RE.pattern,
        description=(
            "Bundle name; addressable as ext:<name>:<Class>@<slot>. "
            "Lowercase snake_case, starting with a letter, 2-64 chars."
        ),
    )
    path: StrictStr = Field(
        ...,
        min_length=1,
        description="Path to the bundle directory, relative to the manifest.",
    )

    @field_validator("path")
    @classmethod
    def _validate_path_shape(cls, value: str) -> str:
        if not value:
            msg = "Bundle path must not be empty"
            raise ValueError(msg)
        # Reject absolute paths and parent-directory traversal at the syntactic
        # level.  A more thorough symlink-aware check happens in
        # validate_extension where the filesystem is available.
        if Path(value).is_absolute():
            msg = f"Bundle path {value!r} must be relative to the manifest"
            raise ValueError(msg)
        parts = Path(value).parts
        if any(part == ".." for part in parts):
            msg = f"Bundle path {value!r} must not contain '..'"
            raise ValueError(msg)
        return value


# ---------------------------------------------------------------------------
# ExtensionManifest
# ---------------------------------------------------------------------------


class ExtensionManifest(BaseModel):
    """The v0 Langflow Extension manifest.

    Required fields:
        - id, version, name, bundles, lfx
    Optional:
        - description, capabilities, schema (``$schema``)
    Deferred (rejected with ``field-deferred-in-this-milestone`` when set):
        - services, routes, hooks, starter_projects, userConfig
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        # ``$schema`` is allowed via alias on the dedicated field below.
    )

    schema_field: str | None = Field(
        default=None,
        alias="$schema",
        description="Optional JSON-Schema URL pointer for editor tooling.",
    )

    schema_version: Literal[1] = Field(
        default=1,
        description="Manifest schema major version. v0 fixes this at 1.",
    )

    id: StrictStr = Field(
        ...,
        pattern=_EXTENSION_ID_RE.pattern,
        description=("Globally-unique extension ID. Lowercase, hyphenated, starting with a letter, 2-64 chars."),
    )
    version: StrictStr = Field(
        ...,
        pattern=_SEMVER_RE.pattern,
        description="SemVer 2.0.0 version string for this extension release.",
    )
    name: StrictStr = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable display name shown in Langflow.",
    )
    description: StrictStr | None = Field(
        default=None,
        max_length=2000,
        description="Optional human-readable summary of what the extension provides.",
    )

    lfx: LangflowCompat = Field(
        ...,
        description="Compatibility declaration vs. the BUNDLE_API.md contract.",
    )

    bundles: list[BundleRef] = Field(
        ...,
        min_length=1,
        description="Bundles shipped by this extension. v0 accepts exactly one.",
    )

    capabilities: Capabilities = Field(
        default_factory=Capabilities,
        description="Optional declared capabilities (v0: requiresCredentials only).",
    )

    # ------------------------------------------------------------------
    # Deferred fields.  We model them as ``None``-only so that downstream
    # tooling can distinguish "absent" from "explicitly set to a value the
    # current milestone does not support".  A non-null value triggers a
    # validation error; the validator records the field name so the CLI can
    # emit ``field-deferred-in-this-milestone`` with a precise location.
    # ------------------------------------------------------------------
    services: None = Field(
        default=None,
        description="Reserved; non-component primitives are deferred (B2).",
    )
    routes: None = Field(
        default=None,
        description="Reserved; non-component primitives are deferred (B2).",
    )
    hooks: None = Field(
        default=None,
        description="Reserved; non-component primitives are deferred (B2).",
    )
    starter_projects: None = Field(
        default=None,
        alias="starterProjects",
        description="Reserved; starter-project shipping is deferred.",
    )
    userConfig: None = Field(  # noqa: N815 - manifest schema field name
        default=None,
        description="Reserved; user-config UI is deferred.",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_bundle_count(self) -> ExtensionManifest:
        # Multi-bundle is reserved.  Validator-enforced here so that the schema
        # itself communicates the constraint; the loader (LE-1015) re-checks at
        # install time with the same code.
        if len(self.bundles) > 1:
            msg = "Manifest declares more than one bundle; multi-bundle extensions are deferred in this milestone."
            raise ValueError(msg)
        # Bundle names must be unique even though only one is allowed today --
        # the loader uses this list directly when multi-bundle ships.
        names = [bundle.name for bundle in self.bundles]
        if len(set(names)) != len(names):
            msg = "Bundle names must be unique within an extension"
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# ManifestSource
# ---------------------------------------------------------------------------


class ManifestSource(BaseModel):
    """A parsed manifest paired with its origin path.

    Returned by :func:`load_manifest` so callers can attribute errors back to
    the file the user actually edited (``extension.json`` vs. ``pyproject.toml``).
    """

    model_config = ConfigDict(frozen=True)

    manifest: ExtensionManifest
    path: Path
    """Absolute path to the file the manifest was read from."""
    kind: Literal["extension.json", "pyproject.toml"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _read_extension_json(path: Path) -> dict[str, Any]:
    """Read and parse an ``extension.json`` file.  Raises on failure."""
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"extension.json is not valid JSON ({exc.msg} at line {exc.lineno})"
        raise ValueError(msg) from exc
    if not isinstance(data, dict):
        msg = "extension.json top-level value must be a JSON object"
        raise TypeError(msg)
    return data


def _read_pyproject_extension(path: Path) -> dict[str, Any] | None:
    """Read ``[tool.langflow.extension]`` from a pyproject.toml.

    Returns the table as a dict, or ``None`` if the table is absent.  Raises
    ``ValueError`` if the TOML is malformed or the section is not a table.
    """
    raw = path.read_bytes()
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        msg = f"pyproject.toml is not valid TOML: {exc}"
        raise ValueError(msg) from exc
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    langflow = tool.get("langflow")
    if not isinstance(langflow, dict):
        return None
    section = langflow.get("extension")
    if section is None:
        return None
    if not isinstance(section, dict):
        msg = "[tool.langflow.extension] must be a TOML table"
        raise TypeError(msg)
    return section


def load_manifest(root: Path | str) -> ManifestSource:
    """Discover and parse a v0 manifest at ``root``.

    Discovery order: ``extension.json`` first, then ``[tool.langflow.extension]``
    in ``pyproject.toml``.  Both present is allowed; ``extension.json`` wins, so
    authors who add ``$schema`` to the JSON for editor support do not have to
    duplicate it in pyproject.toml.

    Raises:
        FileNotFoundError: Neither manifest source exists.
        ValueError | TypeError: The manifest source exists but cannot be
            parsed or fails schema validation.  The exception message is
            suitable for direct inclusion in an :class:`ExtensionError`
            ``message`` field.
    """
    root_path = Path(root).resolve()
    if not root_path.exists():
        msg = f"Manifest root {root_path} does not exist"
        raise FileNotFoundError(msg)

    extension_json = root_path / "extension.json"
    pyproject = root_path / "pyproject.toml"

    if extension_json.is_file():
        data = _read_extension_json(extension_json)
        manifest = ExtensionManifest.model_validate(data)
        return ManifestSource(manifest=manifest, path=extension_json, kind="extension.json")

    if pyproject.is_file():
        section = _read_pyproject_extension(pyproject)
        if section is not None:
            manifest = ExtensionManifest.model_validate(section)
            return ManifestSource(manifest=manifest, path=pyproject, kind="pyproject.toml")

    msg = (
        f"No extension manifest found at {root_path}. Expected either "
        f"'extension.json' or a [tool.langflow.extension] section in 'pyproject.toml'."
    )
    raise FileNotFoundError(msg)

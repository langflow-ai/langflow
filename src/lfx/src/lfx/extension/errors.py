"""Typed errors for the Langflow Extension System.

Every error from validate / loader / reload / migration / events surfaces as a
structured object: ``{code, message, hint, ref_url}``, emitted identically by
CLI (stderr + non-zero exit) and HTTP (non-2xx body).  Codes are kebab-case
(``reload-in-progress``, ``template-deferred-in-this-milestone``,
``component-name-ambiguous``).

``format_extension_error`` is the single place that turns one of these into a
human-readable string.  No other code in the extension system formats error
strings -- this keeps snapshot tests stable and gives downstream consumers a
single source of truth for error rendering.

Phase-1 discriminants are enumerated in :data:`ERROR_CODES`.  Adding a new
discriminant means adding a branch to ``format_extension_error`` and a
snapshot test, both checked in the same PR as the producer that emits it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DOCS_BASE = "https://docs.langflow.org/extensions/errors"
"""Base URL for error reference documentation.  Concrete pages are anchors of
the form ``#<error-code>`` (e.g. ``#manifest-invalid``).
"""


# ---------------------------------------------------------------------------
# Error code registry
# ---------------------------------------------------------------------------

# Phase-1 error codes.  Each code shipped here MUST have:
#   1. a branch in ``format_extension_error``,
#   2. a snapshot test in ``tests/unit/extension/test_errors.py``,
#   3. a documented reference URL anchor.
#
# Loader / reload / migration / events codes are added when those subsystems
# land.
ERROR_CODES: frozenset[str] = frozenset(
    {
        # Schema / manifest discovery
        "manifest-not-found",
        "manifest-invalid",
        "manifest-unreadable",
        "field-deferred-in-this-milestone",
        # Deprecated alias of multi-bundle-unsupported; kept for one
        # milestone for log scrapers.
        "multi-bundle-deferred-in-this-milestone",
        "multi-bundle-unsupported",
        "template-deferred-in-this-milestone",
        # Validate-specific codes
        "path-escape",
        "bundle-path-not-found",
        "bundle-empty",
        "syntax-error",
        "no-component-subclass",
        "build-method-missing",
        "import-star-disallowed",
        "top-level-io-disallowed",
        "execute-imports-failed",
        "version-constraint-unsatisfied",
        # Loader-specific codes
        "module-import-failed",
        "duplicate-component-name",
        "duplicate-distribution",
        "duplicate-inline-bundle",
        "inline-bundle-name-invalid",
        "inline-path-missing",
        "inline-path-unreadable",
        "bundle-json-invalid",
        # init / dev CLI codes
        "extension-target-exists",
        "extension-target-invalid",
        "local-extension-missing",
        # Migration-specific codes
        "migration-table-missing",
        "migration-table-unreadable",
        "migration-table-invalid",
        "component-not-found-with-hint",
        "component-name-ambiguous",
        # Production install / discovery
        "installed-extension-immutable",
        "seed-directory-immutable",
        "seed-directory-not-found",
        "seed-bundle-shadowed",
        "bundle-shadowed",
        "duplicate-extension-id",
        # Reload-specific codes
        "reload-in-progress",
        "reload-bundle-not-installed",
        "reload-bundle-name-mismatch",
        "reload-source-missing",
        # Post-swap hook failures: the registry swap committed but a
        # downstream side-effect (e.g. component cache rebuild) raised.
        # Surfaced on ReloadResult.warnings so the API caller knows the
        # palette may be stale even though ok=True.
        "reload-post-swap-hook-failed",
        "reload-class-retag-failed",
        "reload-transport-error",
        "duplicate-bundle-name",
        # HTTP route gate (Mode A only): the runtime guard that hides the
        # reload route on Mode B/C deployments returns this code so the
        # client gets the same typed envelope as every other reload error.
        "extension-reload-disabled",
        # Extension events route: keyspace is server-derived from the
        # authenticated user; clients that pass ``?keyspace=...`` are
        # rejected so the contract is explicit instead of silently dropped.
        "extension-events-keyspace-forbidden",
    }
)


# ---------------------------------------------------------------------------
# ExtensionError
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtensionError:
    """A typed, structured extension-system error.

    Frozen so callers can safely cache and re-emit instances across the
    CLI / HTTP boundary without worrying about mutation.

    Attributes:
        code: Kebab-case discriminant from :data:`ERROR_CODES`.
        message: One-line summary of what went wrong.
        location: Where the error was found (file path, manifest field path,
            or symbolic location like ``"argv"``).  ``None`` if not applicable.
        content: The literal offending content (e.g. the disallowed value or
            symbol name).  ``None`` if the error is purely positional.
        hint: Concrete suggestion for how to fix the problem.  Required for
            every code shipped in Phase 1.
        ref_url: Link to the error reference docs.  Auto-derived from ``code``
            when not provided.
    """

    code: str
    message: str
    hint: str
    location: str | None = None
    content: str | None = None
    ref_url: str | None = None

    def __post_init__(self) -> None:
        if self.code not in ERROR_CODES:
            msg = (
                f"Unknown extension error code: {self.code!r}. "
                f"Add it to lfx.extension.errors.ERROR_CODES and add a "
                f"format_extension_error branch + snapshot test before use."
            )
            raise ValueError(msg)
        if self.ref_url is None:
            object.__setattr__(self, "ref_url", f"{DOCS_BASE}#{self.code}")

    def to_dict(self) -> dict[str, Any]:
        """Serializable representation suitable for HTTP bodies / JSON output."""
        return {
            "code": self.code,
            "message": self.message,
            "location": self.location,
            "content": self.content,
            "hint": self.hint,
            "ref_url": self.ref_url,
        }


# ---------------------------------------------------------------------------
# ExtensionErrorCollection
# ---------------------------------------------------------------------------


@dataclass
class ExtensionErrorCollection:
    """An ordered, append-only collection of errors and warnings.

    ``validate_extension`` produces one of these.  Warnings do not affect the
    exit code; errors do.
    """

    errors: list[ExtensionError] = field(default_factory=list)
    warnings: list[ExtensionError] = field(default_factory=list)

    def add_error(self, error: ExtensionError) -> None:
        self.errors.append(error)

    def add_warning(self, warning: ExtensionError) -> None:
        self.warnings.append(warning)

    @property
    def ok(self) -> bool:
        return not self.errors

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return bool(self.errors) or bool(self.warnings)


# ---------------------------------------------------------------------------
# format_extension_error -- the single renderer
# ---------------------------------------------------------------------------

_BRANCH_TEMPLATES: dict[str, str] = {
    "manifest-not-found": ("No extension.json or [tool.langflow.extension] entry found in {location}."),
    "manifest-invalid": ("Invalid manifest at {location}: {message}"),
    "manifest-unreadable": ("Could not read manifest at {location}: {message}"),
    "field-deferred-in-this-milestone": ("Manifest field {content!r} is deferred in this milestone."),
    "multi-bundle-deferred-in-this-milestone": (
        "Manifest declares more than one bundle entry; multi-bundle extensions are deferred in this milestone."
    ),
    "multi-bundle-unsupported": (
        "Manifest declares more than one bundle entry; v0 supports exactly one bundle per extension."
    ),
    "duplicate-bundle-name": (
        "Bundle name {content!r} is provided by two installed distributions; "
        "the second is dropped to prevent collision."
    ),
    "reload-class-retag-failed": ("Could not retag {content}.__module__ after reload at {location}: {message}"),
    "reload-transport-error": ("Could not reach the reload endpoint at {location}: {message}"),
    "template-deferred-in-this-milestone": ("Template {content!r} is deferred in this milestone."),
    "path-escape": (
        "Path {content!r} escapes the bundle root (..; absolute path; or symlink leaving the bundle directory)."
    ),
    "bundle-path-not-found": ("Bundle path {content!r} (resolved from manifest field {location}) does not exist."),
    "bundle-empty": ("Bundle {content!r} contains no Python source files."),
    "syntax-error": ("Syntax error in {location}: {message}"),
    "no-component-subclass": ("No Component subclass found anywhere in bundle {content!r}."),
    "build-method-missing": ("Component class at {location} does not declare a build() method."),
    "import-star-disallowed": ("Top-level wildcard import in {location}: {content}"),
    "top-level-io-disallowed": (
        "Top-level I/O primitive {content!r} used in {location}; bundle module import must be side-effect free."
    ),
    "execute-imports-failed": ("Subprocess import probe (--execute-imports) failed for {location}: {message}"),
    "version-constraint-unsatisfied": (
        "Manifest at {location} declares lfx.compat={content!r}, which does not "
        "include this lfx package's BUNDLE_API_VERSION; refusing to load."
    ),
    "module-import-failed": ("Failed to import bundle module {location}: {message}"),
    "duplicate-component-name": (
        "Duplicate Component class name {content!r} in bundle {location}; "
        "component class names must be unique within a bundle."
    ),
    "duplicate-distribution": (
        "Two installed distributions share the canonical name {content!r}; "
        "the lexicographically-first manifest path wins. Locations: {location}."
    ),
    "duplicate-inline-bundle": (
        "Inline bundle name {content!r} appears in multiple LANGFLOW_COMPONENTS_PATH entries; "
        "first wins. Locations: {location}."
    ),
    "inline-bundle-name-invalid": (
        "Inline bundle directory {content!r} does not match the bundle name pattern (lowercase snake_case)."
    ),
    "inline-path-missing": (
        "LANGFLOW_COMPONENTS_PATH entry {content!r} does not exist or is not a directory; skipped."
    ),
    "inline-path-unreadable": ("LANGFLOW_COMPONENTS_PATH entry {content!r} could not be enumerated: {message}"),
    "bundle-json-invalid": (
        "Inline bundle.json at {location} is unreadable or malformed; falling back to derived id/version."
    ),
    "extension-target-exists": ("Cannot create extension at {location}: directory already exists and is not empty."),
    "extension-target-invalid": ("Cannot create extension at {location}: {message}"),
    "local-extension-missing": (
        "Registered dev extension at {location} is missing or no longer a directory; skipping until it reappears."
    ),
    "migration-table-missing": ("Migration table not found at {location}."),
    "migration-table-unreadable": ("Could not read migration table at {location}: {message}"),
    "migration-table-invalid": ("Invalid migration table at {location}: {message}"),
    "component-not-found-with-hint": (
        "Legacy component reference {content!r} (in flow node {location}) is not in the migration table."
    ),
    "component-name-ambiguous": (
        "Legacy component reference {content!r} (in flow node {location}) matches more than one migration entry."
    ),
    "installed-extension-immutable": ("Extension {content!r} is installed via pip and cannot be mutated at runtime."),
    "seed-directory-immutable": ("Extension {content!r} comes from a seed directory and cannot be mutated at runtime."),
    "seed-directory-not-found": ("Configured seed directory {location} does not exist or is not a directory."),
    "seed-bundle-shadowed": (
        "Seed-directory bundle {content!r} at {location} is shadowed by an installed Extension "
        "of the same name; the seed copy is being skipped."
    ),
    "bundle-shadowed": (
        "Bundle {content!r} is registered from multiple discovery sources; the lower-precedence copy "
        "at {location} is being skipped in favor of the higher-precedence one."
    ),
    "duplicate-extension-id": ("Extension id {content!r} is registered more than once (already at {location})."),
    "reload-in-progress": (
        "Reload already in progress for bundle {content!r}; refuse to start a second concurrent reload."
    ),
    "reload-bundle-not-installed": (
        "Cannot reload bundle {content!r}: it is not registered. "
        "Install the extension first or pass an explicit source path."
    ),
    "reload-bundle-name-mismatch": (
        "Reload source at {location} declares bundle name {content!r}, "
        "which does not match the registered bundle being reloaded."
    ),
    "reload-source-missing": (
        "Reload source path {content!r} for bundle {location!r} does not exist or is not a directory."
    ),
    "reload-post-swap-hook-failed": (
        "Post-swap hook failed for bundle {content!r}; the bundle swap committed but a "
        "downstream side-effect (e.g. component cache rebuild) raised."
    ),
    "extension-reload-disabled": (
        "Extension reload is disabled on this server.  "
        "Set LANGFLOW_ENABLE_EXTENSION_RELOAD=true to enable it on a local-development install (Mode A)."
    ),
    "extension-events-keyspace-forbidden": (
        "The {location} query parameter is not accepted; events are scoped server-side to the "
        "authenticated user (rejected value: {content!r})."
    ),
}


def format_extension_error(error: ExtensionError) -> str:
    """Render a single :class:`ExtensionError` as plain text.

    Output shape (kept stable for snapshot tests)::

        error[<code>]: <branch-rendered first line>
          location: <location>
          content:  <content>
          hint:     <hint>
          see:      <ref_url>

    Lines without a value are omitted.  ``format_extension_error`` is the only
    place that maps a code to a sentence; other code paths emit
    :class:`ExtensionError` and let this function render.

    Adding a new error code requires:
        1. Adding the code to :data:`ERROR_CODES`.
        2. Adding a branch template here.
        3. Adding a snapshot test.
    """
    if error.code not in ERROR_CODES:
        # Defensive: ExtensionError.__post_init__ already validates, but a caller
        # may construct via ``object.__new__``.  Surface a stable fallback.
        first_line = error.message
    else:
        template = _BRANCH_TEMPLATES.get(error.code)
        if template is None:
            msg = (
                f"format_extension_error: missing branch for code {error.code!r}. "
                f"Every code in ERROR_CODES requires a template."
            )
            raise RuntimeError(msg)
        first_line = template.format(
            location=error.location if error.location is not None else "<unknown>",
            content=error.content if error.content is not None else "",
            message=error.message,
        )

    lines = [f"error[{error.code}]: {first_line}"]
    if error.location:
        lines.append(f"  location: {error.location}")
    if error.content is not None and error.content != "":
        lines.append(f"  content:  {error.content}")
    lines.append(f"  hint:     {error.hint}")
    lines.append(f"  see:      {error.ref_url}")
    return "\n".join(lines)

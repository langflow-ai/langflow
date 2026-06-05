# Bundle API

Stable surface that Langflow Extension Bundles consume.  Every public symbol
listed below is part of the contract: changes to its name, signature, semantics,
or visibility require a coordinated version bump and a `## Changelog` entry.

This document is paired with the integer **`BUNDLE_API_VERSION`** declared in
[`lfx.extension.manifest`](src/lfx/src/lfx/extension/manifest.py).  Manifests
declare the contract versions they support via `lfx.compat: ["1"]`; a bundle
that does not list `str(BUNDLE_API_VERSION)` is rejected at install time with
`version-constraint-unsatisfied`.

> **CI gate:** any PR that modifies a file containing an in-scope surface MUST
> add a `## Changelog` entry describing the change.  The CI guard
> [`scripts/migrate/check_bundle_api_changelog.py`](scripts/migrate/check_bundle_api_changelog.py)
> enforces this.  Pure-internal refactors that preserve every public symbol's
> name and signature do not require a changelog entry, but reviewers should be
> skeptical.

---

## Surface (v0)

### Component base class

| Symbol | Source |
| --- | --- |
| `Component` | `lfx.custom.custom_component.component.Component` |
| `Component.build()` (declared on subclasses) | call site of every loaded bundle module |
| `Component.inputs` | declarative input list |
| `Component.outputs` | declarative output list |
| `Component.display_name` / `Component.description` / `Component.icon` / `Component.documentation` | metadata read by the palette |
| `Component.name` | optional override of the registry class name |

### Inputs

| Symbol | Source |
| --- | --- |
| `Input` (base) | `lfx.io` |
| `MessageTextInput` / `MultilineInput` / `SecretStrInput` | `lfx.io` |
| `IntInput` / `FloatInput` / `BoolInput` | `lfx.io` |
| `DropdownInput` / `TabInput` | `lfx.io` |
| `DictInput` / `NestedDictInput` | `lfx.io` |
| `FileInput` / `LinkInput` | `lfx.io` |
| `HandleInput` | `lfx.io` |

### Outputs

| Symbol | Source |
| --- | --- |
| `Output` | `lfx.io` |

### Schema types

| Symbol | Source |
| --- | --- |
| `Data` | `lfx.schema.data` |
| `DataFrame` | `lfx.schema.dataframe` |
| `Message` | `lfx.schema.message` |

### Manifest contract (consumed by the loader)

| Symbol | Source |
| --- | --- |
| Manifest schema (`extension.json` / `[tool.langflow.extension]`) | `lfx.extension.manifest.ExtensionManifest` |
| `BundleRef` (one entry in `bundles[]`) | `lfx.extension.manifest.BundleRef` |
| `LfxCompat` (declared as `manifest.lfx`) | `lfx.extension.manifest.LfxCompat` |
| `BUNDLE_API_VERSION` (the integer this lfx ships) | `lfx.extension.manifest` |
| `EXTENSION_SCHEMA_URL` / `SCHEMA_VERSION` | `lfx.extension.manifest` |

Slot vocabulary: `official` (installed pip distributions and seed
directories) and `extra` (paths declared in `LANGFLOW_COMPONENTS_PATH`).
Component IDs at runtime are `ext:<bundle>:<Class>@<slot>`.

### Discovery + loading entry points

| Symbol | Source |
| --- | --- |
| `load_extension(root)` | `lfx.extension.loader` |
| `load_installed_extensions()` | `lfx.extension.loader` |
| `discover_inline_bundles()` | `lfx.extension.loader` |
| `discover_installed_extensions()` / `discover_seed_extensions()` / `discover_all_extensions()` | `lfx.extension.discovery` |
| `LoadedComponent` | `lfx.extension.loader` (frozen dataclass; what the registry stores) |
| `LoadResult` | `lfx.extension.loader` |
| `SLOT_OFFICIAL` / `SLOT_EXTRA` | `lfx.extension.loader` |

### Reload pipeline

| Symbol | Source |
| --- | --- |
| `reload_bundle(registry, bundle_name)` | `lfx.extension.reload` |
| `BundleRegistry` | `lfx.extension.bundle_registry` |
| `BundleRecord` | `lfx.extension.bundle_registry` |
| `ReloadInProgressError` | `lfx.extension.bundle_registry` |
| `POST /api/v1/extensions/{id}/bundles/{name}/reload` | `langflow.api.v1.extensions` |

### Errors

| Symbol | Source |
| --- | --- |
| `ExtensionError` | `lfx.extension.errors` |
| `ExtensionErrorCollection` | `lfx.extension.errors` |
| `format_extension_error(error)` | `lfx.extension.errors` |
| `ERROR_CODES` (frozenset of every typed code) | `lfx.extension.errors` |

The full kebab-case discriminant set is the contract — adding a code is
backward-compatible; removing or renaming a code is a breaking change and
requires a `BUNDLE_API_VERSION` bump.

### Validate / authoring CLI

| Symbol | Source |
| --- | --- |
| `validate_extension(root, *, execute_imports=False)` | `lfx.extension.validate` |
| `ValidateReport` | `lfx.extension.validate` |
| `lfx extension validate` (CLI) | `lfx.cli._extension_commands` |
| `lfx extension schema` (CLI) | `lfx.cli._extension_commands` |
| `lfx extension init` (CLI) | `lfx.cli._extension_commands` |
| `lfx extension dev` (CLI -- registers a local path and execs `langflow run`) | `lfx.cli._extension_commands` |
| `lfx extension list` (CLI) | `lfx.cli._extension_commands` |
| `lfx extension reload` (CLI) | `lfx.cli._extension_commands` |
| `register_dev_extension` / `unregister_dev_extension` (Python API) | `lfx.extension.dev_registry` |

### Migration

| Symbol | Source |
| --- | --- |
| Migration-table file | `src/lfx/src/lfx/extension/migration/migration_table.json` |
| `MigrationEntry` | `lfx.extension.migration.schema` |
| `MigrationTable` | `lfx.extension.migration.schema` |
| `migrate_flow_payload(payload, table)` | `lfx.extension.migration.rewrite` |
| `MIGRATION_SCHEMA_VERSION` | `lfx.extension.migration.schema` |

---

## Out of scope (v0)

These are reserved in the manifest schema and produce a typed
`field-deferred-in-this-milestone` error if set; they are NOT part of the
v0 contract:

- `services` — bundle-declared service factories
- `routes` — bundle-mounted HTTP routes
- `hooks` — bundle-declared lifecycle hooks
- `starter_projects` — bundle-shipped starter flows
- `userConfig` — bundle-declared user-config schema
- Multi-bundle manifests (`bundles` list with length > 1)

---

## Pilot bundle: `lfx-duckduckgo`

The shipped LE-1023 pilot is **`duckduckgo`**, extracted into the
standalone distribution
[`lfx-duckduckgo`](src/bundles/duckduckgo/) under `src/bundles/duckduckgo/`
with its own `pyproject.toml`.  `langflow`'s own `pyproject.toml`
declares `lfx-duckduckgo>=0.1.0` as a regular dependency so a flat
`pip install langflow` continues to ship the bundle as before.

Why this bundle:

- Single component (`DuckDuckGoSearchComponent`) in a single file
  (`duck_duck_go_search_run.py`).
- Zero git churn over the last six months.
- Modern `Component` base class (no `LCToolComponent` legacy).
- No authentication required — failure mode is a single failed request, not a
  paid-API outage.
- Class name is globally unique across `src/lfx/src/lfx/components/**`, so the
  bare-name migration entry is allowed by `check_bare_names.py`.

The runtime half of the M1 proof-of-delivery gate (save a flow on
pre-migration Langflow, upgrade, confirm it loads AND runs identically)
lives in the dogfood checklist at
[`src/bundles/duckduckgo/M1_DOGFOOD_CHECKLIST.md`](src/bundles/duckduckgo/M1_DOGFOOD_CHECKLIST.md);
the deserialize half is covered by
`src/lfx/tests/integration/extension/test_pilot_duckduckgo_upgrade.py`.

---

## Changelog

### v0 (this release)

- Initial surface enumerated above.  Frozen as `BUNDLE_API_VERSION = 1`.
- `BundleRegistry.write_locked()` exposed as a public context manager so the
  reload pipeline can hold the registry write lock across both the
  `sys.modules` swap and the `BundleRecord` install.  Concurrent readers
  can no longer observe new modules paired with the old record.  No change
  to the addressable component contract.
- HTTP reload endpoint (`POST /api/v1/extensions/{id}/bundles/{name}/reload`)
  returns `422 Unprocessable Entity` for structural failures (broken
  bundle, missing source path, name mismatch) instead of `200 OK` with
  `ok=false`.  Body is `{...primaryError, result: ReloadResult}` so the
  full typed result is preserved under the FastAPI `detail` envelope.
  `409 Conflict` for `reload-in-progress` is unchanged.
- CLI table updated to remove the obsolete `dev register` / `dev unregister`
  / `dev list` subcommands; the actual surface is `extension dev <path>`
  plus the Python helpers `register_dev_extension` / `unregister_dev_extension`.
- `MigrationTable.ambiguous_bare_names` added.  Each entry is
  `{name, candidates: [list of canonical IDs]}` and registers a bare
  class name that exists in 2+ bundles.  The deserializer now surfaces
  `component-name-ambiguous` (with the candidate targets) for any bare
  name listed here, instead of falling through to the generic
  `component-not-found-with-hint`.  Seeded with the canonical regression
  cases (`MergeDataComponent`, `SplitTextComponent`, `SubFlowComponent`).
  `check_bare_names.py` now verifies every Component class found in
  2+ bundle folders has a matching marker, so a future bundle move that
  introduces a new ambiguity is caught at PR time.
- Router-trust CI guard broadened to scan every `.py` under
  `src/backend/base/langflow/api/**` and `src/lfx/src/lfx/**`; a new file
  that mounts an `APIRouter(prefix=".../extensions...")` is auto-detected
  and checked for forbidden install/uninstall/registry-mutation handlers.
  Authors of files with non-literal prefixes can opt in via a
  `# router-trust: in-scope` marker.
- Router-trust guard rewritten to use AST-based cross-file resolution.
  A forbidden handler in module A is now caught when module B mounts A's
  router via `parent.include_router(child, prefix=".../extensions...")`,
  and the same applies transitively across multi-hop include_router
  chains.  An imported router that cannot be statically resolved is
  ignored (the guard never flags routes it cannot prove reachable from
  `/extensions`); routes co-located with an in-scope router ARE flagged.
- `check_migration_append_only.py` now compares
  `ambiguous_bare_names` alongside `entries`.  A marker may not be
  removed once published, and its `candidates` list may only grow --
  shrinking it would silently regress flows from
  `component-name-ambiguous` to `component-not-found-with-hint`.
- Router-trust guard now resolves dotted attribute references in
  `include_router` and decorators.  ``include_router(child.api.router,
  prefix="/extensions")`` after ``import child.api`` (and the
  ``import child.api as alias; alias.router`` shape) are caught -- not
  just ``from child.api import router as child_router``.  The parser
  flattens any ``Name``/``Attribute`` chain, and the resolver walks
  imports of either kind (``from M import N`` and ``import M``,
  with or without an asname) back to the source file.
- Router-trust guard's relative-import resolver is now
  ``__init__.py``-aware.  Inside a package, ``from .child import Y``
  anchors at the package itself (level=1 -> ``pkg``); inside a regular
  module ``pkg.foo`` it anchors at the parent package (level=1 ->
  ``pkg``).  The arithmetic differs because ``__init__.py``'s file
  module IS the package, while ``pkg/foo.py``'s file module is
  ``pkg.foo``.  The resolver tracks ``is_package`` and decrements
  ``level`` by one for ``__init__.py`` files so both shapes resolve
  correctly.
- Code-review hardening pass across the extension subsystem.  No public
  symbol's name or signature changed; this entry covers behavioural
  tightening that bundle authors and operators should be aware of:
  - **Path-safety contract honored on every discovery path.**
    ``DiscoveredExtension`` records emitted from
    ``discover_installed_extensions`` / ``discover_seed_extensions``
    now run the same resolve-and-``relative_to`` containment check that
    ``validate_extension`` performs.  A symlinked ``bundles[0].path``
    or a symlinked seed subdirectory that escapes the extension root
    is now rejected with ``path-escape`` *before* reaching the loader,
    instead of slipping through to ``exec_module()``.  The shared
    primitive lives at ``lfx.extension._paths.is_within``; every
    walker (loader, validator, seed discovery, inline-bundle discovery)
    uses the same function and the same ``SKIP_DIR_NAMES``.
  - **``--execute-imports`` env allowlist.** The validator's
    ``--execute-imports`` subprocess now inherits an explicit allowlist
    (``PATH``, ``LANG``, ``LC_*``, ``SYSTEMROOT``, ``TMPDIR``, ``TZ``,
    Python locale + encoding vars) instead of denylisting only
    ``LANGFLOW_*``/``LFX_*``.  Cloud / CI credentials
    (``AWS_*``, ``OPENAI_API_KEY``, ``GITHUB_TOKEN``, ...) no longer
    propagate into untrusted bundle import.  The CLI / module docs
    re-frame this pass as best-effort hygiene lint, not a sandbox.
  - **AST hygiene lint widened.** ``_find_top_level_io`` now flags
    ``exec``, ``eval``, ``__import__``, ``compile`` as top-level
    primitives and ``importlib.import_module`` /
    ``importlib.__import__`` as dotted-name primitives.  Still
    best-effort literal-name matching; trivially bypassable by
    obfuscation, and documented as such.
  - **Reload swap is non-destructive.** ``_swap_sys_modules`` now
    builds the staging->prod rename map **before** any ``sys.modules``
    mutation, snapshots popped old modules into a recovery map, and
    restores them on any mid-swap exception.  The length-mismatch
    tripwire on ``zip(strict=True)`` no longer leaves the prod
    namespace shredded.  A new typed code,
    ``reload-class-retag-failed``, is appended to
    ``ReloadResult.warnings`` when ``cls.__module__`` cannot be
    retagged so the empty-palette-after-reload regression leaves a
    trail instead of silently failing.
  - **Cross-source bundle-name collision.**
    ``load_installed_extensions`` now detects two distributions with
    different canonical names but identical ``bundle.name`` (which
    would silently clobber each other at
    ``_lfx_ext.official.<name>.*``) and emits a typed
    ``duplicate-bundle-name`` error on the loser, dropping its
    components.  ``BundleRegistry.install_bundle`` additionally logs a
    WARNING when an existing record is replaced by a record from a
    different ``source_path`` (catches collisions the upstream
    precedence resolver missed).
  - **Reload endpoint off event loop.**
    ``POST /api/v1/extensions/{id}/bundles/{name}/reload`` now invokes
    ``reload_bundle`` via ``asyncio.to_thread`` so slow or large
    bundle imports do not freeze the worker for other in-flight
    requests.  The wire contract (status codes, body shape) is
    unchanged.
  - **Stable typed-error code rename.**
    ``multi-bundle-deferred-in-this-milestone`` is renamed to the
    stable ``multi-bundle-unsupported``.  The old code is retained in
    ``ERROR_CODES`` as a deprecated alias for one milestone for log
    scrapers.  Three new codes are added to
    ``ERROR_CODES``: ``duplicate-bundle-name`` (see above),
    ``reload-class-retag-failed`` (see above), and
    ``reload-transport-error`` (CLI-side connectivity failure,
    previously misreported as ``reload-source-missing``).
  - **Discovery preserves "unreadable" vs "absent" distinction.**
    ``_pyproject_declares_extension`` now propagates ``OSError`` so a
    permission failure on a pyproject that *might* declare an
    extension surfaces as ``manifest-unreadable`` instead of being
    silently dropped as "no extension here".
  - **Dev registry corruption is logged.** ``_read_state`` now
    distinguishes file absent (silent, legitimate empty registry),
    file present but unreadable (WARNING), and file present but
    corrupt JSON / wrong shape (WARNING with detail).  The state
    file is written with mode 0600 so a hostile third-party process
    cannot inject an extension path into the developer's next
    ``langflow run``.
  - **Entry-point predicate avoids module-level side effects.**
    ``_entry_point_loads_to_component`` now consults
    ``importlib.util.find_spec`` first and only falls through to
    ``ep.load()`` when the spec lookup is insufficient.  The
    ``except BaseException`` was narrowed to ``except Exception`` so
    ``SystemExit`` / ``KeyboardInterrupt`` are no longer swallowed at
    filter time.
  - **Frontend reload-success warnings surfaced.**  The reload route's
    ``ReloadResult.warnings`` (non-empty on success) now reach the
    user via a notice toast in addition to the green success toast.
    Wire shape unchanged; this is a UI fix that consumes existing
    payload fields.
  - **Internal-only file split.** ``sys.modules`` surgery primitives
    moved to ``lfx.extension.reload_swap``; ``load_installed_extensions``
    / ``load_seed_extensions`` moved to
    ``lfx.extension.loader._startup``.  Both are re-exported from
    their previous import paths so external imports are unchanged.
  - **Editable installs are discovered via the entry-point fallback.**
    ``_distribution_manifest_path`` now falls back to the
    ``langflow.extensions`` entry-point group when ``dist.files`` only
    surfaces ``dist-info/`` entries (the ``pip install -e`` /
    ``uv pip install -e`` case).  The entry-point value is resolved
    via ``importlib.util.find_spec`` -- which runs import-system
    finders but never executes the module body -- and the resulting
    package directory is scanned for ``extension.json`` or a
    ``[tool.langflow.extension]`` pyproject.  Wheel installs are
    unaffected: the fallback only fires when the primary ``dist.files``
    scan finds no manifest.  Previously, editable-installed bundles
    were silently dropped by ``lfx extension list`` and the registry,
    even though the bundle pyproject already declared the
    entry-point.
  - **Reload CLI: ``--bundle`` is optional; ``--all`` is implemented.**
    ``lfx extension reload <ext_id>`` now resolves the bundle name
    from local ``discover_all_extensions`` when ``--bundle`` is
    omitted; explicit ``--bundle`` still wins for cases where the
    local install is not visible to the running server.
    ``lfx extension reload --all`` iterates every locally-discovered
    bundle, POSTs reload to each, and exits non-zero if any reload
    fails (previously hard-errored as "not yet wired").  ``--all`` is
    mutually exclusive with a positional id / ``--bundle`` (exit 2).
    The HTTP wire contract (``POST /api/v1/extensions/{id}/bundles/
    {name}/reload`` per-bundle) is unchanged; this is a CLI-only
    surface change.
- **User-scoped extension events.**  Bundle lifecycle events
  (``bundle_reloaded``, ``bundle_reload_failed``, ``flow_migrated``,
  ``extension_error``) now publish to a per-user keyspace
  (``user:<user_id>``) instead of the shared ``"global"`` bucket so
  flow-migration and reload payloads cannot leak across users via the
  poll endpoint.
  - ``reload_bundle`` gains an optional keyword-only ``user_id: str |
    None = None`` argument.  When supplied, ``bundle_reloaded`` /
    ``bundle_reload_failed`` events are emitted to keyspace
    ``user:<user_id>``; ``None`` (CLI / authless dev) keeps the legacy
    ``"global"`` emission.  Existing positional callers are unaffected.
  - ``POST /api/v1/extensions/{id}/bundles/{name}/reload`` now resolves
    the authenticated user and threads its id into ``reload_bundle``, so
    every reload triggered via HTTP is published to that user's
    keyspace.  Wire contract (status codes, body shape) unchanged.
  - ``GET /api/v1/extensions/events`` drops its client-supplied
    ``keyspace`` query parameter.  The endpoint derives the keyspace
    from the authenticated user server-side, so an authenticated client
    can no longer poll another user's keyspace.  Frontends that polled
    without ``keyspace`` (the in-tree consumer) are unaffected;
    third-party callers that explicitly passed ``keyspace=...`` will
    now receive ``422`` from FastAPI's strict parameter validation.
- **Reload event payload aligned with ``ReloadResult``.**  Both
  ``bundle_reloaded`` and ``bundle_reload_failed`` events now carry the
  full ``ReloadResult.to_dict()`` envelope (``ok``, ``bundle``,
  ``reload_id``, ``components_added``, ``components_removed``,
  ``components_changed``, ``warnings``, ``errors``) instead of a
  hand-rolled subset.  Polling clients can now (a) detect body-only
  edits via ``components_changed`` instead of mis-reporting them as
  "no source changes detected", and (b) surface a failed reload's
  ``errors[0].message`` instead of degrading to a generic
  "check server logs" fallback.  HTTP response shape unchanged.
- **``GET /api/v1/extensions/events`` rejects ``keyspace`` explicitly.**
  Previously the endpoint accepted but silently ignored any
  client-supplied ``keyspace`` query parameter (server-derived from the
  authenticated user since the prior entry).  Silent drop masked client
  bugs that assumed the value had effect.  The route now returns ``422
  Unprocessable Entity`` with a typed
  ``extension-events-keyspace-forbidden`` error envelope when the
  parameter is present.  ``extension-events-keyspace-forbidden`` is
  added to ``ERROR_CODES`` (additive; codes-as-contract semantics
  preserved).  In-tree polling clients that never sent the parameter
  are unaffected.

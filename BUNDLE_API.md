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
| `lfx extension dev register` / `unregister` / `list` (CLI) | `lfx.cli._extension_commands` |
| `lfx extension list` (CLI) | `lfx.cli._extension_commands` |
| `lfx extension reload` (CLI) | `lfx.cli._extension_commands` |

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

## Pilot recommendation

For LE-1023 (B1 pilot migration), the recommended target is
**`duckduckgo`**.  Rationale:

- Single component (`DuckDuckGoSearchComponent`) in a single file
  (`duck_duck_go_search_run.py`).
- Zero git churn over the last six months.
- Modern `Component` base class (no `LCToolComponent` legacy).
- No authentication required — failure mode is a single failed request, not a
  paid-API outage.
- Class name is globally unique across `src/lfx/src/lfx/components/**`, so the
  bare-name migration entry is allowed by `check_bare_names.py`.

This is a recommendation, not a decision — the engineer who picks up B1 owns
the call.

---

## Changelog

### v0 (this release)

- Initial surface enumerated above.  Frozen as `BUNDLE_API_VERSION = 1`.

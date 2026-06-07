# Bundle localization (i18n)

How component translations work for bundles, and how a bundle can ship its own.

## Background: what gets translated

Langflow translates **component metadata** — `display_name`, `description`, and
input/output `display_name` / `info` / `placeholder` — into the 7 supported
locales (en, de, es, fr, ja, pt, zh-Hans). At runtime the `/api/v1/all` endpoint
reads the `Accept-Language` header and substitutes translated strings via
`langflow.utils.i18n`. The lookup is keyed by a content-hashed key:

```
components.<norm_name>.<field_path>.<sha256(english)[:8]>
```

If a key is absent for the requested locale, translation falls back to English —
so **an untranslated component always renders correctly in English**, never an
error. Localization is therefore always optional.

This is distinct from the **frontend** locales (`src/frontend/src/locales/`),
which cover app chrome (buttons, dialogs) only and are unaffected by bundles.

## First-party bundles (in this monorepo): centralized

Components under `src/bundles/` are translated through the **central** pipeline,
exactly like in-tree components. `scripts/gp/extract_backend_strings.py` walks
`lfx.components` **and every bundle** under `src/bundles/` (see
`_iter_component_packages`), writing all strings to
`src/backend/base/langflow/locales/en.json`. That file is uploaded to the
translation service and the per-language files are downloaded back.

Consequences for bundle authors in this repo:

- **Do nothing special.** Add your component; its strings land in `en.json` on
  the next regeneration and get translated centrally.
- **Do not** add a `locales/` directory to an in-repo bundle — its strings are
  already in the central files; a per-bundle copy would duplicate them.
- CI (`gp-backend-check.yml`, triggered on `src/bundles/**`) regenerates
  `en.json` and runs `scripts/gp/check_locale_alignment.py` as a backstop
  against mass orphan regressions.

> Historical note: before the extractor walked `src/bundles/`, extracting a
> component silently dropped its strings from `en.json`, orphaning ~30k existing
> translations. The bundle walk + the alignment check exist to prevent that.

## Third-party / installed bundles: ship your own `locales/`

An externally distributed bundle (pip-installed, not in this repo) cannot put its
strings in Langflow's central files. Such a bundle ships its **own** translations:

1. Add a `locales/` directory beside your `extension.json`, with one JSON file
   per locale (`en.json`, `de.json`, ...) using the key scheme above. Use
   `langflow.utils.i18n_keys.component_field_key` / `normalize_component_key` to
   generate keys so they match what the runtime looks up.
2. Declare it in the manifest (optional; `locales/` is the conventional default):
   ```json
   { "...": "...", "locales": "locales" }
   ```
3. Include the directory in your wheel, e.g. (hatchling):
   ```toml
   [tool.hatch.build.targets.wheel]
   include = ["src/lfx_<name>/extension.json", "src/lfx_<name>/locales/*.json", "..."]
   ```

At load time `langflow.utils.i18n._load_translations` discovers each installed
extension's `locales/` directory (via the `langflow.extensions` entry-point group
and the manifest `locales` field) and merges it into the i18n table with
**core-wins** precedence — a bundle can add translations for its own components
but can never shadow a first-party string. Discovery is fully defensive: any
failure degrades to the core locale files.

Translating those strings is the third-party author's responsibility (ship
pre-translated files, or run your own translation pipeline) — Langflow's central
GP pipeline only sees the core `en.json`.

## Deferred tooling (not yet built)

First-party bundles intentionally stay centralized, so the following are
deferred until there is a need to relocate first-party strings out of the
central files:

- `scripts/migrate/port_bundle.py --move-locales` — relocate a component's keys
  from the central locale files into a bundle's `locales/` on extraction.
- A GP "aggregate-then-split" mode that round-trips per-bundle `en.json` files
  through the translation service and writes results back per bundle.

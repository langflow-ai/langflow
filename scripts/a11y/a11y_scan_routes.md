# Langflow Accessibility Scan Route Manifest

The canonical route list lives in:

```text
scripts/a11y/a11y_routes.json
```

Do not maintain route targets in this Markdown file. Add, remove, or edit scan
targets in the JSON manifest so the Python scanner, Playwright a11y spec, and
HTML report all use the same source.

## Manifest Sections

- `static`: default authenticated route surfaces for routine scans and CI.
- `dynamic`: distinct route surfaces that require real IDs before scanning.
- `gated`: real routes that need a specific auth, role, or environment state.
- `excluded`: redirects, aliases, or same-component surfaces excluded from the
  default batch.

## Python Scanner

Use the manifest directly:

```bash
uv run python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --routes-file scripts/a11y/a11y_routes.json \
  --route-group static \
  --out /tmp/langflow-a11y-static-canonical.json \
  --markdown /tmp/langflow-a11y-static-canonical.md \
  --html /tmp/langflow-a11y-static-canonical.html \
  --timeout-ms 45000
```

Explicit `--route` or `--routes` arguments still work and override the manifest.

### State files

Reusable `--states-file` manifests live in `scripts/a11y/states/`. Commit new state
files there instead of ad-hoc `/tmp` paths so post-interaction states (open modals,
scrolled grids) stay rerunnable. `settings-messages.json` covers the AG-Grid
scroll states on `/settings/messages` that a default-load scan cannot see.

A state can name the DOM it depends on with `"requires": "<selector>"`; when that
element is absent (the grid never renders against a backend with no messages) the
state is reported as skipped instead of failing the scan. Any other action failure is
recorded per state as `failed` and the run continues, so one broken state cannot
cost the other routes' findings.

### Policies

`--policies` selects the IBM guideline set the engine evaluates against and defaults
to `IBM_Accessibility`, matching `policies` in `src/frontend/.achecker.yml` so the
Python scanner and the Playwright suite report the same rules.

Passing `--policies ""` runs unfiltered. That also surfaces rules belonging to no
guideline at all (`"rulesets": []` in the report, e.g. `element_scrollable_tabbable`),
which the IBM browser extension hides and which are **not** compliance findings.
Every issue in the report carries its `rulesets` so a non-policy rule is easy to spot.

`--ace-url` defaults to the engine version pinned in `a11y_scan.py`, kept in sync with
the `accessibility-checker` dependency and `ruleArchive` used by the Playwright suite.

## Playwright CI

`src/frontend/tests/a11y/static-routes.a11y.spec.ts` reads the same manifest and
scans every entry in `static`. The route `id` becomes the IBM report label:

```text
route-settings-api-keys
```

`src/frontend/tests/utils/build-a11y-html-report.mjs` also reads the manifest to
map report labels back to route paths and surface names.

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

## Playwright CI

`src/frontend/tests/a11y/static-routes.a11y.spec.ts` reads the same manifest and
scans every entry in `static`. The route `id` becomes the IBM report label:

```text
route-settings-api-keys
```

`src/frontend/tests/utils/build-a11y-html-report.mjs` also reads the manifest to
map report labels back to route paths and surface names.

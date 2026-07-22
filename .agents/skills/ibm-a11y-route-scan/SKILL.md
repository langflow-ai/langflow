---
name: ibm-a11y-route-scan
description: Batch-scan Langflow frontend routes for accessibility issues using the Python IBM Equal Access scanner (scripts/a11y/a11y_scan.py) and produce JSON/Markdown/HTML reports. Scans the default-loaded state of each route only (use explicit state files for modals). Use when asked to scan one or more routes, produce an accessibility report for pages, or batch-check static routes. Reports findings only — does not fix code, run Playwright/axe tests, or perform a formal Level 1 audit; see ibm-a11y-testing-guide, ibm-a11y-level1-audit, and ibm-a11y-pr-remediation for those.
---

# IBM Route Scanner

Use this skill when asked to scan Langflow frontend pages for accessibility issues with the local Python scanner. This skill only reports — it does not modify code. For test-writing guidance, formal audits, or PR-wide fixes, see `ibm-a11y-testing-guide`, `ibm-a11y-level1-audit`, and `ibm-a11y-pr-remediation`.

## Scanner

Use the Python script:

```bash
uv run python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --routes-file scripts/a11y/a11y_routes.json \
  --route-group static \
  --out /tmp/langflow-a11y-report.json \
  --markdown /tmp/langflow-a11y-report.md \
  --html /tmp/langflow-a11y-report.html \
  --timeout-ms 45000
```

Script options:

- `--url`: base app URL, usually `http://localhost:3000`.
- `--routes-file`: route manifest JSON file. Prefer `scripts/a11y/a11y_routes.json`.
- `--route-group`: manifest group to scan. Default: `static`.
- `--routes`: comma-separated route paths to scan.
- `--route`: one route path; can be repeated instead of `--routes`.
- `--levels`: comma-separated issue levels. Default: `violation`.
- `--out`: JSON report path.
- `--markdown`: optional Markdown report path.
- `--html`: optional self-contained HTML report path.
- `--timeout-ms`: per-route timeout.
- `--quiet-ms`: network quiet window before scanning. Default: `1000`.
- `--states-file`: JSON file with explicit modal/state actions.
- `--headed`: show browser while scanning.

## Route Selection

Use `scripts/a11y/a11y_routes.json` as the source of truth for route selection.

The normal CI/local batch is the manifest `static` group. Prefer that unless the user asks for custom, dynamic, or gated routes.

Common manifest-backed command:

```bash
uv run python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --routes-file scripts/a11y/a11y_routes.json \
  --route-group static \
  --out /tmp/langflow-a11y-static.json \
  --markdown /tmp/langflow-a11y-static.md \
  --html /tmp/langflow-a11y-static.html
```

Dynamic routes need real IDs before scanning:

- `/flow/:id/`
- `/flow/:id/view`
- `/playground/:id/`
- `/assets/knowledge-bases/:sourceId/chunks`

For dynamic routes, get IDs from the loaded app, API responses, or existing test data before replacing placeholders.

## Examples

Scan one route:

```bash
uv run python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --route /flows \
  --out /tmp/langflow-a11y-flows.json
```

Scan multiple routes:

```bash
uv run python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --routes-file scripts/a11y/a11y_routes.json \
  --route-group static \
  --out /tmp/langflow-a11y-report.json \
  --markdown /tmp/langflow-a11y-report.md \
  --html /tmp/langflow-a11y-report.html
```

Scan more than violations:

```bash
uv run python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --routes-file scripts/a11y/a11y_routes.json \
  --route-group static \
  --levels violation,potentialviolation,recommendation \
  --out /tmp/langflow-a11y-expanded.json
```

Scan route plus modal states:

```bash
uv run python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --states-file /tmp/langflow-a11y-states.json \
  --out /tmp/langflow-a11y-modal-report.json \
  --markdown /tmp/langflow-a11y-modal-report.md \
  --html /tmp/langflow-a11y-modal-report.html \
  --timeout-ms 45000
```

State file shape:

```json
[
  {
    "route": "/settings/global-variables",
    "states": [
      {
        "name": "new-global-variable-modal",
        "open": [
          { "click": "[data-testid='api-key-button-store']" },
          { "waitFor": "[role='dialog']" }
        ],
        "close": [
          { "press": "Escape" },
          { "waitForHidden": "[role='dialog']" }
        ]
      }
    ]
  }
]
```

Supported state actions:

- `{ "click": "<css selector>" }`
- `{ "clickText": "<visible text>" }`
- `{ "clickRole": { "role": "button", "name": "Create" } }`
- `{ "fill": { "selector": "<css selector>", "value": "text" } }`
- `{ "press": "Escape" }`
- `{ "press": { "selector": "<css selector>", "key": "Enter" } }`
- `{ "waitFor": "<css selector>" }`
- `{ "waitForHidden": "<css selector>" }`
- `{ "waitForText": "<visible text>" }`
- `{ "wait": 500 }`

## Report

The scanner always writes JSON. It can also write Markdown and HTML for presentation.

Use JSON for exact data. Use Markdown for PR comments or issues. Use HTML when the user wants a browsable report.

Summarize:

- report path
- Markdown/HTML report paths, when generated
- total issue count
- per-route issue count
- per-route API request count
- per-route request failure count
- top rule IDs

Use report fields directly:

- `totalIssues`
- `results[].route`
- `results[].state`
- `results[].phase`
- `results[].apiRequests`
- `results[].requestFailures`
- `results[].diagnostics`
- `results[].issues[].ruleId`

## Rules

- Use only scanner output for findings.
- Do not invent route names. Read `routes.tsx`.
- Do not auto-click arbitrary buttons to find modals. Use explicit state actions.
- Avoid destructive modal actions unless the user explicitly asks and data is safe.
- If a route has zero API requests, mention that scan quality may be limited.
- This skill reports only; do not edit files. If the user also wants fixes applied, hand off to `ibm-a11y-pr-remediation` or `ibm-a11y-level1-audit`.

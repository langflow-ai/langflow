# Accessibility test coverage

Langflow has two a11y scan layers:

- **Playwright specs** in this directory are regression hosts. GitHub Actions runs
  every spec that calls `page.runA11yScan(...)` in `.github/workflows/a11y-scan.yml`.
- **`scripts/a11y/a11y_scan.py`** is the ad-hoc route/report tool. Use it when you need a
  Markdown or HTML report for a custom route batch, modal state, or local triage.

## IBM Level 1 compliance docs

| File | Purpose |
|---|---|
| [`ibm-a11y-level1-criteria.md`](ibm-a11y-level1-criteria.md) | Reference guide — IBM Equal Access Toolkit v7.3 Level 1 criteria (WCAG 2.2 A & AA). Read this to understand what each checkbox in the tracker means. |
| [`ibm-a11y-level1-tracker.md`](ibm-a11y-level1-tracker.md) | **Validation tracker** — one checkbox per reusable component (Section A) and per route shell (Section B). Tick a box only when the item has been validated for IBM Level 1. |

The tracker is a **manual checklist** that complements the automated Playwright scans; it does
not replace them. `[x]` means no blocking issue was found during a static code audit
(2026-07-01 baseline). Open `> Gap:` notes are items still needing a fix; `> Note:` items need
a human visual/screen-reader confirmation pass.

## Static route coverage

`static-routes.a11y.spec.ts` mirrors the canonical static route list in
`scripts/a11y/a11y_routes.json`. Add a route there with a stable `ready` check so CI
fails if the route redirects or stops rendering.

Use one scan per distinct page surface. Do not add redirect aliases, folder
filters, or routes that render the same component with only different data.

## Stateful coverage

Use focused specs for states that require UI actions, like the flow canvas,
configuration panels, auth validation, toasts, dialogs, and playground. Keep
those out of `static-routes.a11y.spec.ts`; static routes should stay cheap and
predictable.

## Local commands

```bash
cd src/frontend
RUN_A11Y=true npx playwright test tests/a11y/static-routes.a11y.spec.ts --project=chromium --workers=1
RUN_A11Y=true npx playwright test tests/a11y --project=chromium --workers=1
npm run a11y:html-report --silent
```

The HTML report is written to:

```text
coverage/accessibility-reports/index.html
```

It groups issues by route, then rule, and includes the IBM message, target,
DOM path, ARIA path, element bounds, snippet, and IBM rule link.

To assert against checker baselines:

```bash
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y --project=chromium --workers=1
```

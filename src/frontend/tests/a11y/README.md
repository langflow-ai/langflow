# Accessibility test coverage

Langflow has two a11y scan layers:

- **Playwright specs** in this directory are regression hosts. GitHub Actions
  runs every spec that calls `page.runA11yScan(...)` in
  `.github/workflows/a11y-scan.yml` (it discovers scan hosts with
  `grep -rl "runA11yScan("`, so a new spec is picked up automatically).
- **`scripts/a11y/a11y_scan.py`** is the ad-hoc route/report tool. Use it when you
  need a Markdown or HTML report for a custom route batch, modal state, or local
  triage. See the [`ibm-a11y-automation`](../../../../.agents/skills/ibm-a11y-automation/SKILL.md)
  skill for how to drive it.

## IBM Level 1 compliance docs

| File | Purpose |
|---|---|
| [`ibm-a11y-level1-criteria.md`](ibm-a11y-level1-criteria.md) | Reference guide — IBM Equal Access Toolkit v7.3 Level 1 criteria (WCAG 2.2 A & AA). Read this to understand what each rule the scanner flags means and how to fix it. |
| [`ibm-a11y-level1-tracker.md`](ibm-a11y-level1-tracker.md) | **Route validation tracker** — one checkbox per route surface (static / dynamic / gated). Tick a box only after that route has been scanned and confirmed to pass IBM Level 1. |

The tracker is a **manual checklist** that complements the automated Playwright
scans; it does not replace them. `- [ ]` means the route has not yet been
validated; `- [x]` means it has been scanned and confirmed clean (or its
remaining findings are documented, framework-owned suppressions). Add a short
note under a route when its findings are intentionally suppressed so the next
person knows why.

## Workflow: add a11y coverage for a feature or route

Follow these steps whenever you add or update accessibility coverage for a page,
feature, or flow. This is the loop the specs in this directory were built with.

1. **Create a spec file to scan the feature or path.**
   Pick a route surface from
   [`ibm-a11y-level1-tracker.md`](ibm-a11y-level1-tracker.md) (or add one if it is
   missing) and create `tests/a11y/<feature>.a11y.spec.ts`. Model it on the
   existing specs:
   - [`knowledge-bases.a11y.spec.ts`](knowledge-bases.a11y.spec.ts) — a feature
     with many states, modals, drawers, and a `helpers/*.fixtures.ts` file.
   - [`auth-pages.a11y.spec.ts`](auth-pages.a11y.spec.ts) — gated routes with
     validation, error toasts, and light/dark scans.
   - [`core-pages.a11y.spec.ts`](core-pages.a11y.spec.ts) — a serial journey
     across the flow canvas, config panel, and playground.
   - [`static-routes.a11y.spec.ts`](static-routes.a11y.spec.ts) — the manifest-driven
     scan of every plain static route.

   Import `test`/`expect` from `../fixtures` (never `@playwright/test`), tag every
   test `@release` (plus domain tags), and call `page.runA11yScan("<label>")` once
   per distinct UI surface. See the
   [`a11y-spec-authoring`](../../../../.agents/skills/a11y-spec-authoring/SKILL.md)
   skill for the full authoring guide and a starter template.

2. **Validate that all routes and actions are captured in the scan.**
   A single page load is not enough — the scanner only sees the DOM that is
   present when `runA11yScan` runs. Enumerate and scan every reachable state:
   - **Every route/surface** for the feature (list, detail, empty, loading,
     error, no-results).
   - **Opened modals, drawers, dropdowns, and popovers** — scan while they are
     open, before closing them.
   - **Clicked buttons and menus** that reveal new UI (row-action menus, bulk
     actions, confirmation dialogs).
   - **Revealed / conditionally-rendered fields** — expand advanced sections,
     add-metadata rows, per-item editors, and validation error messages so
     hidden inputs are actually in the DOM during the scan.
   - **Both color schemes** where relevant (`runA11yScan(label, { colorScheme: "dark" })`).

   Use `data-testid`-based `expect(...).toBeVisible()` gates before each scan so
   you are certain the target state has rendered, and `settleNetwork(page)` to let
   async content land.

3. **Run the a11y scan to show IBM accessibility findings.**
   Scans only execute when `RUN_A11Y=true`; without it `runA11yScan` is a no-op.

   ```bash
   cd src/frontend
   RUN_A11Y=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=1
   npm run a11y:html-report --silent
   ```

   The HTML report is written to `coverage/accessibility-reports/index.html`. It
   groups issues by route, then rule, and includes the IBM message, target, DOM
   path, ARIA path, element bounds, snippet, and IBM rule link. To fail the run on
   any new violation (what CI does on `workflow_dispatch` with `assert`):

   ```bash
   RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=1
   ```

4. **Fix the issues associated with the scan.**
   For each violation, fix the application code (semantic HTML, labels, roles,
   focus management, contrast, etc.) rather than the test. Re-run step 3 until the
   scan is clean.
   - If a violation is genuinely owned by shared app chrome or a third-party
     widget (Radix, AG Grid, cmdk) and is not fixable from the feature's markup,
     add its rule ID to the spec's `ignoreRules` array **with a comment** that
     explains, per the report DOM, exactly why it is suppressed. See the
     `KB_IGNORE_RULES` block in
     [`knowledge-bases.a11y.spec.ts`](knowledge-bases.a11y.spec.ts) for the
     expected level of justification.
   - Real, tracked gaps that must be fixed elsewhere (e.g. theme-level contrast)
     should stay called out in the comment, not silently ignored.

5. **Use the criteria guide for reference.**
   Map each flagged rule back to a WCAG/IBM success criterion using
   [`ibm-a11y-level1-criteria.md`](ibm-a11y-level1-criteria.md) — it lists the
   Level 1 requirements, the "Common Failures to Avoid" table, and concrete
   HTML/ARIA/focus patterns to apply. When the route is clean (or its findings are
   documented suppressions), tick its box in
   [`ibm-a11y-level1-tracker.md`](ibm-a11y-level1-tracker.md).

## Static route coverage

`static-routes.a11y.spec.ts` mirrors the canonical static route list in
`scripts/a11y/a11y_routes.json`. Add a route there with a stable `ready` check so
CI fails if the route redirects or stops rendering.

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

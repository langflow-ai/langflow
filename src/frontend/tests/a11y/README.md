# Accessibility (a11y) testing

Welcome! This directory is home to Langflow's accessibility coverage. Everything
here is measured against **IBM Equal Access Toolkit v7.3, Level 1** (WCAG 2.2
Level A & AA). The goal is simple: every page and interaction we ship should work
for people using keyboards, screen readers, and other assistive technology.

If you're here to add coverage for a feature, jump to
[the workflow](#workflow-add-a11y-coverage-for-a-feature-or-route). If you just
want to run a scan, see [Quick start](#quick-start).

## How scanning works

We scan in two complementary ways:

| Layer | What it is | When to reach for it |
|---|---|---|
| **Playwright specs** (this directory) | Regression hosts. Any spec that calls `page.runA11yScan(...)` runs in CI via `.github/workflows/a11y-scan.yml` — the workflow auto-discovers scan hosts with `grep -rl "runA11yScan("`, so a new spec is picked up without any workflow edits. | Permanent, repeatable coverage for a route or feature. |
| **`scripts/a11y/a11y_scan.py`** | An ad-hoc route/report tool that produces Markdown or HTML reports. | One-off triage of a custom route batch or modal state. See the [`ibm-a11y-automation`](../../../../.agents/skills/ibm-a11y-automation/SKILL.md) skill. |

## Reference docs

Two companion documents live alongside these tests:

| Document | What it's for |
|---|---|
| [`ibm-a11y-level1-criteria.md`](ibm-a11y-level1-criteria.md) | The engineering guide to IBM Level 1 criteria — read it to understand what a flagged rule means and how to fix it (includes a "Common Failures to Avoid" table and ready-to-use HTML/ARIA/focus patterns). |
| [`ibm-a11y-level1-tracker.md`](ibm-a11y-level1-tracker.md) | A manual checklist with one checkbox per route surface (static / dynamic / gated). |

The tracker **complements** the automated scans — it doesn't replace them. Read
the boxes like this:

- `- [ ]` — not yet validated.
- `- [x]` — scanned and confirmed clean (or its remaining findings are
  documented, framework-owned suppressions).

When you suppress a finding intentionally, leave a short note under that route so
the next person understands why.

## Quick start

```bash
cd src/frontend

# Scan one spec and open a browsable report
RUN_A11Y=true npx playwright test tests/a11y/static-routes.a11y.spec.ts --project=chromium --workers=1
npm run a11y:html-report --silent        # → coverage/accessibility-reports/index.html

# Scan everything
RUN_A11Y=true npx playwright test tests/a11y --project=chromium --workers=1

# Fail the run on any new violation (what CI does with the `assert` input)
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y --project=chromium --workers=1
```

> Scans only run when `RUN_A11Y=true`. Without it, `runA11yScan(...)` is a no-op,
> so a11y specs can live cheaply next to behavior specs.

The HTML report at `coverage/accessibility-reports/index.html` groups issues by
route, then rule, and includes the IBM message, target, DOM path, ARIA path,
element bounds, snippet, and a link to the IBM rule.

## Workflow: add a11y coverage for a feature or route

This is the loop every spec in this directory was built with. At a glance:

| Step | Goal |
|---|---|
| 1. Create the spec | Add `tests/a11y/<feature>.a11y.spec.ts` for the route/feature. |
| 2. Capture every state | Scan each route, modal, menu, and hidden field — not just the first paint. |
| 3. Run the scan | Execute with `RUN_A11Y=true` and read the HTML report. |
| 4. Fix the findings | Correct the app code; suppress only framework-owned rules, with a reason. |
| 5. Confirm against the criteria | Map each rule to a criterion, then tick the tracker box. |

### 1. Create a spec file for the feature or path

Pick a route surface from
[`ibm-a11y-level1-tracker.md`](ibm-a11y-level1-tracker.md) (or add one if it's
missing) and create `tests/a11y/<feature>.a11y.spec.ts`. The existing specs are
good starting points, each showing a different shape of coverage:

- [`knowledge-bases.a11y.spec.ts`](knowledge-bases.a11y.spec.ts) — a rich feature
  with many states, modals, drawers, and a `helpers/*.fixtures.ts` file.
- [`auth-pages.a11y.spec.ts`](auth-pages.a11y.spec.ts) — gated routes with
  validation, error toasts, and light/dark scans.
- [`core-pages.a11y.spec.ts`](core-pages.a11y.spec.ts) — a serial journey across
  the flow canvas, config panel, and playground.
- [`static-routes.a11y.spec.ts`](static-routes.a11y.spec.ts) — the manifest-driven
  scan of every plain static route.

A few essentials: import `test`/`expect` from `../fixtures` (never
`@playwright/test`), tag every test `@release` (plus any domain tags), and call
`page.runA11yScan("<label>")` once per distinct UI surface. The
[`a11y-spec-authoring`](../../../../.agents/skills/a11y-spec-authoring/SKILL.md)
skill has the full authoring guide and a starter template.

### 2. Capture every route and action in the scan

This is the part that's easy to under-do. The scanner only sees the DOM present
**at the moment `runA11yScan` runs**, so a single page load misses most of the
feature. Walk through and scan every reachable state:

- **Every route/surface** — list, detail, empty, loading, error, no-results.
- **Overlays while they're open** — dialogs, drawers, dropdowns, popovers. Scan
  before you close them.
- **Buttons and menus that reveal new UI** — row-action menus, bulk actions,
  confirmation dialogs, multi-step wizards (scan each step).
- **Conditionally rendered / hidden fields** — expand advanced sections, add
  metadata rows, open per-item editors, and trigger validation so hidden inputs
  and error text are actually in the DOM.
- **Both color schemes**, where the feature themes differently:
  `runA11yScan(label, { colorScheme: "dark" })`.

Gate each scan on a `data-testid`-based `expect(...).toBeVisible()` so you know
the target state has rendered, and use `settleNetwork(page)` to let async content
land first.

### 3. Run the scan

```bash
cd src/frontend
RUN_A11Y=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=1
npm run a11y:html-report --silent
```

Open `coverage/accessibility-reports/index.html` to review the findings. To fail
the run on any new violation (the behavior CI uses on `workflow_dispatch` with
`assert`):

```bash
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=1
```

### 4. Fix the findings

For each violation, fix the **application code** — semantic HTML, labels, roles,
focus management, contrast, and so on — rather than adjusting the test. Re-run
step 3 until the scan is clean.

Sometimes a finding is genuinely owned by shared app chrome or a third-party
widget (Radix, AG Grid, cmdk) and can't be fixed from the feature's markup. Those
suppressions are **feature-specific**. Knowledge Bases centralizes its own in
[`knowledge-bases-ignore-rules.json`](knowledge-bases-ignore-rules.json) — one
`{ "ruleId", "reason" }` entry per rule:

- `knowledge-bases.a11y.spec.ts` imports it to build `KB_IGNORE_RULES` for every
  `runA11yScan(...)` call (only relevant under `RUN_A11Y_ASSERT=true`).
- `build-a11y-html-report.mjs` reads the same file and **greys these findings out
  on KB-labeled routes only** — other feature scans are unaffected and show all
  their findings as actionable. The report then shows *actionable* vs *suppressed*
  counts; focus on the actionable numbers.

Other feature specs should create their own `<feature>-ignore-rules.json` if they
need to suppress framework-owned rules. Keep real tracked gaps (for example,
theme-level `text_contrast_sufficient`) in the list with a reason — they stay
visible as suppressed for tracking, never silently dropped.

> The scan itself dismisses open overlays (it injects the IBM ACE engine, which
> closes Radix menus/dropdowns/popovers). To scan a state and then interact with
> it, re-open the overlay resiliently — see the
> [`a11y-spec-authoring`](../../../../.agents/skills/a11y-spec-authoring/SKILL.md)
> skill for the pattern.

### 5. Confirm against the criteria

Map each flagged rule back to a WCAG/IBM success criterion using
[`ibm-a11y-level1-criteria.md`](ibm-a11y-level1-criteria.md). Once the route
scans clean (or its remaining findings are documented suppressions), tick its box
in [`ibm-a11y-level1-tracker.md`](ibm-a11y-level1-tracker.md).

## Choosing where a scan belongs

**Static routes → `static-routes.a11y.spec.ts`.** This spec mirrors the canonical
route list in `scripts/a11y/a11y_routes.json`. Add a route there with a stable
`ready` check so CI fails if the route redirects or stops rendering. Use one scan
per distinct page surface — don't add redirect aliases, folder filters, or routes
that render the same component with only different data.

**Anything stateful → a focused spec.** States that need UI actions (the flow
canvas, configuration panels, auth validation, toasts, dialogs, playground)
belong in their own spec. Keep them out of `static-routes.a11y.spec.ts` so static
routes stay cheap and predictable.

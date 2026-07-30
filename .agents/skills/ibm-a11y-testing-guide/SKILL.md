---
name: ibm-a11y-testing-guide
description: Reference guide for writing and running Langflow frontend accessibility tests with axe (Jest) and IBM Equal Access (Playwright `page.runA11yScan`). Covers which engine/test layer to pick, the POUR checklist, axe-vs-IBM rule gaps, Radix/AG-Grid component gotchas, and IBM baselines. Use when writing or reviewing a11y tests, debugging a specific axe/IBM violation, or deciding which test layer fits a UI surface. Does not run scans, audit a whole surface, or fix a PR end-to-end — see ibm-a11y-route-scan, ibm-a11y-level1-audit, and ibm-a11y-pr-remediation for those.
---

# IBM/axe Accessibility Testing Guide

Reference material for **how** to test a given UI surface. This skill does not decide what to scan or drive a fix loop by itself — use it while writing tests, debugging a violation, or implementing a fix identified by `ibm-a11y-route-scan`, `ibm-a11y-level1-audit`, or `ibm-a11y-pr-remediation`.

## When To Use

Use this skill for frontend work under `src/frontend` when the change affects:

- UI components, primitives, pages, routes, dialogs, drawers, popovers, dropdowns, tabs, accordions, tables, forms, navigation, or canvas controls.
- ARIA attributes, labels, roles, focus management, tab order, keyboard interaction, disabled states, loading states, or error states.
- A request to write, fix, or review an axe/IBM accessibility test.

Use alongside:

- `frontend-testing` for Jest/React Testing Library patterns.
- `e2e-testing` for Playwright patterns.
- `frontend-i18n` when adding or changing user-facing labels, accessible names, `aria-label`, tooltips, or visible strings.
- `ibm-a11y-route-scan` to batch-scan routes with the Python scanner and produce Markdown/HTML reports.
- `ibm-a11y-level1-audit` for a scoped IBM Level 1 compliance audit and report.
- `ibm-a11y-pr-remediation` to scan and fix an entire PR/branch end-to-end.

## Goal

Do not stop at "run axe on default render." Inspect the changed UI and cover every meaningful user-visible state, for both keyboard and screen-reader users, that can expose accessibility bugs.

## The Bar: two engines, both must pass

Automated a11y is not one tool. Run BOTH — they catch different classes of bug:

- **axe-core** — Jest `axe()` (`@/utils/a11y-test`), jsdom-only. Fast; strong on contrast, labels, roles, ARIA basics.
- **IBM Equal Access** — the stricter engine on ARIA structure and keyboard semantics; catches real WCAG Level-1 issues axe silently passes. Two entry points, **same engine** (`aChecker`):
  - Playwright **`page.runA11yScan(label)`** — runs `aChecker.getCompliance` in-browser on the **live DOM**, so it scans open modals / menus / selected / editing states. This is IBM, **not** axe (despite the name).
  - `scripts/a11y/a11y_scan.py` (see `ibm-a11y-route-scan`) — route scanner for the default-loaded page only.

A page that is green on axe is NOT done. When the change touches a table/tree/listbox/menu/composite widget, IBM is mandatory. Prefer `page.runA11yScan` for stateful surfaces (it sees the DOM after your interactions); use the Python scanner for a quick default-load route check.

Verify commands:

```bash
cd src/frontend
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=5

# The Python scanner's playwright deps are NOT in the default `uv sync`.
# One-time: `uv run --with playwright playwright install chromium`
uv run --with playwright python scripts/a11y/a11y_scan.py \
  --url http://localhost:3000 \
  --routes /settings/<route> \
  --out /tmp/a11y.json --markdown /tmp/a11y.md --timeout-ms 45000
```

`RUN_A11Y=true` runs the scan; add `RUN_A11Y_ASSERT=true` to actually fail on new violations (without it the scan is informational). Both engines must report zero. After changing a shared component, re-scan every page that uses it, not just the one you touched.

## First Pass

1. Read the changed files and nearby tests.
2. Identify the UI surface:
   - Primitive/component only
   - Composed component
   - Page/route
   - Stateful workflow
   - Shared helper that changes labels, roles, tab order, or focus behavior
3. List interactive surfaces:
   - Buttons, links, inputs, checkboxes, switches, radios, selects, comboboxes
   - Dropdown menus, popovers, dialogs, drawers, tooltips
   - Tabs, accordions, tables/treegrids, row actions, pagination
   - Keyboard-only interactions and focus traps
4. List states worth scanning:
   - Default, populated, empty, loading, error/validation visible
   - Disabled/read-only, selected/expanded/open
   - Modal/dropdown/popover open
   - Mobile viewport when layout changes

## What To Check (POUR checklist)

### Perceivable
- Non-text content has a text alternative; decorative images are hidden from AT.
- Text contrast ≥ 4.5:1; non-text (icons, borders, focus rings) ≥ 3:1.
- Layout reflows at 320px / 400% zoom without horizontal scroll or loss of content.

### Operable (keyboard is the big one)
- Every control is reachable AND operable by keyboard (Enter/Space activate; arrows where expected).
- Focus is always visible.
- Focus order is logical and matches visual order.
- **No keyboard trap — test Shift+Tab too, not just Tab.** Focus can always move out of a widget both ways.
- Disabled controls are not in the tab order.
- Composite widgets (grid/tree/listbox/menu/tablist) are ONE logical tab stop with a roving `tabindex`; arrows move within.
- After async transitions (route change, panel open/close) focus lands somewhere useful, never silently on `<body>`.

### Understandable
- Inputs have programmatic labels; visible label matches accessible name.
- Errors are identified in text and associated with their field; give a suggestion when possible.
- The same control is identified consistently across the app.

### Robust (name / role / value)
- Interactive elements expose a correct role, name, and state.
- Valid ARIA parent/child (e.g. `rowgroup` owns `row`, `list` owns `listitem`).
- No tabbable element with a non-widget role (`presentation`/`none`).
- `aria-hidden="true"` never wraps a focusable element.

## axe vs IBM: known gaps

Things axe passes but IBM flags (all real WCAG Level 1):

| IBM rule | WCAG | Typical cause |
| --- | --- | --- |
| `element_tabbable_role_valid` | 4.1.2 | tabbable element with `role="presentation"` / no widget role (focus sentinels, wrappers) |
| `aria_child_valid` | 1.3.1 | `rowgroup`/`list`/`tablist` owning no valid child role |
| `aria_child_tabbable` | 2.1.1 / 4.1.2 | composite widget with no tabbable descendant (needs roving `tabindex`) |
| `aria_hidden_focus_misuse` | 4.1.2 | focusable element inside `aria-hidden="true"` |
| `aria_accessiblename_exists` | 4.1.2 | element with a widget role but no accessible name — e.g. an AG Grid `columnheader` with neither `field` nor `headerName` (icon-only action column) |
| `aria_content_in_landmark` | 1.3.1 | content outside any landmark — e.g. a Radix menu/popover portaled to `<body>`. `role="menu"` is NOT landmark-exempt; only `aria-modal` dialogs are. Often unfixable app-wide → baseline it (see below) |

Rule of thumb: touch a table/tree/listbox/menu → scan with IBM.

## Component Gotchas

- **Data grids (AG Grid — the shared `TableComponent`)**: the grid's own tab guards + pagination are the fragile part.
  - Disabled paging buttons must be `tabindex="-1"`, but NEVER `inert`/`disabled` — that breaks AG Grid's tab guards and traps reverse (Shift+Tab) entry (WCAG 2.1.2).
  - AG Grid still *programmatically* focuses disabled paging on tab-out; handle with its `tabToNextCell` hook plus a container-scoped `focusin` redirect (defer the redirect to `requestAnimationFrame` — focus changes inside a `focusin` handler are ignored, and AG Grid restores the last-focused cell on the next tick).
  - Empty rowgroups need `role="presentation"`; the grid needs one roving-tabindex row.
  - **Icon-only / action column header**: AG Grid derives the `columnheader` accessible name from `field`; a column with neither `field` nor `headerName` is nameless (`aria_accessiblename_exists`, 4.1.2). Give it a `headerName` and hide it visually with a `headerClass` (sr-only clip on `.ag-header-cell-text`) so the header stays blank but named.
  - **Interactive control inside a cell** (menu trigger, button): AG Grid navigates **cell-by-cell** and never tab-focuses the inner control, so it's keyboard-inoperable. Activate it from the grid's `onCellKeyDown` on Enter/Space (give the column a `colId` to target it). A **Radix trigger opens on keydown/pointerdown, not a synthetic `.click()`** — focus the trigger and **re-dispatch the key** (`new KeyboardEvent("keydown", {key, bubbles:true})`), guarding against re-entry (skip when `target` is already the button). `TableComponent` spreads `{...props}` to AG Grid, so pass `onCellKeyDown` from the page — no shared-component change.
  - **Focus visible on borderless grids** (`.ag-no-border`): the theme suppresses the cell focus outline (`outline:none`), hiding keyboard focus (2.4.7). Restore it with a `:focus-visible` ring scoped to `.ag-no-border .ag-cell:focus-visible` (+ header/row). `:focus-visible` **distinguishes modality on AG cells** — mouse click resolves to `:focus`, keyboard nav to `:focus-visible` — so the ring shows for keyboard only and mouse stays quiet. CAVEAT when verifying: probe with a **clean, first-interaction** page; a session that already used the keyboard makes `:focus-visible` report `true` for a later mouse click (heuristic contamination).
  - Set `ensureDomOrder: true` so DOM order matches visual order for tab navigation.
  - `TableComponent` is shared across settings/traces — fix once in the grid patch, then re-scan every grid page. Its pagination/tab-out rework lives in LE-1720 / PR #13953; don't duplicate it per-page.
- **Modals/drawers**: title + description, focus trapped inside while open, focus restored to the trigger on close, Escape closes.
- **Dropdowns/popovers**: reachable by keyboard, Escape closes, focus returns to the trigger.
- **Radix (shadcn) primitives** — three recurring traps:
  - **`Trigger asChild` double tab stop**: a `DialogTrigger`/`DropdownMenuTrigger` wrapping a real `<button>` **without `asChild`** makes Radix render its *own* `<button>` around it → nested buttons → two consecutive tab stops (2.4.3). Always pass `asChild` when the child is already an interactive element. (Watch the trigger wrapper's own `asChild={cond}` default — `DeleteConfirmationModal` needs an explicit `asChild`.)
  - **Focus-restore race**: on close, Radix restores focus to its trigger **once, asynchronously**. If the menu action programmatically moves focus elsewhere (e.g. `startEditingCell` opens an inline editor), Radix steals it back. Re-assert focus on your target across a few `requestAnimationFrame`s to outlast the one-time restore. For rename-style flows, `.select()` the input too.
  - **Portaled menu landmark**: `DropdownMenu`/`Popover` content portals to `<body>`, tripping `aria_content_in_landmark`. Portaling into `<main>` is not an option when `<main>` is `overflow-hidden` (clips the menu). Treat as app-wide debt → **baseline it** (below); the menu's real a11y (role, named trigger, keyboard open/close, focus restore) is covered by a keyboard test instead.
- **Disabled controls**: keep them out of the tab order. Only use `aria-disabled` (instead of native `disabled`) when the control must stay discoverable, and keep it non-operable.
- **Icon-only buttons**: real `<button>` with an `aria-label`.
- **Custom clickable divs/cells**: prefer a semantic element; if a cell/card must open something it needs Enter/Space handling, not just `onClick`.

## Best practices (settings grids + modals)

Apply these when building or reviewing AG Grid tables that open an edit modal (reference: `GlobalVariablesPage`, `tests/a11y/global-variables.a11y.spec.ts`):

- **Keyboard map on selectable rows:** **Space** toggles the row checkbox; **Enter** opens the row’s edit/detail UI. Do not use Space to open the modal.
- **Scope the map on the page:** implement with page-level `onCellKeyDown` and per-column `suppressKeyboardEvent` for Enter/Space so AG Grid’s default Space handling does not compete. Prefer not changing shared `TableComponent` defaults unless the same map is product-wide.
- **Keep selection UI in sync:** after `node.setSelected`, update React selection state so toolbar actions (e.g. delete) enable/disable correctly (`TableOptions.hasSelection` is read at render time).
- **Retain place on modal close (2.4.3):** remember the focused cell (`rowIndex` + `colId`) when opening edit; on close (Escape, Cancel, or save) restore with `api.setFocusedCell` + DOM `.focus()`, using a few `requestAnimationFrame`s to outlast Radix dialog cleanup. Controlled edit dialogs without a Radix trigger need this explicitly. Create flows that use a real `DialogTrigger` (e.g. Add New) should restore to that trigger.
- **Verify with keyboard tests:** open from a cell → Escape → focus is still on that cell; Enter can open again without a mouse re-click.

## Choose Test Layer

### Jest + axe

Use Jest when the changed surface is a primitive or component that renders in jsdom without full app routing.

```tsx
import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";

it("should_have_no_axe_violations", async () => {
  const { container } = render(<Component />);
  expect(await axe(container)).toHaveNoViolations();
});
```

Notes: `a11y-test.ts` disables `color-contrast` (jsdom can't measure layout). Prefer role/label/text queries. Assert accessible names explicitly for icon-only / visually-hidden / generated labels. Put tests at `__tests__/<name>.a11y.test.tsx`.

```bash
cd src/frontend
npx jest path/to/<name>.a11y.test.tsx --runInBand
```

### Playwright + `page.runA11yScan`

Use Playwright when the surface needs real browser layout, routing, app state, mocking, modals, tables, focus order, keyboard behavior, or full-page interactions.

```ts
import { expect, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";

test("scans populated state", { tag: ["@release", "@api"] }, async ({ page }) => {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/example");
  await expect(page.getByText("Example")).toBeVisible();
  await page.runA11yScan("settings-example-populated");
});
```

Rules: put specs under `tests/a11y/<feature>.a11y.spec.ts`; import `test`/`expect` from `../fixtures`; tag every test `@release` plus a domain tag (`@workspace`/`@api`/`@database`/`@components`/`@starter-projects`); stable scan names (lowercase, feature-first, state-specific); mock API for deterministic states; disable animations for focus assertions; use explicit interactions (no random clicking of destructive controls). If the route belongs in static coverage, update `scripts/a11y/a11y_routes.json`.

```bash
cd src/frontend
RUN_A11Y=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=5
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=5
npm run a11y:html-report --silent
```

## IBM baselines (accepting known debt)

Some IBM violations are real but framework-level and can't be fixed per-page (e.g. `aria_content_in_landmark` on a Radix menu portal). Track them with an IBM baseline so the scan stays green while the debt is recorded — do NOT silently drop the scan or the assertion.

How it works (`fixtures.ts` + `.achecker.yml`):

- `baselineFolder: tests/a11y/baselines`. The baseline file name is the **scan label**: `{project}__{label}.json`, e.g. `chromium__assets-files-actions-menu.json` (dashes preserved; the first scan in a test has no index suffix).
- On each run IBM's `filterReport` loads that file and marks any result matching a baseline entry by **`path.dom` + `ruleId` + `reasonId`** as `ignored: true`. `countNewA11yViolations` counts `violation && !ignored`, so baselined issues don't fail.

Create one:

1. Run the scan once — it writes the full report to `coverage/accessibility-reports/{label}.json`.
2. Copy the offending result(s) into `tests/a11y/baselines/{label}.json` as `{ "results": [ { "ruleId", "reasonId", "path": { "dom": … } } ] }`. A **minimal** baseline (only the entries to ignore) is clearest; add a `description` field noting why and how to resurface it.
3. Re-run → the scan passes. Commit the baseline so the debt is tracked; **deleting it resurfaces the violation**. Point at the baseline from a comment in the spec.

Matching is exact-DOM-path, so baselines can go stale if unrelated `<body>`-level portals (toasts) shift the portal index — scan the state with no other overlays open.

## Route/Page Coverage Matrix

For route/page changes, cover the smallest matrix representing real user states:

- Loaded/default, empty data, populated data
- Primary modal open, dropdown/popover open
- Validation or error visible
- Selected/expanded table row or bulk-action state
- Mobile viewport when responsive layout changes

Don't force states the page can't enter; briefly explain any skipped state.

## Data-Rich Route Pattern

Use `tests/a11y/api-keys.a11y.spec.ts` and `tests/a11y/files.a11y.spec.ts` as the models for route-level work: mock API data; scan populated table; scan empty table; open create modal and scan; submit to the generated-result modal and scan; open a text-cell modal and scan; select a row and scan the selected state; set a mobile viewport and scan. Add keyboard-interaction tests (not scans) for tab-out, reverse re-entry, Enter-to-open, focus restore, and focus-visible where the surface has custom keyboard behavior. This is the expected bar for data-rich routes.

**Driving grid row states**: client-rendered states (upload progress %, upload-failed/error, disabled rows) are usually driven by fields the cell renderer reads off the row (`params.data.*`). If the list query returns the response untransformed, just inject the field into the mocked rows (e.g. `{ ...file, progress: -1 }`) to scan the error/progress state — no need to simulate the real flow.

## Report Back

When done, state:

- Test files added or updated, and states scanned.
- Commands run — including whether BOTH axe and IBM were run and both reported zero.
- Any states not covered and why.
- Any remaining a11y risk or accepted limitation.

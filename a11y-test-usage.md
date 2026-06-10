# Accessibility Test Usage

This document explains how to run and extend the IBM accessibility scans used in Playwright tests.

## Scope

- Test runner: Playwright
- Scanner: IBM `accessibility-checker`
- Current scan policy: `IBM_Accessibility`
- Current compliance focus: IBM Equal Access `Level 1`

## Files

- Fixture wiring: [src/frontend/tests/fixtures.ts](/Users/viktoravelino/projects/langflow/src/frontend/tests/fixtures.ts)
- A11y helpers: [src/frontend/tests/utils/accessibility-checker.ts](/Users/viktoravelino/projects/langflow/src/frontend/tests/utils/accessibility-checker.ts)
- Checker config: [src/frontend/.achecker.yml](/Users/viktoravelino/projects/langflow/src/frontend/.achecker.yml)

## Environment flags

- `RUN_A11Y=true`
  - enables IBM scans
  - writes HTML reports
  - does **not** fail tests on a11y violations by itself

- `RUN_A11Y_ASSERT=true`
  - used together with `RUN_A11Y=true`
  - fails the test when IBM reports violations according to checker assertion rules

## Run scans

From `src/frontend`:

```bash
RUN_A11Y=true npx playwright test
```

Run scans and fail on violations:

```bash
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test
```

Run a specific file:

```bash
RUN_A11Y=true npx playwright test tests/core/features/folders.spec.ts
```

Run a specific test:

```bash
RUN_A11Y=true npx playwright test tests/core/features/folders.spec.ts --grep "CRUD folders"
```

## Report output

Reports are written to:

```bash
src/frontend/coverage/accessibility-reports/
```

Current naming is flat and short:

```bash
chromium__main-page.html
chromium__files-page.html
chromium__folders-flows-page.html
```

One scan produces one HTML report and one JSON report.

Aggregate all JSON reports into one grouped summary (from `src/frontend`):

```bash
npm run a11y:report          # table grouped by rule, deduped by DOM path
npm run a11y:report -- --json
```

## Add a scan to an existing test

Use the existing `page.runA11yScan(...)` helper exposed by the Playwright fixture.

Example:

```ts
import { expect, test } from "../../fixtures";

test("example page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("mainpage_title")).toBeVisible();

  await page.runA11yScan("main-page");
});
```

Guidelines:

- run the scan only after the page is stable
- use a short label like `main-page`, `files-page`, `folders-flows-page`
- prefer one scan per test at first
- if you add scans to existing tests, put them at a stable checkpoint before flaky mutations

## Current fixture behavior

When `RUN_A11Y=true`:
- scan runs
- summary JSON is attached to Playwright test info
- HTML report is generated

When `RUN_A11Y_ASSERT=true` too:
- test fails with a compact terminal summary
- full details stay in the HTML report

Current assertion output includes:
- scan name
- report path
- counts
- top grouped issue types


## Current limitations

- IBM checker policy is broader than current `Level 1` scope
- some existing Playwright tests are flaky, so not every file is a good assert-mode host
- a11y failures are best added first to stable smoke tests or stable checkpoints inside existing tests

## Recommended workflow

1. Add `page.runA11yScan("label")` to a stable test.
2. Run with:

```bash
RUN_A11Y=true npx playwright test <file>
```

3. Open the HTML report in `coverage/accessibility-reports/`.
4. If output is useful and test is stable, try:

```bash
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test <file> --retries=0
```

5. Map findings back to IBM Equal Access `Level 1` scope in the audit docs.

---

## Component-level a11y unit tests (jest-axe)

Second tier next to the IBM page scans. Runs on every PR via the normal Jest suite.

- Matcher: `toHaveNoViolations` is registered globally in [src/frontend/src/setupTests.ts](/Users/viktoravelino/projects/langflow/src/frontend/src/setupTests.ts)
- Shared axe instance: [src/frontend/src/utils/a11y-test.ts](/Users/viktoravelino/projects/langflow/src/frontend/src/utils/a11y-test.ts) (`color-contrast` disabled — jsdom has no layout; contrast stays with the IBM checker)
- File convention: `<component>.a11y.test.tsx` inside the component's `__tests__/` folder
- Known gaps are encoded as regular tests asserting the semantics the component *should* have — they **fail by design** until the corresponding fix lands, then stay as regression locks

Pattern:

```tsx
import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";

it("has no axe violations", async () => {
  const { container } = render(<MyComponent aria-label="Thing" />);
  expect(await axe(container)).toHaveNoViolations();
});
```

Run them:

```bash
cd src/frontend
npx jest a11y.test          # all component a11y tests
npx jest checkbox.a11y      # one component
```

### Candidate components

Wave 1 — shared primitives with named gaps in [a11y-action-plan.md](/Users/viktoravelino/projects/langflow/a11y-action-plan.md):

| Component | Plan item | What to assert | Status |
|-----------|-----------|----------------|--------|
| `components/ui/checkbox.tsx` (`Checkbox`, `CheckBoxDiv`) | 1.3 | checkbox role, `aria-checked`, keyboard toggle | Done — `checkbox.a11y.test.tsx` (failing until fix) |
| `components/ui/accordion.tsx` (`AccordionTrigger`) | 1.4 | trigger is focusable button with expanded state | Done — `accordion.a11y.test.tsx` (failing until fix) |
| `components/ui/input.tsx` | 1.2 | no duplicate label when externally labeled | Done — `input.a11y.test.tsx` (failing until fix) |
| `components/ui/dialog.tsx` | 0.4 / 1.7 | focus lands inside on open; single accessible dialog name | Done — `dialog.a11y.test.tsx` (axe + name pass; focus test failing until fix) |
| `parameterRenderComponent/components/inputComponent` | 1.1 | password toggle tab-focusable, `aria-label` + `aria-pressed` | Done — `inputComponent.a11y.test.tsx` (failing until fix) |
| `modals/baseModal` (`type="full-screen"`) | 1.5 | `role="dialog"`, `aria-modal`, labeled title | Done — `baseModal.a11y.test.tsx` (failing until fix) |
| `components/common/genericIconComponent` | 0.3 | decorative default `aria-hidden`, opt-in `aria-label` | Done — `genericIconComponent.a11y.test.tsx` (uses `jest.unmock`; failing until fix) |

Wave 2 — naming, structure, feedback:

| Component | Plan item | What to assert | Status |
|-----------|-----------|----------------|--------|
| `core/appHeaderComponent` | 2.3 / 3.3 | `<header>` landmark; bell button accessible name + unread state | Done — `appHeader.a11y.test.tsx` (failing until fix) |
| `pages/MainPage/components/list` (flow cards) | 2.2 | card is focusable link/button, Enter activates | Done — `list.a11y.test.tsx` (failing until fix) |
| `alerts/displayArea` | 4.2 | `aria-live` region announces alerts | Done — `displayArea.a11y.test.tsx` (failing until fix) |
| `components/ui/switch.tsx` | 4.1.2 | switch role + checked state | Done — `switch.a11y.test.tsx` (passing regression locks) |
| `components/ui/select.tsx` / `dropdown-menu.tsx` | 4.1.2 | combobox/menu trigger has accessible name (IBM scan flagged unnamed comboboxes) | Done — `select.a11y.test.tsx` (passing locks; call-site naming stays with IBM scans) |
| `components/ui/table.tsx` | 3.5 | header cells with `scope="col"`, caption/label | Done — `table.a11y.test.tsx` (scope test failing until fix) |
| `components/ui/tabs.tsx` | 4.1.2 | tablist/tab roles, arrow-key navigation | Done — `tabs.a11y.test.tsx` (passing regression locks) |

Not testable in jsdom (stay with IBM page scans): ReactFlow canvas, node handles/edges, contrast tokens, focus-visible CSS.

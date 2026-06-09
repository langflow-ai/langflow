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

One scan produces one HTML report.

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

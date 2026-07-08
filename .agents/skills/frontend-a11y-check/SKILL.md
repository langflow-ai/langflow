---
name: frontend-a11y-check
description: "Plan, write, run, or review accessibility checks for Langflow frontend work. Use when changes touch React UI, routes, pages, modals, forms, tables, navigation, Radix/shadcn primitives, keyboard behavior, ARIA labels, focus order, or when the user asks for an a11y check, axe test, Playwright a11y scan, or accessibility coverage."
---

# Frontend Accessibility Check

## When To Use

Use this skill for frontend work under `src/frontend` when the change affects:

- UI components, primitives, pages, routes, dialogs, drawers, popovers, dropdowns, tabs, accordions, tables, forms, navigation, or canvas controls.
- ARIA attributes, labels, roles, focus management, tab order, keyboard interaction, disabled states, loading states, or error states.
- A new route or existing route surface that should be scanned.
- A request to add, fix, run, or review accessibility tests.

Use alongside:

- `frontend-testing` for Jest/React Testing Library patterns.
- `e2e-testing` for Playwright patterns.
- `frontend-i18n` when adding or changing user-facing labels, accessible names, `aria-label`, tooltips, or visible strings.
- `ibm-a11y-automation` when the user asks to run the Python route scanner or produce Markdown/HTML reports.

## Goal

Do not stop at "run axe on default render." Inspect the changed UI and cover every meaningful user-visible state that can expose accessibility bugs.

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
   - Default
   - Populated data
   - Empty data
   - Loading
   - Error/validation visible
   - Disabled/read-only
   - Selected/expanded/open
   - Modal/dropdown/popover open
   - Mobile viewport when layout changes

## Choose Test Layer

### Jest + axe

Use Jest when the changed surface is a primitive or component that can be rendered in jsdom without full app routing.

Good for:

- `src/frontend/src/components/ui/*`
- Reusable form fields, buttons, inputs, dialogs, popovers, tables
- Local component states: loading, disabled, error, selected, invalid
- Accessible name/role assertions

Pattern:

```tsx
import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";

describe("Component accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(<Component />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_accessible_name", () => {
    render(<Component />);

    expect(screen.getByRole("button", { name: "Save Flow" })).toBeInTheDocument();
  });
});
```

Notes:

- Use `src/frontend/src/utils/a11y-test.ts`; it disables `color-contrast` because jsdom cannot check real layout.
- Prefer role/label/text queries. Use test ids only when semantic queries are not stable enough.
- Test accessible names explicitly when labels are visually hidden, loading, icon-only, or generated from props.
- Add a11y tests next to component tests: `__tests__/<name>.a11y.test.tsx`.

Command:

```bash
cd src/frontend
npx jest path/to/<name>.a11y.test.tsx --runInBand
```

### Playwright + `page.runA11yScan`

Use Playwright when the changed surface needs real browser layout, routing, app state, data mocking, modals, tables, focus order, keyboard behavior, or full-page interactions.

Good for:

- Routes and pages
- Settings pages
- Flow canvas workflows
- Tables/treegrids and row selection
- Dialogs, dropdowns, popovers, navigation sidebars
- Any issue involving tab order, focus trap, viewport layout, or real CSS

Pattern:

```ts
import { expect, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";

test.describe("Feature route accessibility", () => {
  test(
    "scans populated state",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });
      await page.goto("/settings/example");
      await expect(page.getByText("Example")).toBeVisible();

      await page.runA11yScan("settings-example-populated");
    },
  );
});
```

Rules:

- Put focused route/state specs under `src/frontend/tests/a11y/<feature>.a11y.spec.ts`.
- Import `test` and `expect` from `../fixtures`, not `@playwright/test`.
- Every test must include `@release` plus valid domain tag(s): `@workspace`, `@api`, `@database`, `@components`, `@starter-projects`.
- Use stable scan names: lowercase, feature-first, state-specific.
- Mock API responses for deterministic empty/populated/error states.
- Disable animations if timing or focus assertions are flaky.
- Use explicit interactions. Do not randomly crawl or click arbitrary destructive controls.
- If route belongs in static route coverage, update `scripts/a11y/a11y_routes.json` with stable `ready` check.

Commands:

```bash
cd src/frontend
RUN_A11Y=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=1
npm run a11y:html-report --silent
npm run a11y:job-summary --silent
```

To assert against checker baselines:

```bash
cd src/frontend
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=1
```

## Route/Page Coverage Matrix

For route or page changes, cover the smallest matrix that represents real user states:

- Loaded/default page
- Empty data state
- Populated data state
- Primary modal open
- Dropdown/popover open
- Validation or error visible
- Selected/expanded table row or bulk action state
- Mobile viewport when responsive layout changes

Do not force every state if the page cannot enter it. Do explain skipped states briefly.

## PR #13953 Pattern

Use `src/frontend/tests/a11y/api-keys.a11y.spec.ts` as model for route-level work:

- Mock API data.
- Scan populated table.
- Scan empty table.
- Open create modal and scan.
- Submit form to generated-result modal and scan.
- Open text-cell modal and scan.
- Select table row and scan selected state.
- Set mobile viewport and scan responsive state.

This is the expected bar for data-rich routes.

## Manual Code Review Checklist

While reading changed UI code, check:

- Interactive icon-only controls have accessible names.
- Inputs have labels or valid `aria-labelledby`/`aria-label`.
- Visible label and accessible name stay aligned.
- Dialogs have title/description and trap/restore focus.
- Dropdown/popover content is reachable by keyboard and closes with Escape.
- Custom buttons/links use semantic elements where possible.
- Disabled controls are not focusable unless intentionally discoverable.
- Tables/treegrids have one logical tab stop and no duplicate row/header tab stops.
- Pagination/disabled table controls are not in tab order.
- Error text is associated with inputs.
- Loading state keeps useful accessible name.
- `aria-hidden` does not hide focusable descendants.
- New user-facing labels go through i18n in every locale.

## Report Back

When done, state:

- Test files added or updated.
- States scanned.
- Commands run.
- Any states not covered and why.
- Any remaining a11y risk.

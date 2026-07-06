---
name: a11y-spec-authoring
description: Author Playwright IBM Equal Access (a11y) scan spec files for Langflow frontend features and routes. Use when the user asks to add, write, or extend accessibility scan coverage for a page, feature, modal, or route; when creating a tests/a11y/*.a11y.spec.ts file; when enumerating states/modals/hidden fields to scan; or when triaging and fixing IBM Level 1 accessibility violations found by runA11yScan. For the ad-hoc Python route scanner instead, use the ibm-a11y-automation skill.
---

# Langflow a11y Scan Spec Authoring

Use this skill to build a Playwright accessibility spec that scans a feature or
route with the IBM Equal Access checker and drives its findings to zero.

## When to Apply

- User asks to **add a11y coverage** for a feature, page, modal, or route.
- User asks to **write or fix a `tests/a11y/*.a11y.spec.ts`** file.
- User asks to **capture all states** (modals, dropdowns, hidden fields) in a scan.
- User asks to **fix IBM Level 1 accessibility violations** surfaced by a scan.

**Do NOT apply** when:

- The user wants the ad-hoc Python route scanner / report → use `ibm-a11y-automation`.
- The user wants general E2E behavior tests → use `e2e-testing`.

## Source material (read these first)

| File | Why |
|---|---|
| `src/frontend/tests/a11y/README.md` | The 5-step a11y coverage workflow this skill implements. |
| `src/frontend/tests/a11y/ibm-a11y-level1-criteria.md` | Maps each flagged rule to a WCAG/IBM criterion + fix patterns. |
| `src/frontend/tests/a11y/ibm-a11y-level1-tracker.md` | Route checklist. Pick/add the surface you are covering; tick it when clean. |
| `src/frontend/tests/a11y/knowledge-bases.a11y.spec.ts` | Best full example: many states, modals, drawers, `ignoreRules`, a fixtures helper. |
| `src/frontend/tests/a11y/auth-pages.a11y.spec.ts` | Gated routes, validation, error toasts, light/dark scans. |
| `src/frontend/tests/a11y/core-pages.a11y.spec.ts` | Serial journey across canvas → config panel → playground. |
| `src/frontend/tests/a11y/static-routes.a11y.spec.ts` | Manifest-driven scan of plain static routes. |

## The workflow

1. **Create the spec** `tests/a11y/<feature>.a11y.spec.ts` for the route/feature.
2. **Capture every state** — routes plus opened modals, clicked menus, revealed
   hidden fields, both color schemes.
3. **Run the scan** with `RUN_A11Y=true` and read the HTML report.
4. **Fix the app code** for each violation; suppress only framework-owned rules
   with a justified comment.
5. **Reference the criteria** guide, then tick the tracker box when clean.

## File conventions

- Location: `src/frontend/tests/a11y/`.
- Name: kebab-case + `.a11y.spec.ts` (e.g. `knowledge-bases.a11y.spec.ts`).
- Reusable mocks/route helpers go in `tests/a11y/helpers/<feature>.fixtures.ts`.
- **Import from `../fixtures`, never `@playwright/test`** — the custom fixture
  attaches `runA11yScan`, `allowFlowErrors`, and API-error detection.
- **Tag every test** with `@release` plus domain tags (commonly
  `["@release", "@workspace"]`). Untagged specs drop out of the release run.

## The `runA11yScan` API

```ts
await page.runA11yScan(label);                              // scan current DOM
await page.runA11yScan(label, { colorScheme: "dark" });    // scan dark mode
await page.runA11yScan(label, { ignoreRules: KB_IGNORE_RULES });
```

- `label` — a unique, kebab/underscore-friendly string per **distinct UI
  surface** (e.g. `kb-empty`, `kb-delete-modal-open`). It names the report entry.
- Scans only run when `RUN_A11Y=true`; otherwise the call is a no-op that returns
  `null`. This lets a11y specs live alongside behavior specs cheaply.
- `ignoreRules` drops matching rule IDs from the violation count and the failure
  message. Use it only for framework/chrome-owned rules (see below).

## Capturing every state (the important part)

The checker only sees the DOM present **at the moment `runA11yScan` runs**. A
single page load misses most of the feature. Before each scan, gate on a
`data-testid` with `expect(...).toBeVisible()` so you are certain the target
state rendered, then scan. Enumerate:

- **Route surfaces:** list, detail, empty, loading, error, no-results.
- **Overlays while open:** dialogs, drawers, dropdowns, popovers, tooltips —
  scan before pressing `Escape`/closing.
- **Menus & buttons that reveal UI:** row-action menus, bulk-action bars,
  confirmation modals, multi-step wizards (scan each step).
- **Conditionally-rendered / hidden fields:** expand advanced sections, click
  "add metadata"/"add row", open per-item editors, and trigger validation so the
  error text and previously-hidden inputs are actually in the DOM.
- **Color schemes:** scan light and dark where the feature themes differently.

Patterns from the examples:

```ts
// Gate, then scan an opened menu (knowledge-bases.a11y.spec.ts)
await page.getByTestId("kb-row-actions-trigger").first().click();
await expect(page.getByRole("menuitem", { name: /view chunks/i })).toBeVisible({
  timeout: TIMEOUTS.standard,
});
await page.runA11yScan("kb-row-actions-open", { ignoreRules: KB_IGNORE_RULES });

// Reveal a hidden field before scanning
await page.getByTestId("kb-run-metadata-add").click();
await expect(page.getByTestId("kb-run-metadata-key-0")).toBeVisible();
await page.runA11yScan("kb-upload-metadata-add", { ignoreRules: KB_IGNORE_RULES });

// Loading/error states via a gated route or forced error
page.allowFlowErrors(); // when intentionally driving a 4xx/5xx
```

For loading states, gate the network response so the spinner stays on screen
during the scan (see `gateRoute` in `helpers/knowledge-bases.fixtures.ts`). For
error states, mock a 4xx and call `page.allowFlowErrors()` so the fixture's
API-error detector does not fail the test.

## Disable animations

Add a style tag that zeroes animations/transitions before scanning so the DOM is
stable (every example defines a `disableAnimations(page)` helper). After route
navigation, call `settleNetwork(page)` (a `networkidle` wait) so async content
lands before the scan.

## Suppressing framework-owned rules (`ignoreRules`)

Fix application markup first. Only suppress a rule when it is provably owned by
shared chrome (app header, folder sidebar) or a third-party widget (Radix, AG
Grid, cmdk) and cannot be fixed from the feature's markup. Define a module-level
array and document each entry against the report DOM — match the depth of the
`KB_IGNORE_RULES` comments:

```ts
const FEATURE_IGNORE_RULES = [
  // rule_id: <where it fires in the report DOM> + <why it is not fixable here>.
  // e.g. "aria_hidden_nontabbable": Radix sets aria-hidden on the whole
  // background subtree without `inert`; flags app-wide chrome, not this feature.
  "aria_hidden_nontabbable",
];
```

Keep real, tracked gaps (e.g. theme-level `text_contrast_sufficient`) called out
in the comment as a known Level 1 gap to fix elsewhere — never silently drop them.

## Starter template

```ts
import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

const RELEASE = { tag: ["@release", "@workspace"] };

// Only suppress framework/chrome-owned rules, each justified against the report.
const FEATURE_IGNORE_RULES: string[] = [];

async function disableAnimations(page: LangflowPage) {
  await page.addStyleTag({
    content: `*,*::before,*::after{animation-duration:0s !important;animation-delay:0s !important;transition-duration:0s !important;transition-delay:0s !important;scroll-behavior:auto !important;}`,
  });
}

async function openFeatureRoute(page: LangflowPage) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/your/route");
  await disableAnimations(page);
  await expect(page.getByTestId("your-ready-testid")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

test.describe("<feature> accessibility", () => {
  test("scans the default state", RELEASE, async ({ page }) => {
    await openFeatureRoute(page);
    await page.runA11yScan("<feature>-default", {
      ignoreRules: FEATURE_IGNORE_RULES,
    });
  });

  test("scans an opened modal", RELEASE, async ({ page }) => {
    await openFeatureRoute(page);
    await page.getByTestId("open-modal-btn").click();
    await expect(page.getByRole("dialog")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("<feature>-modal-open", {
      ignoreRules: FEATURE_IGNORE_RULES,
    });
  });
});
```

For a feature with many scenarios, drive data-only variants from an array of
`{ name, run }` scenarios (see `KB_LIST_SCENARIOS` in the KB spec) to cut
bootstrap overhead, and use `test.describe.configure({ mode: "serial" })` for a
single journey that walks through connected states (see `core-pages.a11y.spec.ts`).

## Run, read, fix

```bash
cd src/frontend
# Run + generate the browsable HTML report
RUN_A11Y=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=1
npm run a11y:html-report --silent   # -> coverage/accessibility-reports/index.html

# Fail on any new violation (what CI does with the `assert` input)
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=1
```

For each violation: open the HTML report, find the rule + DOM/ARIA path, map it to
a criterion in `ibm-a11y-level1-criteria.md`, fix the **application code** (not the
test), and re-run until clean. CI (`.github/workflows/a11y-scan.yml`) auto-discovers
any spec that calls `runA11yScan(`, so no workflow edit is needed for a new spec.

## Rules

- Import `test`/`expect` from `../fixtures`; tag every test `@release`.
- One `runA11yScan` label per distinct UI surface; labels must be unique + stable.
- Always gate on a visible `data-testid`/role before scanning a state.
- Fix app markup before adding an `ignoreRules` entry; justify every suppression.
- Don't invent routes — read `src/frontend/src/routes.tsx` and the tracker.
- Prefer real integrations; when mocking, put route mocks in `helpers/*.fixtures.ts`.
- Tick the tracker box only after the surface scans clean (or findings are
  documented suppressions).

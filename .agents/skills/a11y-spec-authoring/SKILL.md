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
| `src/frontend/tests/a11y/<feature>-ignore-rules.json` | Feature-specific suppress list (KB example: `knowledge-bases-ignore-rules.json`). |
| `src/frontend/tests/a11y/knowledge-bases.a11y.spec.ts` | Best full example: many states, modals, drawers, shared ignore rules, a fixtures helper. |
| `src/frontend/tests/a11y/auth-pages.a11y.spec.ts` | Gated routes, validation, error toasts, light/dark scans. |
| `src/frontend/tests/a11y/core-pages.a11y.spec.ts` | Serial journey across canvas → config panel → playground. |
| `src/frontend/tests/a11y/static-routes.a11y.spec.ts` | Manifest-driven scan of plain static routes. |

## The workflow

1. **Create the spec** `tests/a11y/<feature>.a11y.spec.ts` for the route/feature.
2. **Capture every state** — routes plus opened modals, clicked menus, revealed
   hidden fields, both color schemes.
3. **Run the scan** with `RUN_A11Y=true` and read the HTML report.
4. **Fix the app code** for each violation; suppress only framework-owned rules
   via the shared ignore list.
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

- `label` — a unique, descriptive string per **distinct UI surface** (e.g.
  `kb-empty`, `kb-delete-modal-open`). **The label becomes the route name in the
  report**, so keep it unique and stable. (For the 2nd+ scan inside one test the
  fixture appends a numeric index; the report strips it, so don't rely on it.)
- Scans only run when `RUN_A11Y=true`; otherwise the call is a no-op that returns
  `null`. This lets a11y specs live alongside behavior specs cheaply.
- `ignoreRules` drops matching rule IDs from the in-test violation count and the
  failure message (only relevant under `RUN_A11Y_ASSERT=true`).

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

For loading states, gate the network response so the spinner stays on screen
during the scan (see `gateRoute` in `helpers/knowledge-bases.fixtures.ts`). For
error states, mock a 4xx and call `page.allowFlowErrors()` so the fixture's
API-error detector does not fail the test.

## Gotchas (learned the hard way)

- **`runA11yScan` dismisses open overlays.** Running the scan injects and runs
  the IBM ACE engine, which mutates/inspects the DOM and closes open Radix menus,
  dropdowns, and popovers. If you need to interact with that overlay *after* the
  scan (e.g. click a menu item), **re-open it**, and do so resiliently because
  re-opening a Radix menu is a toggle click that can race the previous close:

  ```ts
  await page.keyboard.press("Escape");
  await expect(menuItem).toBeHidden({ timeout: TIMEOUTS.standard });
  await expect(async () => {
    await trigger.click();
    await expect(targetItem).toBeVisible({ timeout: TIMEOUTS.short });
  }).toPass({ timeout: TIMEOUTS.standard });
  ```

- **"at least one visible" checks must use `.first()`.** A locator combined with
  `.or()` throws a strict-mode violation when more than one candidate is present
  (e.g. a page showing both an "Add" button and a search input). Assert on
  `locator.first()`.

- **Disable animations + settle the network.** Add a style tag that zeroes
  animations/transitions before scanning (every example defines a
  `disableAnimations(page)` helper), and call `settleNetwork(page)` after
  navigation so async content lands before the scan.

## Suppressing framework-owned rules

Fix application markup first. Only suppress a rule when it is provably owned by
shared chrome (app header, folder sidebar) or a third-party widget (Radix, AG
Grid, cmdk) and cannot be fixed from the feature's markup.

**Suppressions are feature-specific.** Each feature owns its own
`tests/a11y/<feature>-ignore-rules.json` — one entry per rule with a `ruleId`
and a `reason` grounded in the report DOM. The KB example is
`knowledge-bases-ignore-rules.json`.

- The spec imports it to build the `ignoreRules` array:

  ```ts
  import a11yIgnoreRules from "./rules/knowledge-bases-ignore-rules.json";
  const KB_IGNORE_RULES = a11yIgnoreRules.suppressed.map((rule) => rule.ruleId);
  ```

- `build-a11y-html-report.mjs` reads the file and **greys findings out only on
  routes whose label starts with `kb`** — other feature scans see all their
  findings as actionable. The report shows *actionable* vs *suppressed* counts;
  the job summary sorts routes by actionable issues and lists only actionable
  rules.

Other features should create their own `<feature>-ignore-rules.json` and scope
the report-level suppression to their route prefix (update
`isSuppressedForRoute` in `build-a11y-html-report.mjs` if/when needed). Keep
real tracked gaps (e.g. theme-level `text_contrast_sufficient`) in the list with
a reason — they show as suppressed but stay visible for tracking.

## Starter template

```ts
import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";
import a11yIgnoreRules from "./<feature>-ignore-rules.json";

const RELEASE = { tag: ["@release", "@workspace"] };
const IGNORE_RULES = a11yIgnoreRules.suppressed.map((rule) => rule.ruleId);

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
    await page.runA11yScan("<feature>-default", { ignoreRules: IGNORE_RULES });
  });

  test("scans an opened modal", RELEASE, async ({ page }) => {
    await openFeatureRoute(page);
    await page.getByTestId("open-modal-btn").click();
    await expect(page.getByRole("dialog")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
    await page.runA11yScan("<feature>-modal-open", { ignoreRules: IGNORE_RULES });
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
npm run a11y:job-summary --silent   # markdown summary (actionable vs suppressed)

# Fail on any new violation (what CI does with the `assert` input)
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/<feature>.a11y.spec.ts --project=chromium --workers=1
```

Focus on the **actionable** count/rules — suppressed rows are chrome/framework
issues tracked elsewhere. For each actionable violation: open the HTML report,
find the rule + DOM/ARIA path, map it to a criterion in
`ibm-a11y-level1-criteria.md`, fix the **application code** (not the test), and
re-run until actionable is zero. CI (`.github/workflows/a11y-scan.yml`)
auto-discovers any spec that calls `runA11yScan(`, so no workflow edit is needed
for a new spec.

## Rules

- Import `test`/`expect` from `../fixtures`; tag every test `@release`.
- One `runA11yScan` label per distinct UI surface; labels must be unique + stable
  (the label is the report's route name).
- Always gate on a visible `data-testid`/role before scanning a state.
- Re-open overlays after a scan (resiliently) — the scan dismisses them.
- Fix app markup before suppressing; add suppressions to `<feature>-ignore-rules.json`
  with a DOM-grounded reason.
- Don't invent routes — read `src/frontend/src/routes.tsx` and the tracker.
- Prefer real integrations; when mocking, put route mocks in `helpers/*.fixtures.ts`.
- Tick the tracker box only after the surface's actionable count is zero.

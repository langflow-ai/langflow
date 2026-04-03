---
name: e2e-testing
description: Write and review Playwright E2E tests for Langflow. Trigger when the user asks to write, fix, or review E2E tests, spec files, Playwright tests, or integration tests that exercise the full UI. Also trigger when modifying data-testid attributes, test helpers in tests/utils/, or fixture configuration.
---

# Langflow E2E Testing (Playwright)

## When to Apply

- User asks to **write E2E tests** for a feature or flow
- User asks to **fix a failing E2E test**
- User asks to **review E2E test coverage**
- User modifies `data-testid` attributes in components (may break existing tests)
- User changes test utilities in `src/frontend/tests/utils/`

**Do NOT apply** when:
- User asks about unit tests (use `frontend-testing` skill for Jest)
- User asks about backend tests (use `backend-code-review` skill for pytest)

## Tech Stack

| Tool | Version | Purpose |
|------|---------|---------|
| Playwright | 1.57.0 | E2E test runner + browser automation |
| Chromium | (bundled) | Default browser (Firefox/Safari disabled) |
| Custom fixtures | `tests/fixtures.ts` | Auto-detects API errors and flow execution failures |

## Key Commands

```bash
# Run all E2E tests
npx playwright test

# Run tests filtered by tag
npx playwright test --grep "@release"
npx playwright test --grep "@workspace"
npx playwright test --grep "@starter-projects"

# Run a specific test file
npx playwright test tests/core/features/run-flow.spec.ts

# Debug mode (headed browser + step through)
npx playwright test --debug

# Show HTML report after run
npx playwright show-report

# Update snapshots (if used)
npx playwright test --update-snapshots
```

## Configuration

**File**: `src/frontend/playwright.config.ts`

| Setting | Value | Why |
|---------|-------|-----|
| `fullyParallel` | `true` | Tests run in parallel for speed |
| `timeout` | 5 minutes | Flow builds can be slow; prevents false timeouts |
| `retries` | 3 (local), 2 (CI) | Flaky network/rendering issues; retries catch them |
| `workers` | 2 | Balances speed and resource usage |
| `actionTimeout` | 20s | Individual action timeout (click, fill, etc.) |
| `trace` | `on-first-retry` | Captures trace on failures for debugging |
| `baseURL` | `http://localhost:3000` | Vite dev server |

**WebServer**: Playwright auto-starts backend (uvicorn on 7860) + frontend (npm start on 3000).

## Directory Structure

```
src/frontend/tests/
├── fixtures.ts                     # Custom test fixture with error detection
├── globalTeardown.ts               # Cleanup (removes temp DB after tests)
├── core/
│   ├── features/                   # Main feature tests (run-flow, playground, etc.)
│   ├── integrations/               # Starter project / template tests
│   ├── regression/                 # Bug regression tests
│   └── unit/                       # Component-level Playwright tests
├── extended/
│   ├── features/                   # Extended features (MCP, auto-save, etc.)
│   ├── integrations/               # Extended integrations
│   └── regression/                 # Extended regressions
└── utils/                          # 37+ shared helper functions
```

## File Naming

- **kebab-case** with `.spec.ts` suffix: `run-flow.spec.ts`, `playground.spec.ts`, `flow-lock.spec.ts`
- Template tests may use spaces: `Document QA.spec.ts`, `Social Media Agent.spec.ts`
- Sharded tests for parallelization: `chatInputOutputUser-shard-0.spec.ts`

> **Note**: E2E tests use `.spec.ts` (Playwright convention). Unit tests use `.test.tsx` (Jest convention). Do not mix them.

## Test Anatomy

### Basic Test

```typescript
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to run a flow successfully",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Arrange: Create a flow
    await page.getByTestId("blank-flow").click();

    // Act: Add components and run
    await page.getByTestId("sidebar-search-input").fill("Chat Output");
    // ... setup ...

    // Assert: Verify result
    await expect(page.getByTestId("build-status-success")).toBeVisible({ timeout: 30000 });
  },
);
```

### With test.describe

```typescript
test.describe("Flow Lock Feature", () => {
  test(
    "should lock and unlock a flow",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      // ...
    },
  );

  test(
    "should prevent editing when locked",
    { tag: ["@release"] },
    async ({ page }) => {
      // ...
    },
  );
});
```

### With Serial Mode (tests that depend on order)

```typescript
test.describe.configure({ mode: "serial" });

test("step 1: create flow", async ({ page }) => { /* ... */ });
test("step 2: edit flow", async ({ page }) => { /* ... */ });
test("step 3: delete flow", async ({ page }) => { /* ... */ });
```

### With Event Delivery Modes (streaming/polling/direct)

```typescript
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Document Q&A should work",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    // This test runs 3 times: streaming, polling, direct
    // Each mode is configured automatically via route interception
  },
);
```

## Tags System

Every test MUST have at least one tag. Tags enable filtering and CI pipeline configuration.

| Tag | Purpose | When to Use |
|-----|---------|-------------|
| `@release` | Tests that must pass before release | Critical user flows |
| `@workspace` | Workspace/flow management | Creating, editing, deleting flows |
| `@api` | API-dependent features | Tests that call backend endpoints |
| `@database` | Database operations | Tests involving persistence |
| `@components` | Component-level tests | Individual component behavior |
| `@starter-projects` | Template/starter project tests | Pre-built flow templates |
| `@regression` | Bug regression tests | Tests for specific fixed bugs |

```typescript
// Right: tag your test
test("my feature test", { tag: ["@release", "@workspace"] }, async ({ page }) => { ... });

// Wrong: no tags — test can't be filtered
test("my feature test", async ({ page }) => { ... });
```

## Custom Fixtures: Error Detection

**Always import `test` and `expect` from `../../fixtures`, NOT from `@playwright/test`.**

```typescript
// Right
import { expect, test } from "../../fixtures";

// Wrong — bypasses error detection
import { expect, test } from "@playwright/test";
```

Why: The custom fixture automatically monitors all `/api/` responses and fails the test if:
- HTTP 400, 404, 422, or 500 errors occur
- Flow execution returns `error: true` in event streams
- Python exceptions appear in streamed responses

To opt-in to expected errors (e.g., testing error handling):
```typescript
test("should show error on invalid input", { tag: ["@release"] }, async ({ page }) => {
  page.allowFlowErrors();  // Allow flow errors for this test
  // ... test that expects errors ...
});
```

## Selector Strategy

### Priority (in order of preference)

1. **`getByTestId`** — Most stable, used 95% of the time in Langflow
2. **`getByRole`** — For buttons, headings, and form elements
3. **`getByText`** — For visible text content
4. **`waitForSelector`** — For CSS selectors and dynamic elements
5. **`locator`** — For complex selectors (CSS, XPath)

### Common data-testid Patterns

**Canvas & Navigation:**
- `blank-flow` — New blank flow button
- `sidebar-search-input` — Component search
- `canvas_controls_dropdown` — Canvas controls menu
- `fit_view`, `zoom_out`, `zoom_in` — Canvas controls
- `react-flow-id` — ReactFlow canvas container

**Component Fields:**
- `popover-anchor-input-{fieldname}` — Input field for a component parameter
- `input-chat-playground` — Playground chat input
- `div-chat-message` — Chat message in playground

**Actions:**
- `add-component-button-{component}` — Add component to canvas
- `button-send` — Send chat message
- `button_run_{component}` — Run specific component
- `publish-button`, `save-flow-button` — Flow actions
- `edit-fields-button` — Toggle inspection panel field editor

**Modals & Panels:**
- `modal-title` — Modal heading
- `icon-Globe` — Global variables
- `icon-Lock` — Flow lock toggle
- `session-selector` — Playground session switcher

### Important: Global Variables and Badges

When a component field has a global variable selected (`load_from_db: true` + `value: "OPENAI_API_KEY"`), the field renders a **badge** instead of an `<input>` element. This means `getByTestId("popover-anchor-input-api_key")` will NOT find the element — it doesn't exist in the DOM.

Templates with global variables pre-selected: Market Research, Price Deal Finder, Research Agent.
Templates without (input IS rendered): Instagram Copywriter.

## Core Helper Functions

Located in `src/frontend/tests/utils/`:

| Function | What it Does | When to Use |
|----------|-------------|-------------|
| `awaitBootstrapTest(page)` | Waits for app to fully load | **Start of every test** |
| `initialGPTsetup(page)` | Full setup: adjustView → updateComponents → selectModel → addKey → adjustView → unselectNodes | Tests that need OpenAI configured |
| `adjustScreenView(page, opts?)` | Fit view + zoom out | After adding components to canvas |
| `zoomOut(page, times)` | Zoom out N times | When components are too small |
| `selectGptModel(page)` | Selects gpt-4o-mini for all Language Model nodes | GPT-dependent tests |
| `addOpenAiInputKey(page)` | Fills OPENAI_API_KEY for all openai_api_key fields | Tests requiring API key |
| `enableInspectPanel(page)` | Toggles inspection panel ON | **MUST call before `edit-fields-button`** |
| `disableInspectPanel(page)` | Toggles inspection panel OFF | Cleanup after inspection |
| `updateOldComponents(page)` | Clicks "Update all" if outdated components exist | After loading saved flows |
| `unselectNodes(page)` | Clicks empty canvas area to deselect all nodes | After node operations |
| `renameFlow(page, { flowName })` | Renames the current flow | Flow management tests |
| `uploadFile(page, filename)` | Uploads a file from test assets | File upload tests |
| `withEventDeliveryModes(...)` | Runs test 3x: streaming, polling, direct | Starter project tests |

### initialGPTsetup Options

```typescript
await initialGPTsetup(page);  // All steps

await initialGPTsetup(page, {
  skipAdjustScreenView: true,
  skipUpdateOldComponents: true,
  skipSelectGptModel: true,
});
```

### Inspection Panel Pattern (CRITICAL)

```typescript
// MUST enable inspection panel FIRST
await enableInspectPanel(page);

// Click a node to select it
await page.getByTestId("title-OpenAI").click();

// Open field editor
await page.getByTestId("edit-fields-button").click();

// Toggle field visibility
await page.getByTestId("showmodel_name").click();

// Close field editor
await page.getByTestId("edit-fields-button").click();
```

**If you skip `enableInspectPanel(page)`, the `edit-fields-button` will NOT be visible.**

## Skip Patterns

```typescript
// Skip test if env var missing
test.skip(!process?.env?.OPENAI_API_KEY, "OPENAI_API_KEY required to run this test");

// Skip test unconditionally with reason
test.skip(true, "Feature not yet implemented with new designs");
```

## Writing Good E2E Tests

### Do:
- **Tag every test** with at least one tag
- **Import from `../../fixtures`**, not `@playwright/test`
- **Start with `awaitBootstrapTest(page)`** — always
- **Use `getByTestId`** for stable selectors
- **Set explicit timeouts** on `waitForSelector` and `expect(...).toBeVisible()` for async operations
- **Test the complete user flow**: setup → action → verification
- **Use `withEventDeliveryModes`** for tests that involve flow execution (chat, build)

### Don't:
- **Don't use `page.waitForTimeout()`** unless absolutely necessary — prefer `waitForSelector` or `expect().toBeVisible()`
- **Don't hardcode API keys** — read from `process.env.OPENAI_API_KEY`
- **Don't skip tests without a reason** — always provide the second argument to `test.skip()`
- **Don't import from `@playwright/test`** — use the custom fixtures
- **Don't forget `enableInspectPanel(page)`** before accessing `edit-fields-button`
- **Don't assume input fields exist** when global variables are selected (badge renders instead)

### Challenge Tests (Apply Here Too)

E2E tests should also cover adversarial scenarios:
- **Invalid input**: paste 10K characters, special characters (`<script>alert(1)</script>`), empty submissions
- **Network interruption**: what happens if the user loses connection mid-build?
- **Permission boundaries**: can a user access another user's flow via direct URL?
- **Concurrent actions**: double-click delete, rapid chat messages
- **Error recovery**: does the UI recover gracefully from a 500 error?

## References

- [Selector Patterns](references/selectors.md) — Complete data-testid catalog
- [Helper Functions](references/helpers.md) — Detailed documentation of all 37+ utility functions
- [Test Fixtures](references/fixtures.md) — Custom fixture error detection behavior

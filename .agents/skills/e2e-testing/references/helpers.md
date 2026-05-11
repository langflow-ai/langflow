# E2E Test Helper Functions

All helpers are located in `src/frontend/tests/utils/`. Import them by name.

## Bootstrap & Setup

### `awaitBootstrapTest(page, options?)`

**Call this at the start of EVERY test.** Waits for the app to fully load and optionally opens the new project modal.

```typescript
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// Default: waits for load + opens new project modal
await awaitBootstrapTest(page);

// Skip opening modal (for tests that start on an existing page)
await awaitBootstrapTest(page, { skipModal: true });
```

Why: Without this, tests race against the app's initialization. Components may not be rendered, stores may not be hydrated, and API calls may not be complete. Every flaky "element not found" failure is likely a missing `awaitBootstrapTest`.

### `initialGPTsetup(page, options?)`

Full OpenAI setup pipeline. Calls 6 steps in order:
1. `adjustScreenView` — fit view + zoom out
2. `updateOldComponents` — update any outdated components
3. `selectGptModel` — select gpt-4o-mini for all Language Model nodes
4. `addOpenAiInputKey` — fill OPENAI_API_KEY in all openai_api_key fields
5. `adjustScreenView` — fit again (components may have moved)
6. `unselectNodes` — click empty canvas to deselect

```typescript
// All steps
await initialGPTsetup(page);

// Skip specific steps
await initialGPTsetup(page, {
  skipAdjustScreenView: true,
  skipUpdateOldComponents: true,
  skipSelectGptModel: true,
});
```

Why: Many tests need a working OpenAI-connected flow. This helper standardizes the setup so test authors don't reinvent it. The order matters — updating components before selecting models prevents stale model dropdowns.

## Canvas Controls

### `adjustScreenView(page, options?)`

Clicks "fit view" then zooms out. Ensures all nodes are visible and interactable.

```typescript
await adjustScreenView(page);                          // Default: fit + 1 zoom out
await adjustScreenView(page, { numberOfZoomOut: 3 });  // Fit + 3 zoom outs
```

Why: After adding components, some may be off-screen or overlapping. Fit view centers them; zoom out ensures click targets are large enough for Playwright to hit reliably.

### `zoomOut(page, times)`

Zooms out the canvas a specific number of times.

```typescript
await zoomOut(page, 5);
```

### `unselectNodes(page)`

Clicks the empty canvas area at position (0, 0) to deselect all nodes.

```typescript
await unselectNodes(page);
```

Why: Selected nodes show selection UI (toolbars, handles) that can overlay other elements. Deselecting before interacting with other elements prevents click interception.

## Component Setup

### `selectGptModel(page)`

Finds all Language Model nodes and selects `gpt-4o-mini` in their model dropdown.

Why: Tests that require LLM execution need a specific model. Using `gpt-4o-mini` keeps costs low and responses fast.

### `addOpenAiInputKey(page)`

Finds all fields with `data-testid="popover-anchor-input-openai_api_key"` and fills them with `process.env.OPENAI_API_KEY`.

**Warning**: Only works when the field renders as an `<input>`. If a global variable is selected (badge mode), this helper won't find the field. Check the template's `load_from_db` setting.

### `updateOldComponents(page)`

If the canvas shows an "Update all" button (outdated components), clicks it and waits for update to complete.

Why: Saved flows from older versions may have outdated component definitions. Updating them ensures the test runs against current component behavior, not stale cached versions.

## Inspection Panel

### `enableInspectPanel(page)`

Opens the canvas controls dropdown and toggles the inspection panel ON.

**MUST be called BEFORE any interaction with `edit-fields-button`.** Without it, the inspection panel is hidden and `edit-fields-button` does not exist in the DOM.

```typescript
await enableInspectPanel(page);
await page.getByTestId("title-OpenAI").click();       // Select a node
await page.getByTestId("edit-fields-button").click();  // Now visible
```

### `disableInspectPanel(page)`

Toggles the inspection panel OFF. Use for cleanup or when testing canvas-only behavior.

## Flow Management

### `renameFlow(page, options)`

Renames the current flow in the workspace.

```typescript
await renameFlow(page, { flowName: "My Test Flow" });
```

### `uploadFile(page, filename)`

Uploads a file from the `tests/assets/` directory.

```typescript
await uploadFile(page, "test-document.pdf");
```

## Event Delivery Modes

### `withEventDeliveryModes(title, config, testFn, options?)`

Wraps a test function to run it 3 times: once for each event delivery mode (streaming, polling, direct). Each mode is configured by intercepting the `/api/v1/config` route.

```typescript
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Document Q&A should process and respond",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    // Test body — runs 3 times with different delivery modes
    await page.getByTestId("input-chat-playground").fill("What is this about?");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("div-chat-message")).toBeVisible({ timeout: 60000 });
  },
  { timeout: 10000 },  // Optional delay between mode switches
);
```

Why: Langflow supports 3 event delivery modes. A bug that only appears in polling mode would be missed if tests only run in streaming mode. This helper ensures all modes are covered without writing 3x the tests.

## Advanced Patterns

### `openAdvancedOptions(page)` (LEGACY)

Opens the old edit modal for component configuration. **Deprecated** — use `enableInspectPanel` + `edit-fields-button` for new tests.

### `closeAdvancedOptions(page)` (LEGACY)

Closes the old edit modal. **Deprecated**.

## Creating New Helpers

When to create a new helper:
- The same 5+ lines of setup appear in 3+ test files (DRY)
- The pattern involves complex waits or retries that are easy to get wrong
- The helper encapsulates Langflow-specific knowledge (e.g., global variable badge behavior)

When NOT to create a helper:
- For a single test's setup (keep it inline)
- For generic Playwright operations (use Playwright API directly)
- For assertions (assertions should be explicit in the test, not hidden in helpers)

Place new helpers in `src/frontend/tests/utils/` with kebab-case naming: `my-new-helper.ts`.

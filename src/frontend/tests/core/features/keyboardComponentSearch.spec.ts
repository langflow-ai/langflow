import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";

test(
  "user can search and add components using keyboard shortcuts",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    // Navigate to homepage and handle initial modal
    await awaitBootstrapTest(page);

    // Start with blank flow. The click creates the flow and navigates, but the
    // canvas we are leaving has a sidebar search input too -- so waiting on that
    // selector alone can resolve against the outgoing page, which is then torn
    // down mid-test and takes the focus set below with it. Wait for the new
    // flow's own load to land before touching the keyboard.
    const newFlowLoaded = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        /\/api\/v1\/flows\/[0-9a-f-]{36}$/.test(response.url()),
    );
    await page.getByTestId("blank-flow").click();
    await newFlowLoaded;
    // Readiness is asserted after the navigation barrier above, so it cannot be
    // satisfied by the outgoing canvas. This subsumes the previous fixed 500ms
    // wait: it holds until the sidebar search input is visible *and* the sidebar
    // reports data-search-hotkey-ready, which is the state the sleep guessed at.
    await waitForFlowEditorReady(page);

    // Start the shortcut on the canvas so a previously focused noflow control
    // cannot intentionally suppress the global search hotkey.
    await page.locator(".react-flow__pane").click();
    await expect
      .poll(() =>
        page.evaluate(() => !document.activeElement?.closest(".noflow")),
      )
      .toBe(true);
    const sidebarSearchInput = page.getByTestId("sidebar-search-input");
    await expect(sidebarSearchInput).not.toBeFocused();

    // Press "/" to activate search
    await page.keyboard.press("Slash");

    // Verify search is focused and disclosures are closed when search is empty
    await expect(sidebarSearchInput).toBeFocused({
      timeout: 1000,
    });
    await expect(page.getByTestId("input_outputChat Input")).not.toBeVisible();

    // Type "chat" to search for chat components
    await page.keyboard.type("chat");

    await expect(page.getByTestId("input_outputChat Input")).toBeVisible({
      timeout: 1000,
    });

    // Verify disclosures open when search has content
    await expect(page.getByTestId("input_outputChat Input")).toBeVisible();

    // Press Tab to focus first result
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");

    // Verify some expected chat-related components are visible
    await expect(page.getByTestId("input_outputChat Input")).toBeVisible();
    await expect(page.getByTestId("input_outputChat Output")).toBeVisible();

    // Press Space to select the component
    await page.keyboard.press("Space");

    // Verify component was added to flow
    const addedComponent = await page.locator(".react-flow__node").first();
    await expect(addedComponent).toBeVisible();

    // Clear search input and verify disclosures are closed
    await sidebarSearchInput.clear();
    await expect(page.getByTestId("input_outputChat Input")).not.toBeVisible();

    // Test Enter key selection
    await page.keyboard.press("Slash");
    await page.keyboard.type("prompt");

    // Verify disclosures open with new search
    await expect(
      page.getByTestId("models_and_agentsPrompt Template"),
    ).toBeVisible();

    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Enter");

    // Verify second component was added
    const nodeCount = await page.locator(".react-flow__node").count();
    expect(nodeCount).toBe(2);

    // Verify search is cleared and disclosures are closed after adding component
    await page.keyboard.press("Slash");
    await sidebarSearchInput.clear();
    await expect(sidebarSearchInput).toHaveValue("");
    await expect(page.getByTestId("input_outputChat Input")).not.toBeVisible();

    await expect(sidebarSearchInput).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(sidebarSearchInput).not.toBeFocused();
    await expect(page.getByTestId("input_outputChat Input")).not.toBeVisible();
  },
);

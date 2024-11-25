import { expect, test } from "@playwright/test";

test(
  "user can search and add components using keyboard shortcuts",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    // Navigate to homepage and handle initial modal
    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    let modalCount = 0;
    try {
      const modalTitleElement = await page?.getByTestId("modal-title");
      if (modalTitleElement) {
        modalCount = await modalTitleElement.count();
      }
    } catch (error) {
      modalCount = 0;
    }

    while (modalCount === 0) {
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    // Start with blank flow
    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 1000,
    });

    // Press "/" to activate search
    await page.keyboard.press("/");

    // Verify search is focused and disclosures are closed when search is empty
    await expect(page.getByTestId("sidebar-search-input")).toBeFocused({
      timeout: 1000,
    });
    await expect(page.getByTestId("inputsChat Input")).not.toBeVisible();

    // Type "chat" to search for chat components
    await page.keyboard.type("chat");

    await expect(page.getByTestId("inputsChat Input")).toBeVisible({
      timeout: 1000,
    });

    // Verify disclosures open when search has content
    await expect(page.getByTestId("inputsChat Input")).toBeVisible();

    // Press Tab to focus first result
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");

    // Verify some expected chat-related components are visible
    await expect(page.getByTestId("inputsChat Input")).toBeVisible();
    await expect(page.getByTestId("outputsChat Output")).toBeVisible();

    // Press Space to select the component
    await page.keyboard.press("Space");

    // Verify component was added to flow
    const addedComponent = await page.locator(".react-flow__node").first();
    await expect(addedComponent).toBeVisible();

    // Clear search input and verify disclosures are closed
    await page.getByTestId("sidebar-search-input").clear();
    await expect(page.getByTestId("inputsChat Input")).not.toBeVisible();

    // Test Enter key selection
    await page.keyboard.press("/");
    await page.keyboard.type("prompt");

    // Verify disclosures open with new search
    await expect(page.getByTestId("promptsPrompt")).toBeVisible();

    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Enter");

    // Verify second component was added
    const nodeCount = await page.locator(".react-flow__node").count();
    expect(nodeCount).toBe(2);

    // Verify search is cleared and disclosures are closed after adding component
    await page.keyboard.press("/");
    await page.getByTestId("sidebar-search-input").clear();
    await expect(page.getByTestId("sidebar-search-input")).toHaveValue("");
    await expect(page.getByTestId("inputsChat Input")).not.toBeVisible();

    await expect(page.getByTestId("sidebar-search-input")).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("sidebar-search-input")).not.toBeFocused();
    await expect(page.getByTestId("inputsChat Input")).not.toBeVisible();
  },
);

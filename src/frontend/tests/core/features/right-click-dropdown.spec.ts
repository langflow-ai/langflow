import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user can open component dropdown menu by right-clicking on nodes",
  { tag: ["@release", "@components", "@dropdown", "@right-click"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Start with a basic template that has multiple components
    if (await page.getByTestId("components-btn").isVisible()) {
      await page.getByTestId("side_nav_options_all-templates").click();
      await page.getByRole("heading", { name: "Basic Prompting" }).click();
    }

    await page.getByTestId("template-get-started-card-basic-prompting").click();

    // Wait for the flow to load
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 3000,
    });

    // Test 1: Right-click on Chat Input component should open dropdown immediately (single click)
    const chatInputComponent = page.getByText("Chat Input").first();

    // First, click somewhere else to ensure no component is selected
    await page.click("body", { position: { x: 100, y: 100 } });
    await page.waitForTimeout(500);

    // Single right-click on the Chat Input component should immediately open dropdown
    await chatInputComponent.click({ button: "right" });

    // Wait for and verify the dropdown menu appears immediately after single right-click
    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 2000,
    });

    // Verify the dropdown menu is visible and contains expected options
    const dropdown = page.locator('[data-testid="more-options-modal"]').first();
    await expect(dropdown).toBeVisible();

    // Verify the right-clicked component is now selected/focused (like a left-click would do)
    // The component should be visually selected and have the toolbar visible
    // Since we right-clicked, both the dropdown menu AND regular selection should be active
    const chatInputNode = page
      .locator('[data-testid="div-generic-node"]')
      .first();
    await expect(chatInputNode).toBeVisible();

    // Test 2: Verify dropdown contains expected menu items
    // Check for Save option
    const saveOption = page.getByTestId("save-button-modal");
    await expect(saveOption).toBeVisible();

    // Check for Copy option
    const copyOption = page.getByTestId("copy-button-modal").first();
    await expect(copyOption).toBeVisible();

    // Check for Delete option (should be at the bottom with red styling)
    const deleteOption = page.locator('text="Delete"').last();
    await expect(deleteOption).toBeVisible();

    // Test 3: Verify clicking on dropdown option works
    await saveOption.click();

    // Handle the save dialog if it appears
    if (await page.getByTestId("replace-button").isVisible()) {
      await page.getByTestId("replace-button").click();
    }

    // Verify the dropdown closes after selection
    await page.waitForTimeout(1000);
    await expect(saveOption).not.toBeVisible();

    // Test 4: Test right-click on different component
    const promptComponent = page.getByText("Prompt").first();

    // Right-click on the Prompt component
    await promptComponent.click({ button: "right" });

    // Verify dropdown opens for the new component
    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 2000,
    });

    const newDropdown = page
      .locator('[data-testid="more-options-modal"]')
      .first();
    await expect(newDropdown).toBeVisible();
  },
);

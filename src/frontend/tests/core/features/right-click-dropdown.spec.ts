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

    // Wait for the flow to load
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 3000,
    });

    // Test 1: Right-click on Chat Input component should open dropdown
    const chatInputComponent = page.getByText("Chat Input").first();

    // First, click somewhere else to ensure no component is selected
    await page.click("body", { position: { x: 100, y: 100 } });
    await page.waitForTimeout(500);

    // Right-click on the Chat Input component
    await chatInputComponent.click({ button: "right" });

    // Wait for and verify the dropdown menu appears
    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 2000,
    });

    // Verify the dropdown menu is visible and contains expected options
    const dropdown = page.locator('[data-testid="more-options-modal"]').first();
    await expect(dropdown).toBeVisible();

    // Test 2: Verify dropdown contains expected menu items
    // Check for Save option
    const saveOption = page.getByTestId("save-button-modal");
    await expect(saveOption).toBeVisible();

    // Check for Copy option
    const copyOption = page.getByTestId("copy-button-modal");
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
    await expect(dropdown).not.toBeVisible();

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

    // Test 5: Verify clicking elsewhere closes the dropdown
    await page.click("body", { position: { x: 100, y: 100 } });
    await page.waitForTimeout(500);

    // Dropdown should no longer be visible
    await expect(newDropdown).not.toBeVisible();

    // Test 6: Verify Escape key closes the dropdown
    await promptComponent.click({ button: "right" });
    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 2000,
    });

    const escapeTestDropdown = page
      .locator('[data-testid="more-options-modal"]')
      .first();
    await expect(escapeTestDropdown).toBeVisible();

    // Press Escape key
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);

    // Dropdown should close
    await expect(escapeTestDropdown).not.toBeVisible();

    // Test 7: Verify right-click works when component is already selected
    await chatInputComponent.click(); // Select the component first

    // Wait for selection toolbar to appear
    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 1000,
    });

    // Right-click on the same selected component
    await chatInputComponent.click({ button: "right" });

    // The dropdown should still be functional
    await page.waitForTimeout(500);
    const selectedDropdown = page
      .locator('[data-testid="more-options-modal"]')
      .first();
    await expect(selectedDropdown).toBeVisible();

    // Test one more interaction to confirm it works
    await copyOption.click();
    await page.waitForTimeout(500);
    await expect(selectedDropdown).not.toBeVisible();
  },
);

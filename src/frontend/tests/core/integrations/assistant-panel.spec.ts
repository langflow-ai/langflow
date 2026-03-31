import { test, expect } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("Assistant Panel UI", { tag: ["@release"] }, () => {
  test("should open and close from canvas controls", async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    // Panel should not be visible initially
    await expect(page.getByTestId("assistant-panel")).not.toBeVisible();

    // Open assistant panel
    await page.getByTestId("assistant-button").click();
    await expect(page.getByTestId("assistant-panel")).toBeVisible();

    // Verify core UI elements
    await expect(page.getByText("Langflow Assistant")).toBeVisible();
    await expect(page.getByTestId("assistant-input-textarea")).toBeVisible();
    await expect(page.getByTestId("assistant-model-selector")).toBeVisible();
    await expect(page.getByTestId("assistant-new-session")).toBeDisabled();

    // Toggle via assistant button (close)
    await page.getByTestId("assistant-button").click();
    await expect(page.getByTestId("assistant-panel")).not.toBeVisible();

    // Toggle via assistant button (open again)
    await page.getByTestId("assistant-button").click();
    await expect(page.getByTestId("assistant-panel")).toBeVisible();

    // Toggle via assistant button (close again)
    await page.getByTestId("assistant-button").click();
    await expect(page.getByTestId("assistant-panel")).not.toBeVisible();
  });
});

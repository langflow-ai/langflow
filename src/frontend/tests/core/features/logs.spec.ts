import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { selectGptModel } from "../../utils/select-gpt-model";

test(
  "should able to see and interact with logs",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await expect(page.getByTestId(/.*rf__node.*/).first()).toBeVisible({
      timeout: 3000,
    });
    let outdatedComponents = await page.getByTestId("update-button").count();

    while (outdatedComponents > 0) {
      await page.getByTestId("update-button").first().click();
      outdatedComponents = await page.getByTestId("update-button").count();
    }

    let filledApiKey = await page.getByTestId("remove-icon-badge").count();
    while (filledApiKey > 0) {
      await page.getByTestId("remove-icon-badge").first().click();
      filledApiKey = await page.getByTestId("remove-icon-badge").count();
    }

    await page.getByText("Logs").click();
    await page.getByText("No Data Available", { exact: true }).isVisible();
    await page.keyboard.press("Escape");

    const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
    const isApiKeyInputVisible = await apiKeyInput.isVisible();

    if (isApiKeyInputVisible) {
      await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
    }

    await selectGptModel(page);

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 1000,
    });
    await page.getByTestId("button_run_chat output").first().click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("Logs").click();

    // Verify the new column headers are present (inside the dialog)
    const dialog = page.getByLabel("Dialog");
    await expect(dialog.getByText("Timestamp", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Component", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Target", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Inputs", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Outputs", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Status", { exact: true })).toBeVisible();

    // Verify there are log entries (grid cells)
    await expect(dialog.getByRole("gridcell").first()).toBeVisible();

    // Verify success status badge is displayed (scoped to dialog)
    await expect(dialog.locator("text=success").first()).toBeVisible();

    await page.keyboard.press("Escape");

    await page.getByTestId("user-profile-settings").first().click();
    await page.getByText("Settings", { exact: true }).click();

    await page.getByText("Messages", { exact: true }).click();
    await expect(page.getByText("index", { exact: true }).last()).toBeVisible();
    await expect(page.getByText("timestamp", { exact: true })).toBeVisible();
    await expect(page.getByText("flow_id", { exact: true })).toBeVisible();
    await expect(page.getByText("source", { exact: true })).toBeVisible();
    await expect(page.getByText("target", { exact: true })).toBeVisible();
    await expect(page.getByText("vertex_id", { exact: true })).toBeVisible();
    await expect(page.getByText("status", { exact: true })).toBeVisible();
    await expect(page.getByText("error", { exact: true })).toBeVisible();
    await expect(page.getByText("outputs", { exact: true })).toBeVisible();
    await expect(page.getByText("inputs", { exact: true })).toBeVisible();

    await expect(page.getByRole("gridcell").first()).toBeVisible();
  },
);

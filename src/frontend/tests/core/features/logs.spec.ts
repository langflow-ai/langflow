import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

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

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("gpt-4o-1-option").click();

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
    await page.getByRole("gridcell").first().isVisible();

    // Verify success status badge is displayed
    await expect(page.locator("text=success").first()).toBeVisible();

    await page.keyboard.press("Escape");

    await page.getByTestId("user-profile-settings").first().click();
    await page.getByText("Settings", { exact: true }).click();

    await page.getByText("Messages", { exact: true }).click();
    await page.getByText("index", { exact: true }).last().isVisible();
    await page.getByText("timestamp", { exact: true }).isVisible();
    await page.getByText("flow_id", { exact: true }).isVisible();
    await page.getByText("source", { exact: true }).isVisible();
    await page.getByText("target", { exact: true }).isVisible();
    await page.getByText("vertex_id", { exact: true }).isVisible();
    await page.getByText("status", { exact: true }).isVisible();
    await page.getByText("error", { exact: true }).isVisible();
    await page.getByText("outputs", { exact: true }).isVisible();
    await page.getByText("inputs", { exact: true }).isVisible();

    await page.getByRole("gridcell").first().isVisible();
  },
);

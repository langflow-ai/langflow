import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "Flow logs modal should handle pagination correctly",
  { tag: ["@logs"] },
  async ({ page }) => {
    // Start with a blank flow
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    // Create multiple log entries by running a component multiple times
    await page.getByTestId("disclosure-input / output").click();
    await page.waitForSelector('[data-testid="input_outputText Input"]', {
      timeout: 3000,
      state: "visible",
    });

    // Add a text input component
    await page
      .getByTestId("input_outputText Input")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-text-input").click();
      });

    // Run the component multiple times to generate logs
    for (let i = 0; i < 5; i++) {
      // Change the input value for each run to create distinct log entries
      await page
        .getByTestId("textarea_str_input_value")
        .fill(`Test input ${i + 1}`);
      await page.getByTestId("button_run_text input").click();

      // Wait for successful run before continuing to next iteration
      await page.waitForSelector("text=built successfully", { timeout: 30000 });

      // Wait a bit between runs to ensure distinct timestamps
      await page.waitForTimeout(1000);
    }

    // Open the logs modal
    await page.getByTestId("flow-logs-modal-button").click();

    // Wait for logs modal to appear
    await page.waitForSelector("text=Logs", {
      timeout: 3000,
      state: "visible",
    });

    // Check if logs table appears
    const logsTable = page.locator(".ag-flow-logs-table");
    await expect(logsTable).toBeVisible();

    // Check for multiple rows in the table
    const rows = page.locator(".ag-row");
    await expect(rows).toHaveCount(5);

    // Verify timestamps are sorted in descending order (newest first)
    const timestamps = await page
      .locator(".ag-row td:nth-child(2)")
      .allTextContents();

    // Convert timestamps to Date objects for comparison
    const dates = timestamps.map((ts) => new Date(ts));

    // Verify the sorting is in descending order
    for (let i = 0; i < dates.length - 1; i++) {
      expect(dates[i].getTime()).toBeGreaterThanOrEqual(dates[i + 1].getTime());
    }

    // Change page size if pagination controls are visible
    const paginatorVisible = await page
      .locator('.ag-flow-logs-table + div [data-testid="paginator"]')
      .isVisible();

    if (paginatorVisible) {
      // Click on the page size dropdown
      await page.locator('[data-testid="paginator-select"]').click();

      // Select a different page size
      await page.locator('[data-testid="paginator-option-12"]').click();

      // Verify the page size changed
      await expect(
        page.locator('[data-testid="paginator-select"]'),
      ).toContainText("12");
    }
  },
);

test(
  "Flow logs modal should show both success and error logs",
  { tag: ["@logs"] },
  async ({ page }) => {
    // Start with a blank flow
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    // Add a text input component for success logs
    await page.getByTestId("disclosure-input / output").click();
    await page.waitForSelector('[data-testid="input_outputText Input"]', {
      timeout: 3000,
      state: "visible",
    });

    await page
      .getByTestId("input_outputText Input")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-text-input").click();
        await page.getByTestId("textarea_str_input_value").fill("Success test");
        await page.getByTestId("button_run_text input").click();
      });

    // Wait for successful run
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    // Add a Custom Component that will generate an error
    await page.getByTestId("sidebar-custom-component-button").click();

    await page.waitForSelector('[data-testid="div-generic-node"]', {
      timeout: 3000,
    });

    // Set up the custom component with code that will cause an error
    await page.getByTestId("code-button-modal").click();

    const errorCode = `from langflow.custom import Component
from langflow.io import Output

class ErrorComponent(Component):
    display_name = "Error Component"

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self):
        raise ValueError('Error test')`;

    await page.locator(".ace_content").click();
    await page.keyboard.press("ControlOrMeta+A");
    await page.locator("textarea").fill(errorCode);
    await page.getByText("Check & Save").click();

    // Wait for the component to be ready
    await page.waitForTimeout(1000);

    // Run the component to generate error logs
    await page.getByTestId("button_run_error component").click();

    // Wait for error notification
    await page.waitForSelector("text=Error", { timeout: 30000 });

    // Open the logs modal
    await page.getByTestId("flow-logs-modal-button").click();

    // Wait for logs modal to appear
    await page.waitForSelector("text=Logs", {
      timeout: 3000,
      state: "visible",
    });

    // Verify both successful and error log entries exist
    const successRow = page
      .locator(".ag-row")
      .filter({ has: page.getByText("SUCCESS") });
    await expect(successRow).toBeVisible();

    const errorRow = page
      .locator(".ag-row")
      .filter({ has: page.getByText("ERROR") });
    await expect(errorRow).toBeVisible();

    // Verify error message is displayed
    const errorText = page.getByText("Error").first();
    await expect(errorText).toBeVisible();
  },
);

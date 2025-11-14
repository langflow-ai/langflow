import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "Simple Agents starter template should display successful log entries after flow run",
  { tag: ["@logs", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    // Navigate to Simple Agent template
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Simple Agent" }).first().click();

    // Wait for canvas to load
    await page.waitForLoadState("networkidle");
    await page.waitForSelector('[data-testid="div-generic-node"]', {
      timeout: 15000,
      state: "visible",
    });

    // Setup API keys
    await initialGPTsetup(page);

    // Run the flow by opening playground and sending a message
    await page.getByTestId("playground-btn-flow-io").click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 3000,
      state: "visible",
    });

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("What is todays date?");

    await page.getByTestId("button-send").last().click();

    // Wait for flow execution to complete
    const stopButton = page.getByRole("button", { name: "Stop" });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });

    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 120000 });
    }

    // Close playground to access flow logs button
    await page.getByRole("button", { name: "Close" }).first().click();
    await page.waitForTimeout(1000);

    // Open the logs modal
    await page.getByTestId("canvas_controls").click();

    // Wait for logs modal to appear
    await page.waitForSelector("text=Logs", {
      timeout: 3000,
      state: "visible",
    });

    // Verify the logs modal content
    const logsHeader = page.getByTestId("icon-ScrollText");
    await expect(logsHeader).toBeVisible();

    // Check if logs table appears
    const logsTable = page.locator(".ag-flow-logs-table");
    await expect(logsTable).toBeVisible();

    // Verify successful status entry exists
    const statusCell = page
      .locator(".ag-row")
      .filter({ has: page.getByText("SUCCESS") })
      .first();

    await expect(statusCell).toBeVisible();

    // Verify that we have log entries from the agent execution
    const logRows = page.locator(".ag-row");
    const logRowCount = await logRows.count();
    expect(logRowCount).toBeGreaterThan(0);
  },
);

test(
  "Simple Agents starter template should display error log entries when API key is missing",
  { tag: ["@logs", "@starter-projects"] },
  async ({ page }) => {
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    // Navigate to Simple Agent template
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Simple Agent" }).first().click();

    // Wait for canvas to load
    await page.waitForLoadState("networkidle");
    await page.waitForSelector('[data-testid="div-generic-node"]', {
      timeout: 15000,
      state: "visible",
    });

    // Explicitly do NOT set up API keys - leave them empty to test failure scenario
    // This means we skip the initialGPTsetup(page) call

    // Run the flow by opening playground and sending a message
    await page.getByTestId("playground-btn-flow-io").click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 3000,
      state: "visible",
    });

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("What is todays date?");

    await page.getByTestId("button-send").last().click();

    // Wait for flow execution to fail (should be faster than success)
    const stopButton = page.getByRole("button", { name: "Stop" });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });

    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 120000 });
    }

    // Close playground to access flow logs button
    await page.getByRole("button", { name: "Close" }).first().click();
    await page.waitForTimeout(1000);

    // Open the logs modal
    await page.getByTestId("canvas_controls").click();

    // Wait for logs modal to appear
    await page.waitForSelector("text=Logs", {
      timeout: 3000,
      state: "visible",
    });

    // Verify the logs modal content
    const logsHeader = page.getByTestId("icon-ScrollText");
    await expect(logsHeader).toBeVisible();

    // Check if logs table appears
    const logsTable = page.locator(".ag-flow-logs-table");
    await expect(logsTable).toBeVisible();

    // Verify error status entry exists
    const statusCell = page
      .locator(".ag-row")
      .filter({ has: page.getByText("ERROR") })
      .first();

    await expect(statusCell).toBeVisible();

    // Verify that we have log entries from the agent execution
    const logRows = page.locator(".ag-row");
    const logRowCount = await logRows.count();
    expect(logRowCount).toBeGreaterThan(0);
  },
);

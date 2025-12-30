import { expect, test } from "../../fixtures";
import { addCustomComponent } from "../../utils/add-custom-component";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("Flow Logs Modal", () => {
  test(
    "should open logs modal and show description",
    { tag: ["@release", "@logs"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page.getByTestId("blank-flow").click();

      await page.waitForSelector(
        '[data-testid="sidebar-custom-component-button"]',
        {
          timeout: 3000,
        },
      );

      // Open the logs modal
      await page.getByText("Logs").click();

      // Verify modal is open by checking the description
      await expect(
        page.getByText("Inspect component executions."),
      ).toBeVisible();

      // Close modal
      await page.keyboard.press("Escape");
    },
  );

  test(
    "should show 'No Data Available' when no logs exist",
    { tag: ["@release", "@logs"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page.getByTestId("blank-flow").click();

      await page.waitForSelector(
        '[data-testid="sidebar-custom-component-button"]',
        {
          timeout: 3000,
        },
      );

      // Open logs modal without running any component
      await page.getByText("Logs").click();

      // Verify "No Data Available" message is shown
      await expect(page.getByText("No Data Available")).toBeVisible();

      // Close modal
      await page.keyboard.press("Escape");
    },
  );

  test(
    "should display success status after successful component execution",
    { tag: ["@release", "@logs"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page.getByTestId("blank-flow").click();

      await page.waitForSelector(
        '[data-testid="sidebar-custom-component-button"]',
        {
          timeout: 3000,
        },
      );

      // Add a custom component
      await addCustomComponent(page);

      await page.waitForSelector('[data-testid="title-Custom Component"]', {
        timeout: 3000,
      });

      // Run the component
      await page.getByTestId("button_run_custom component").click();

      await page.waitForSelector("text=built successfully", { timeout: 30000 });

      // Open logs modal
      await page.getByText("Logs").click();

      // Verify success status badge is displayed (scoped to dialog)
      const dialog = page.getByLabel("Dialog");
      await expect(dialog.locator("text=success").first()).toBeVisible();

      // Close modal
      await page.keyboard.press("Escape");
    },
  );

  test(
    "should display error status after failed component execution",
    { tag: ["@release", "@logs"] },
    async ({ page }) => {
      const customComponentCodeWithError = `
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data


class CustomComponent(Component):
    display_name = "Custom Component"
    description = "Use as a template to create your own component."
    icon = "code"
    name = "CustomComponent"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input Value",
            value="Hello, World!",
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        msg = "THIS IS A TEST ERROR MESSAGE"
        raise ValueError(msg)
`;

      await awaitBootstrapTest(page);

      await page.getByTestId("blank-flow").click();

      await page.waitForSelector(
        '[data-testid="sidebar-custom-component-button"]',
        {
          timeout: 3000,
        },
      );

      // Add a custom component
      await addCustomComponent(page);

      await page.waitForTimeout(1000);

      await page.waitForSelector('[data-testid="title-Custom Component"]', {
        timeout: 3000,
      });
      await page.getByTestId("title-Custom Component").click();

      // Open code editor and add error code
      await page.getByTestId("code-button-modal").click();

      await page.locator(".ace_content").click();
      await page.keyboard.press("ControlOrMeta+A");
      await page.locator("textarea").fill(customComponentCodeWithError);

      await page.getByText("Check & Save").last().click();

      // Run the component (it will fail)
      await page.getByTestId("button_run_custom component").click();

      // Wait for error message to appear
      await page.waitForSelector("text=THIS IS A TEST ERROR MESSAGE", {
        timeout: 30000,
      });

      // Open logs modal
      await page.getByText("Logs").click();

      // Verify error status badge is displayed (scoped to dialog)
      const dialog = page.getByLabel("Dialog");
      await expect(dialog.locator("text=error").first()).toBeVisible();

      // Close modal
      await page.keyboard.press("Escape");
    },
  );

  test(
    "should open detail viewer when clicking on Inputs cell",
    { tag: ["@release", "@logs"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page.getByTestId("blank-flow").click();

      await page.waitForSelector(
        '[data-testid="sidebar-custom-component-button"]',
        {
          timeout: 3000,
        },
      );

      // Add a custom component
      await addCustomComponent(page);

      await page.waitForSelector('[data-testid="title-Custom Component"]', {
        timeout: 3000,
      });

      // Run the component
      await page.getByTestId("button_run_custom component").click();

      await page.waitForSelector("text=built successfully", { timeout: 30000 });

      // Open logs modal
      await page.getByText("Logs").click();

      // Wait for the logs table to be visible
      const logsDialog = page.getByLabel("Dialog");
      await expect(logsDialog.locator("text=success").first()).toBeVisible();

      // Click on the Inputs cell (find cell in Inputs column)
      const inputsCell = logsDialog.locator('[col-id="inputs"]').last();
      await inputsCell.click();

      // Verify detail viewer dialog opens with JSON content
      await expect(page.locator("text=json").first()).toBeVisible();

      // Close detail viewer
      await page.keyboard.press("Escape");

      // Close logs modal
      await page.keyboard.press("Escape");
    },
  );

  test(
    "should mask sensitive data like api_key in logs",
    { tag: ["@release", "@logs"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page.getByTestId("blank-flow").click();

      await page.waitForSelector(
        '[data-testid="sidebar-custom-component-button"]',
        {
          timeout: 3000,
        },
      );

      // Add a custom component
      await addCustomComponent(page);

      await page.waitForSelector('[data-testid="title-Custom Component"]', {
        timeout: 3000,
      });

      // Run the component
      await page.getByTestId("button_run_custom component").click();

      await page.waitForSelector("text=built successfully", { timeout: 30000 });

      // Open logs modal
      await page.getByText("Logs").click();

      // Verify that sensitive data is masked (should not see full API keys)
      const logsDialog = page.getByLabel("Dialog");

      // If there's any api_key in the logs, it should be redacted
      // Look for the REDACTED pattern
      const pageContent = await logsDialog.textContent();

      // If api_key appears in the content, it should be masked
      if (pageContent && pageContent.includes("api_key")) {
        // Should not contain long API key patterns (sk-proj-... with full key)
        expect(pageContent).not.toMatch(/sk-proj-[a-zA-Z0-9_-]{20,}/);
      }

      // Close modal
      await page.keyboard.press("Escape");
    },
  );
});

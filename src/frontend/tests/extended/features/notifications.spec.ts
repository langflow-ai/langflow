import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "User should be able to interact notifications tab",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="disclosure-input / output"]', {
      timeout: 3000,
      state: "visible",
    });

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
        await page.getByTestId("button_run_text input").click();
      });

    await page.waitForSelector("text=Running", {
      timeout: 30000,
      state: "visible",
    });

    await page.waitForSelector("text=built successfully", { timeout: 30000 });
    await page.getByTestId("notification_button").click();

    // Add explicit waits before checking visibility
    await page.waitForSelector('[data-testid="icon-Trash2"]', {
      timeout: 3000,
      state: "visible",
    });

    // Then check visibility
    const notificationsText = page
      .getByText("Notifications", { exact: true })
      .last();
    await expect(notificationsText).toBeVisible();

    const trashIcon = page.getByTestId("icon-Trash2").last();
    await expect(trashIcon).toBeVisible();

    const builtSuccessfullyText = page
      .getByText("Flow built successfully", { exact: true })
      .last();
    await expect(builtSuccessfullyText).toBeVisible();
  },
);

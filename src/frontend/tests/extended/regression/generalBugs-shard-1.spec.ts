import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import { selectStarterTemplate } from "../../utils/flow/select-starter-template";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";

test(
  "should delete rows from table message",
  { tag: ["@release"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await awaitBootstrapTest(page);

    await selectStarterTemplate(page, TEXTS.templateBasicPrompting);
    await configureLoopbackOpenAI(page);

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000,
    });

    await page.getByTestId("user-profile-settings").click();

    await page.waitForSelector('text="Settings"');
    await page.getByText(TEXTS.settings).last().click();

    await page.waitForSelector('text="Messages"');
    await page.getByText("Messages").last().click();

    await page.waitForSelector(".ag-checkbox-input");
    await page.locator(".ag-checkbox-input").first().click();

    await page.waitForSelector('[data-testid="icon-Trash2"]:first-child');
    await page.getByTestId("icon-Trash2").first().click();

    await page.waitForSelector("text=No Data Available", { timeout: 30000 });
    await expect(page.getByText("No Data Available")).toBeVisible();
  },
);

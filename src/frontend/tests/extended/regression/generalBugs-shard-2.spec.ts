import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "should use webhook component on API",
  {
    tag: ["@release"],
  },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("webhook");

    await page.waitForSelector('[data-testid="dataWebhook"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("dataWebhook")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await adjustScreenView(page);

    // wait for the update to be applied
    await page.waitForTimeout(1000);

    await page.getByText("API", { exact: true }).click();

    await page.getByText("Webhook cURL", { exact: true }).click();
    await page.getByRole("tab", { name: "Webhook cURL" }).click();

    await page.getByTestId("icon-Copy").last().click();

    const handle = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent = await handle.jsonValue();
    expect(clipboardContent.length).toBeGreaterThan(0);
    expect(clipboardContent).toContain("curl -X POST");
    expect(clipboardContent).toContain("webhook");
    await page.getByRole("tab", { name: "Tweaks" }).click();
  },
);

import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

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
    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

    let modalCount = 0;
    try {
      const modalTitleElement = await page?.getByTestId("modal-title");
      if (modalTitleElement) {
        modalCount = await modalTitleElement.count();
      }
    } catch (error) {
      modalCount = 0;
    }

    while (modalCount === 0) {
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

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

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

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

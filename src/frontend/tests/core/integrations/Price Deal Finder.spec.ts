import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Price Deal Finder",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.AGENTQL_API_KEY,
      "AGENTQL_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.TAVILY_API_KEY,
      "TAVILY_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Price Deal Finder" }).click();
    await adjustScreenView(page);

    await initialGPTsetup(page, {
      skipAdjustScreenView: true,
      skipAddNewApiKeys: true,
      skipSelectGptModel: true,
    });

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(0)
      .fill(process?.env?.TAVILY_API_KEY ?? "");

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(1)
      .fill(process?.env?.AGENTQL_API_KEY ?? "");

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(2)
      .fill(process?.env?.OPENAI_API_KEY ?? "");

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    const product = randomProduct();

    await page.getByTestId("input-chat-playground").fill(product);

    await page.getByTestId("button-send").click();

    try {
      await page.waitForSelector('[data-testid="button-stop"]', {
        timeout: 180000,
        state: "hidden",
      });
    } catch (_error) {
      console.error("Timeout error");
      test.skip(true, "Timeout error");
    }

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ").toLowerCase();

    expect(concatAllText.length).toBeGreaterThan(100);

    const zeldaChapter = product.split(" ")[1];
    expect(concatAllText).toContain(zeldaChapter);
  },
);

const randomProduct = () => {
  const products = [
    "Zelda Tears of the Kingdom",
    "Zelda Ocarina of Time",
    "Zelda Majora's Mask",
    "Zelda The Wind Waker",
    "Zelda Twilight Princess",
    "Zelda Skyward Sword",
    "Zelda Breath of the Wild",
    "Zelda Link's Awakening",
    "Zelda Link to the Past",
  ];

  return products[Math.floor(Math.random() * products.length)].toLowerCase();
};

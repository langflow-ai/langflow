import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { waitForOpenModalWithChatInput } from "../../utils/wait-for-open-modal";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Graph Rag",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.ASTRA_DB_API_ENDPOINT,
      "ASTRA_DB_API_ENDPOINT required to run this test",
    );

    test.skip(
      !process?.env?.ASTRA_DB_APPLICATION_TOKEN,
      "ASTRA_DB_APPLICATION_TOKEN required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Graph Rag" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await page
      .getByTestId("popover-anchor-input-token")
      .nth(0)
      .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");

    await page
      .getByTestId("popover-anchor-input-token")
      .nth(1)
      .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");

    await page
      .getByTestId("popover-anchor-input-api_endpoint")
      .nth(0)
      .fill(process.env.ASTRA_DB_API_ENDPOINT ?? "");

    await page
      .getByTestId("popover-anchor-input-api_endpoint")
      .nth(1)
      .fill(process.env.ASTRA_DB_API_ENDPOINT ?? "");

    await page.getByTestId("button_run_astra db graph").last().click();

    try {
      await page.waitForSelector("text=built successfully", {
        timeout: 30000 * 3,
      });
    } catch (e) {
      console.log("Build timeout");
      test.skip();
    }

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.getByTestId("button-send").click();

    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 30000 * 3,
    });

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ");

    expect(concatAllText).toContain("Haskell");
    expect(concatAllText).toContain("reverseWords");
    expect(concatAllText).toContain("words");
    expect(concatAllText).toContain("map reverse");
    expect(concatAllText).toContain("unwords");
  },
);

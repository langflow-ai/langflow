import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import uaParser from "ua-parser-js";

test(
  "Simple Agent",
  { tag: ["@release", "@starter-project"] },
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

    const getUA = await page.evaluate(() => navigator.userAgent);
    const userAgentInfo = uaParser(getUA);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Simple Agent" }).first().click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    let outdatedComponents = await page
      .getByTestId("icon-AlertTriangle")
      .count();

    while (outdatedComponents > 0) {
      await page.getByTestId("icon-AlertTriangle").first().click();
      outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
    }

    let filledApiKey = await page.getByTestId("remove-icon-badge").count();
    while (filledApiKey > 0) {
      await page.getByTestId("remove-icon-badge").first().click();
      filledApiKey = await page.getByTestId("remove-icon-badge").count();
    }

    await page
      .getByTestId("popover-anchor-input-api_key")
      .fill(process.env.OPENAI_API_KEY ?? "");

    await page.getByTestId("fit_view").click();

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("gpt-4o-1-option").click();

    await page.getByTestId("button_run_chat output").last().click();

    await page.waitForSelector("text=built successfully", {
      timeout: 10000 * 60 * 3,
    });

    await page.getByTestId("playground-btn-flow-io").click();

    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();

    const concatAllText = textContents.join(" ").toLowerCase();

    expect(concatAllText).toContain("hello! how can i assist you today?");
    expect(concatAllText.length).toBeGreaterThan(20);
  },
);

import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { waitForOpenModalWithChatInput } from "../../utils/wait-for-open-modal";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Market Research",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
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

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Market Research" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);
    await page
      .getByTestId(/rf__node-TavilySearchComponent-[A-Za-z0-9]{5}/)
      .getByTestId("popover-anchor-input-api_key")
      .nth(0)
      .fill(process.env.TAVILY_API_KEY ?? "");

    //* TODO: Remove these 5 steps once the template is updated *//
    await page.getByTestId("dropdown-output-openaimodel").click();

    await page
      .getByTestId("dropdown-item-output-openaimodel-language model")
      .click();

    await page
      .getByTestId("handle-structuredoutput-shownode-structured output-right")
      .click();

    await page
      .getByTestId("handle-parser-shownode-data or dataframe-left")
      .click();

    await page.getByTestId("tab_1_stringify").click();

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", {
      timeout: 60000 * 3,
    });

    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page
      .getByText("No input message provided.", { exact: true })
      .last()
      .isVisible();

    await waitForOpenModalWithChatInput(page);

    const textContents = await getAllResponseMessage(page);

    expect(textContents.length).toBeGreaterThan(300);
    expect(textContents).toContain("amazon");
  },
);

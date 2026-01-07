import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
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

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    // Find the Tavily node and fill the API key with retry
    const tavilyNode = page.getByTestId(/rf__node-TavilySearchComponent-/);
    const tavilyApiKeyInput = tavilyNode.getByTestId("popover-anchor-input-api_key");

    const maxRetries = 5;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      await tavilyApiKeyInput.waitFor({ state: "visible", timeout: 10000 });
      await tavilyApiKeyInput.click();
      await tavilyApiKeyInput.clear();
      await tavilyApiKeyInput.fill(process.env.TAVILY_API_KEY ?? "");
      await tavilyApiKeyInput.press("Tab"); // Trigger blur to save value

      // Verify the value was filled
      const value = await tavilyApiKeyInput.inputValue();
      if (value === process.env.TAVILY_API_KEY) {
        break;
      }

      await page.waitForTimeout(500);
    }

    await page
      .getByTestId("handle-parsercomponent-shownode-data or dataframe-left")
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

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

    // Fill Tavily API key - try multiple approaches for robustness
    const tavilyApiKey = process.env.TAVILY_API_KEY ?? "";

    // Approach 1: Direct fill like Instagram Copywriter (most reliable)
    try {
      await page
        .getByTestId(/rf__node-TavilySearchComponent-[A-Za-z0-9]{5}/)
        .getByTestId("popover-anchor-input-api_key")
        .nth(0)
        .fill(tavilyApiKey, { timeout: 10000 });
    } catch {
      // Approach 2: Try without the node prefix, by index
      try {
        const apiKeyInputs = page.getByTestId("popover-anchor-input-api_key");
        const count = await apiKeyInputs.count();
        for (let i = 0; i < count; i++) {
          const input = apiKeyInputs.nth(i);
          const placeholder = await input.getAttribute("placeholder");
          if (
            placeholder?.toLowerCase().includes("tavily") ||
            i === count - 1
          ) {
            await input.fill(tavilyApiKey);
            break;
          }
        }
      } catch {
        // Approach 3: Last resort - fill all api_key inputs with Tavily key
        await page
          .getByTestId("popover-anchor-input-api_key")
          .last()
          .fill(tavilyApiKey);
      }
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

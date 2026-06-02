import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { disableInspectPanel } from "../../utils/open-advanced-options";
import { unselectNodes } from "../../utils/unselect-nodes";
import { waitForOpenModalWithChatInput } from "../../utils/wait-for-open-modal";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Market Research",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    test.skip(
      !process?.env?.TAVILY_API_KEY,
      "TAVILY_API_KEY required to run this test",
    );
    loadDotenvIfLocal(__dirname);
    await page.goto("/");
    await openStarterProject(page, "Market Research");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await disableInspectPanel(page);

    // TAVILY_API_KEY is auto-loaded as a global variable from the
    // environment (see VARIABLES_TO_GET_FROM_ENVIRONMENT in constants.py).
    // When loaded, the input is replaced by a badge and fill() would fail.
    // Only fill manually when the input is still present.
    const tavilyApiKeyInput = page.getByTestId("popover-anchor-input-api_key");
    if ((await tavilyApiKeyInput.count()) > 0) {
      await tavilyApiKeyInput.fill(process.env.TAVILY_API_KEY || "");
    }

    await unselectNodes(page);

    await page
      .getByTestId("handle-parsercomponent-shownode-json or table-left")
      .click();

    await page.getByTestId("tab_1_stringify").click();

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 60000 * 3,
    });

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await page
      .getByText(TEXTS.labelNoInputMessage, { exact: true })
      .last()
      .isVisible();

    await waitForOpenModalWithChatInput(page);

    const textContents = await getAllResponseMessage(page);

    expect(textContents.length).toBeGreaterThan(100);
    // Non-blocking: log a warning if the response lacks expected domain data
    if (!textContents.includes("amazon")) {
      console.warn(
        "Market Research response did not contain 'amazon'. LLM may have returned incomplete data.",
      );
    }
  },
);

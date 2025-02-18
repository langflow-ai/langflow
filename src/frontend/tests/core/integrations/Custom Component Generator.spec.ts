import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { waitForOpenModalWithChatInput } from "../../utils/wait-for-open-modal";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Custom Component Generator",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.ANTHROPIC_API_KEY,
      "ANTHROPIC_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByTestId("template-custom-component-generator").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    try {
      await page
        .getByTestId("anchor-popover-anchor-input-api_key")
        .last()
        .fill(process.env.ANTHROPIC_API_KEY ?? "");
    } catch (e) {
      console.log("There's API already added");
    }

    await page.waitForSelector('[data-testid="dropdown_str_model_name"]', {
      timeout: 5000,
    });

    await page.getByTestId("dropdown_str_model_name").click();

    await page.keyboard.press("Enter");

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.getByText("Playground", { exact: true }).last().click();
    await page
      .getByText("No input message provided.", { exact: true })
      .last()
      .isVisible();

    await waitForOpenModalWithChatInput(page);

    const textContents = await getAllResponseMessage(page);
    expect(textContents.length).toBeGreaterThan(100);
    expect(await page.getByTestId("chat-code-tab").last().isVisible()).toBe(
      true,
    );
    expect(textContents).toContain("langflow");
  },
);

import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { waitForOpenModalWithChatInput } from "../../utils/wait-for-open-modal";
import { unselectNodes } from "../../utils/unselect-nodes";
import { adjustScreenView } from "../../utils/adjust-screen-view";

test(
  "Instagram Copywriter",
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
    await page.getByRole("heading", { name: "Instagram Copywriter" }).click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    // We have to get the rf__node because there are more components with popover-anchor-input-api_key

    await adjustScreenView(page);

    await page.getByText("Tavily AI Search", { exact: true }).last().click();
    const tavily = page
      .getByTestId(/rf__node-TavilySearchComponent-[A-Za-z0-9]{5}/)
      .getByTestId("popover-anchor-input-api_key");

    if ((await tavily.count()) > 0) {
      await tavily.nth(0).fill(process.env.TAVILY_API_KEY ?? "");
    } else {
      await page
        .getByTestId("popover-anchor-input-api_key")
        .fill(process.env.TAVILY_API_KEY ?? "");
    }

    await unselectNodes(page);
    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", {
      timeout: 30000 * 2,
    });

    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page
      .getByText("Create a Langflow post", { exact: true })
      .last()
      .isVisible();

    await waitForOpenModalWithChatInput(page);

    const textContents = await getAllResponseMessage(page);

    expect(textContents.length).toBeGreaterThan(300);
  },
);

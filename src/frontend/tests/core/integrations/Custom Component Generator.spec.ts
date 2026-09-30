import { expect } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Custom Component Generator",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await page.goto("/");

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByTestId("template-custom-component-generator").click();
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await configureLoopbackOpenAI(page);

    await page.getByTestId("playground-btn-flow-io").click();

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill(
        "Create a custom component that can generate a random number between 1 and 100 and is called Langflow Random Number",
      );

    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: TEXTS.stop });
    await stopButton.waitFor({ state: "hidden", timeout: 90_000 });

    const textContents = await getAllResponseMessage(page);
    expect(textContents.length).toBeGreaterThan(100);
    await expect(page.getByTestId("chat-code-tab").last()).toBeVisible();
    expect(textContents.toLowerCase()).toContain("langflow");
  },
);

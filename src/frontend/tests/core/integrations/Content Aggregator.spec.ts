import { expect } from "../../fixtures";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Content Aggregator",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await page.goto("/");
    await openStarterProject(page, "Content Aggregator");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await configureLoopbackOpenAI(page, {
      skipAdjustScreenView: true,
    });

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 3000,
    });

    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("what is langflow?");

    await page.getByTestId("button-send").click();

    await page.waitForSelector("text=Finished", { timeout: 100000 });

    await page.waitForSelector(".markdown", { timeout: 3000 });

    const textContents = await page
      .locator(".markdown")
      .last()
      .allTextContents();

    const concatAllText = textContents.join(" ").toLowerCase();

    expect(concatAllText.length).toBeGreaterThan(30);
    expect(concatAllText).toContain("deterministic");
  },
);

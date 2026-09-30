import { expect } from "../../fixtures";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "SaaS Pricing",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await page.goto("/");
    await openStarterProject(page, "SaaS Pricing");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await configureLoopbackOpenAI(page);

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await page
      .getByText(TEXTS.labelNoInputMessage, { exact: true })
      .last()
      .isVisible();

    await sendPlaygroundMessage(
      page,
      "Price this SaaS: infra 2000, support 1000, dev 3000, margin 30%, 200 subscribers.",
    );

    const textContents = await getAllResponseMessage(page);

    expect(textContents.length).toBeGreaterThan(40);
  },
);

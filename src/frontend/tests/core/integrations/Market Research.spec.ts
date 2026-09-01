import { expect } from "../../fixtures";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Market Research",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await page.goto("/");
    await openStarterProject(page, "Market Research");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await expect(page.getByTestId("title-Agent")).toBeVisible();
    await expect(page.getByTestId("title-Web Search")).toBeVisible();
    await expect(page.getByTestId("title-Structured Output")).toBeVisible();
    await expect(page.getByTestId("title-Parser")).toBeVisible();
    await expect(page.getByTestId("title-Chat Input")).toBeVisible();
    await expect(page.getByTestId("title-Chat Output")).toBeVisible();
  },
);

import { expect } from "../../fixtures";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Sequential Tasks Agents",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await page.goto("/");
    await openStarterProject(page, "Sequential Tasks Agents");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await expect(page.getByTestId("title-Agent")).toHaveCount(3);
    await expect(page.getByTestId("title-Web Search")).toBeVisible();
    await expect(page.getByTestId("title-Chat Output")).toBeVisible();
  },
);

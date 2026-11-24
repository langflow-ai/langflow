import { expect, test } from "../../fixtures";
import { openStarterProject } from "../../utils/flow/open-starter-project";

test(
  "Instagram Copywriter",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await page.goto("/");
    await openStarterProject(page, "Instagram Copywriter");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await expect(page.getByTestId("title-Agent")).toHaveCount(2);
    await expect(page.getByTestId("title-Web Search")).toBeVisible();
    await expect(page.getByTestId("title-Chat Input")).toBeVisible();
    await expect(page.getByTestId("title-Chat Output")).toBeVisible();
  },
);

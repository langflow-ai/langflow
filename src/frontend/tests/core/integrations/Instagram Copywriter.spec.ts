import { expect, test } from "../../fixtures";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "Instagram Copywriter",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await page.goto("/");
    await openStarterProject(page, "Instagram Copywriter");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await expect(page.getByTestId("title-Agent")).toHaveCount(2);
    await expect(page.getByTestId("title-Web Search")).toBeVisible();
    await expect(page.getByTestId("title-Chat Input")).toBeVisible();
    await expect(page.getByTestId("title-Chat Output")).toBeVisible();
  },
);

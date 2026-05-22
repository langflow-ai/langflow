import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";

test(
  "user must be able to create a new flow clicking on New Flow button",
  { tag: ["@release", "@mainpage"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await page.waitForSelector("text=playground", { timeout: 30000 });
    await page.waitForSelector("text=share", { timeout: 30000 });

    await expect(page.getByTestId("button_run_chat output")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("button_run_language model")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("button_run_prompt template")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("button_run_chat input")).toBeVisible({
      timeout: 30000,
    });
  },
);

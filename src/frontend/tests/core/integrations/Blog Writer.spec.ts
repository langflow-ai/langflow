import { expect, test } from "../../fixtures";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { openStarterProject } from "../../utils/flow/open-starter-project";

import { TEXTS } from "../../utils/constants/texts";
withEventDeliveryModes(
  "Blog Writer",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await openStarterProject(page, "Blog Writer");

    await initialGPTsetup(page);

    await page.getByText("URL", { exact: true }).last().click();

    await page
      .getByTestId("inputlist_str_urls_0")
      .nth(0)
      .fill(
        "https://www.natgeokids.com/uk/discover/animals/sea-life/turtle-facts/",
      );

    await page.getByTestId("input-list-plus-btn_urls-0").click();

    await page
      .getByTestId("inputlist_str_urls_1")
      .nth(0)
      .fill("https://www.originaldiving.com/blog/top-ten-turtle-facts");

    await page.getByText("Instructions", { exact: true }).last().click();

    await page
      .getByTestId("textarea_str_input_value")
      .fill(
        "Use the references above for style to write a new blog/tutorial about turtles. Suggest non-covered topics.",
      );

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000 * 3,
    });

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await page
      .getByPlaceholder(
        "No chat input variables found. Click to run your flow.",
        { exact: true },
      )
      .last()
      .isVisible();

    await expect(page.getByText("turtles").last()).toBeVisible();
    await expect(page.getByText("sea").last()).toBeVisible();
    await expect(page.getByText("survival").last()).toBeVisible();
  },
);

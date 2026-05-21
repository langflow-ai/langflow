import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";

test(
  "user must be able to create a new flow clicking on New Flow button",
  { tag: ["@release", "@mainpage"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await awaitBootstrapTest(page);

    await page.getByText("Close").last().click();

    await page.getByTestId("add-project-button").click();

    await page.getByText("New Project").last().click();

    await page.waitForSelector("text=new flow", { timeout: 30000 });

    expect(
      (
        await page.waitForSelector("text=new flow", {
          timeout: 30000,
        })
      ).isVisible(),
    );

    expect(
      await page.waitForSelector("data-testid=new_project_btn_empty_page", {
        timeout: 5000,
        state: "visible",
      }),
    );

    await page.getByTestId("new_project_btn_empty_page").click();

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
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

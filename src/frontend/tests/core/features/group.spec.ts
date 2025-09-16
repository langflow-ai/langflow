import { test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("group node test", () => {
  /// <reference lib="dom"/>
  // TODO: fix this test
  test.skip(
    "group and ungroup updating values",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page.getByTestId("side_nav_options_all-templates").click();
      await page
        .getByRole("heading", { name: "Basic Prompting" })
        .first()
        .click();
      await page.getByTestId("fit_view").first().click();

      await page.getByTestId("title-OpenAI").click();
      await page
        .getByTestId("title-OpenAI")
        .click({ modifiers: ["ControlOrMeta"] });
      await page
        .getByTestId("title-Prompt")
        .click({ modifiers: ["ControlOrMeta"] });
      await page
        .getByTestId("title-OpenAI")
        .click({ modifiers: ["ControlOrMeta"] });

      await page.getByRole("button", { name: "Group" }).click();
      await page.getByTestId("title-Group").click();
      await page.getByTestId("edit-name-description-button").click();
      await page.getByTestId("input-title-Group").first().fill("test");
      await page.getByTestId("save-name-description-button").first().click();
      await page.keyboard.press("ControlOrMeta+g");
      await page.getByTestId("title-OpenAI").isVisible();
      await page.getByTestId("title-Prompt").isVisible();
    },
  );
});

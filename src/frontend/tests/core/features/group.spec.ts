import { test } from "@playwright/test";

test.describe("group node test", () => {
  /// <reference lib="dom"/>
  test("group and ungroup updating values", async ({ page }) => {
    await page.goto("/");

    let modalCount = 0;
    try {
      const modalTitleElement = await page?.getByTestId("modal-title");
      if (modalTitleElement) {
        modalCount = await modalTitleElement.count();
      }
    } catch (error) {
      modalCount = 0;
    }

    while (modalCount === 0) {
      await page.getByText("New Flow", { exact: true }).click();
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Basic Prompting" })
      .first()
      .click();
    await page.waitForTimeout(1000);
    await page.getByTestId("fit_view").first().click();

    await page.getByTestId("title-OpenAI").click();
    await page.getByTestId("title-OpenAI").click({ modifiers: ["Control"] });
    await page.getByTestId("title-Prompt").click({ modifiers: ["Control"] });
    await page.getByTestId("title-OpenAI").click({ modifiers: ["Control"] });

    await page.getByRole("button", { name: "Group" }).click();
    await page.getByTestId("title-Group").dblclick();
    await page.getByTestId("input-title-Group").first().fill("test");
    await page.getByTestId("icon-Ungroup").first().click();
    await page.keyboard.press("Control+g");
    await page.getByTestId("title-OpenAI").isVisible();
    await page.getByTestId("title-Prompt").isVisible();
  });
});

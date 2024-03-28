import { expect, test } from "@playwright/test";

test.describe("group node test", () => {
  /// <reference lib="dom"/>
  test("group and ungroup updating values", async ({ page }) => {
    await page.goto("http:localhost:3000/");
    await page.locator('//*[@id="new-project-btn"]').click();

    await page.getByRole("heading", { name: "Data Ingestion" }).click();
    await page.waitForTimeout(2000);
    await page.getByLabel("fit view").click();
    await page.keyboard.down("Control");
    await page
      .getByTestId("title-OpenAIEmbeddings")
      .click({ modifiers: ["Control"] });
    await page.getByTestId("title-URL").click({ modifiers: ["Control"] });
    await page
      .getByTestId("title-Recursive Character Text Splitter")
      .click({ modifiers: ["Control"] });
    await page.keyboard.up("Control");
    await page.getByRole("button", { name: "Group" }).click();
    await page.getByTestId(/input-collection_name_Chroma-.*/).click();
    await page.getByTestId(/input-collection_name_Chroma-.*/).fill("test");
    await page.getByTestId("title-Group").click();
    await page.keyboard.press("Control+g");
    const value = await page.getByTestId("input-collection_name").inputValue();
    expect(value).toBe("test");
  });
});

import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "InputListComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");

    await page.waitForSelector('[data-testid="dataURL"]', {
      timeout: 3000,
    });
    await page
      .getByTestId("dataURL")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-url").click();
      });
    await adjustScreenView(page);

    await page.getByTestId("inputlist_str_urls_0").fill("test test test test");

    // Test cursor position preservation
    const input = page.getByTestId("inputlist_str_urls_0");
    await input.click();
    await input.press("Home"); // Move cursor to start
    await input.press("ArrowRight"); // Move cursor to position 1
    await input.press("ArrowRight"); // Move cursor to position 2
    await input.pressSequentially("XD", { delay: 100 }); // Type at position 2

    const cursorValue = await input.inputValue();
    if (!cursorValue.startsWith("teXD")) {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("inputlist_str_urls_0").fill("test test test test");

    await page.getByTestId("input-list-plus-btn_urls-0").click();

    await page.getByTestId("input-list-plus-btn_urls-0").click();

    await page
      .getByTestId("inputlist_str_urls_1")
      .fill("test1 test1 test1 test1");

    await page
      .getByTestId("inputlist_str_urls_2")
      .fill("test2 test2 test2 test2");

    await page.getByTestId("div-generic-node").click();
    await page.getByTestId("edit-button-modal").last().click();

    const value0 = await page.getByTestId("inputlist_str_urls_0").inputValue();
    const value1 = await page.getByTestId("inputlist_str_urls_1").inputValue();

    const value2 = await page.getByTestId("inputlist_str_urls_2").inputValue();

    if (
      value0 !== "test test test test" ||
      value1 !== "test1 test1 test1 test1" ||
      value2 !== "test2 test2 test2 test2"
    ) {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("input-list-delete-btn-edit_urls-0").click();

    expect(
      await page.getByTestId("input-list-delete-btn-edit_urls-2").count(),
    ).toBe(0);

    await page.getByTestId("input-list-delete-btn-edit_urls-1").click();

    expect(
      await page.getByTestId("input-list-delete-btn-edit_urls-1").count(),
    ).toBe(0);

    await page.getByText("Close").last().click();

    await page.getByTestId("input-list-plus-btn_urls-0").click();
    await page.getByTestId("input-list-plus-btn_urls-0").click();
    await page.getByTestId("input-list-plus-btn_urls-0").click();

    expect(await page.getByTestId("input-list-delete-btn_urls-0").count()).toBe(
      1,
    );

    expect(await page.getByTestId("input-list-delete-btn_urls-1").count()).toBe(
      1,
    );

    expect(await page.getByTestId("input-list-delete-btn_urls-2").count()).toBe(
      1,
    );

    expect(await page.getByTestId("input-list-delete-btn_urls-3").count()).toBe(
      1,
    );

    expect(await page.getByTestId("input-list-delete-btn_urls-4").count()).toBe(
      0,
    );

    expect(await page.getByTestId("inputlist_str_urls_0").inputValue()).toBe(
      "test1 test1 test1 test1",
    );

    expect(await page.getByTestId("inputlist_str_urls_1").inputValue()).toBe(
      "",
    );

    await page.getByTestId("edit-button-modal").click();

    expect(
      await page.getByTestId("inputlist_str_edit_urls_0").inputValue(),
    ).toBe("test1 test1 test1 test1");

    expect(
      await page.getByTestId("inputlist_str_edit_urls_1").inputValue(),
    ).toBe("");
  },
);

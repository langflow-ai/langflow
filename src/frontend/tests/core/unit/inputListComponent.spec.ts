import { expect, test } from "@playwright/test";

test(
  "InputListComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
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
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");

    await page.waitForSelector('[data-testid="dataURL"]', {
      timeout: 3000,
    });
    await page
      .getByTestId("dataURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

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
    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();

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

    await page.getByTestId("input-list-minus-btn-edit_urls-1").click();

    const plusButtonLocator = page.getByTestId(
      "input-list-minus-btn-edit_urls-1",
    );
    const elementCount = await plusButtonLocator?.count();

    if (elementCount > 1) {
      expect(false).toBeTruthy();
    }

    await page.getByText("Close").last().click();

    await page.getByTestId("input-list-minus-btn_urls-2").isHidden();

    await page.getByTestId("input-list-plus-btn_urls-0").click();
    await page.getByTestId("input-list-plus-btn_urls-0").click();

    await page.getByTestId("inputlist_str_urls_0").fill("test test test test");
    await page
      .getByTestId("inputlist_str_urls_1")
      .fill("test1 test1 test1 test1");
    await page
      .getByTestId("inputlist_str_urls_2")
      .fill("test2 test2 test2 test2");
    await page
      .getByTestId("inputlist_str_urls_3")
      .fill("test3 test3 test3 test3");

    await page.getByTestId("div-generic-node").click();
    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();

    const value0Edit = await page
      .getByTestId("inputlist_str_edit_urls_0")
      .inputValue();
    const value1Edit = await page
      .getByTestId("inputlist_str_edit_urls_1")
      .inputValue();
    const value2Edit = await page
      .getByTestId("inputlist_str_edit_urls_2")
      .inputValue();
    const value3Edit = await page
      .getByTestId("inputlist_str_edit_urls_3")
      .inputValue();

    if (
      value0Edit !== "test test test test" ||
      value1Edit !== "test1 test1 test1 test1" ||
      value2Edit !== "test2 test2 test2 test2" ||
      value3Edit !== "test3 test3 test3 test3"
    ) {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("input-list-minus-btn-edit_urls-1").click();
    await page.getByTestId("input-list-minus-btn-edit_urls-1").click();
    await page.getByTestId("input-list-minus-btn-edit_urls-1").click();

    const plusButtonLocatorEdit0 = await page.getByTestId(
      "input-list-plus-btn-edit_urls-0",
    );
    const elementCountEdit0 = await plusButtonLocatorEdit0?.count();

    const plusButtonLocatorEdit2 = await page.getByTestId(
      "input-list-plus-btn-edit_urls-1",
    );
    const elementCountEdit2 = await plusButtonLocatorEdit2?.count();

    if (elementCountEdit0 > 1 || elementCountEdit2 > 0) {
      expect(false).toBeTruthy();
    }

    const minusButtonLocatorEdit1 = await page.getByTestId(
      "input-list-minus-btn-edit_urls-1",
    );

    const elementCountMinusEdit1 = await minusButtonLocatorEdit1?.count();

    const minusButtonLocatorEdit2 = await page.getByTestId(
      "input-list-minus-btn-edit_urls-2",
    );

    const elementCountMinusEdit2 = await minusButtonLocatorEdit2?.count();

    if (elementCountMinusEdit1 > 1 || elementCountMinusEdit2 > 0) {
      expect(false).toBeTruthy();
    }
  },
);

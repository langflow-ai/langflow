import { expect, test } from "@playwright/test";
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

    await page.getByTestId("input-list-dropdown-menu-0-edit").click();

    await page.getByTestId("input-list-dropdown-menu-0-delete").click();

    expect(
      await page.getByTestId("input-list-dropdown-menu-2-edit").count(),
    ).toBe(0);

    await page.getByTestId("input-list-dropdown-menu-1-edit").click();

    await page.getByTestId("input-list-dropdown-menu-1-delete").click();

    expect(
      await page.getByTestId("input-list-dropdown-menu-1-edit").count(),
    ).toBe(0);

    await page.getByText("Close").last().click();

    await page.getByTestId("input-list-plus-btn_urls-0").click();
    await page.getByTestId("input-list-plus-btn_urls-0").click();
    await page.getByTestId("input-list-plus-btn_urls-0").click();

    expect(
      await page.getByTestId("input-list-dropdown-menu-0-view").count(),
    ).toBe(1);

    expect(
      await page.getByTestId("input-list-dropdown-menu-1-view").count(),
    ).toBe(1);

    expect(
      await page.getByTestId("input-list-dropdown-menu-2-view").count(),
    ).toBe(1);

    expect(
      await page.getByTestId("input-list-dropdown-menu-3-view").count(),
    ).toBe(1);

    expect(
      await page.getByTestId("input-list-dropdown-menu-4-view").count(),
    ).toBe(0);

    await page.getByTestId("input-list-dropdown-menu-0-view").click();
    await page.getByTestId("input-list-dropdown-menu-0-duplicate").click();

    expect(await page.getByTestId("inputlist_str_urls_0").inputValue()).toBe(
      "test1 test1 test1 test1",
    );

    expect(await page.getByTestId("inputlist_str_urls_1").inputValue()).toBe(
      "test1 test1 test1 test1",
    );

    await page.getByTestId("edit-button-modal").click();

    expect(
      await page.getByTestId("inputlist_str_edit_urls_0").inputValue(),
    ).toBe("test1 test1 test1 test1");

    expect(
      await page.getByTestId("inputlist_str_edit_urls_1").inputValue(),
    ).toBe("test1 test1 test1 test1");

    await page.getByTestId("input-list-dropdown-menu-1-edit").click();

    await page.getByTestId("input-list-dropdown-menu-1-duplicate").click();

    expect(
      await page.getByTestId("inputlist_str_edit_urls_0").inputValue(),
    ).toBe("test1 test1 test1 test1");

    expect(
      await page.getByTestId("inputlist_str_edit_urls_1").inputValue(),
    ).toBe("test1 test1 test1 test1");

    expect(
      await page.getByTestId("inputlist_str_edit_urls_2").inputValue(),
    ).toBe("test1 test1 test1 test1");
  },
);

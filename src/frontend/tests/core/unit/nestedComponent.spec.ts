import { expect, test } from "@playwright/test";

test(
  "NestedComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

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
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("api request");

    await page.waitForSelector('[data-testid="dataAPI Request"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("dataAPI Request")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.click('//*[@id="react-flow-id"]');

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("dict_nesteddict_headers").first().click();
    await page
      .getByText("{")
      .last()
      .hover()
      .then(async () => {
        await page.locator(".json-view--edit").first().click();
        await page.locator(".json-view--input").first().fill("keytest");
        await page.locator(".json-view--edit").first().click();

        await page.locator(".json-view--edit").first().click();
        await page.locator(".json-view--input").first().fill("keytest1");
        await page.locator(".json-view--edit").first().click();

        await page.locator(".json-view--edit").first().click();
        await page.locator(".json-view--input").first().fill("keytest2");
        await page.locator(".json-view--edit").first().click();
      });

    await page
      .locator(".json-view--pair")
      .first()
      .hover()
      .then(async () => {
        await page.locator(".json-view--edit").nth(2).click();
        await page.locator(".json-view--null").first().fill("proptest1");
        await page.locator(".json-view--edit").nth(2).click();
      });

    await page.getByText("Save").last().click();

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();

    await page.getByTestId("dict_nesteddict_edit_headers").first().click();

    expect(await page.getByText("keytest", { exact: true }).count()).toBe(1);
    expect(await page.getByText("keytest1", { exact: true }).count()).toBe(1);
    expect(await page.getByText("keytest2", { exact: true }).count()).toBe(1);
    expect(await page.getByText("proptest1").count()).toBe(1);

    await page
      .locator(".json-view--pair")
      .first()
      .hover()
      .then(async () => {
        await page.locator(".json-view--edit").nth(3).click();
        await page.locator(".json-view--edit").nth(2).click();
      });

    expect(await page.getByText("keytest", { exact: true }).count()).toBe(0);
    expect(await page.getByText("proptest1").count()).toBe(0);
  },
);

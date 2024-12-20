import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "NestedComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

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

    await adjustScreenView(page);

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

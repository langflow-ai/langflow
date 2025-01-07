import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { extractAndCleanCode } from "../../utils/extract-and-clean-code";

test(
  "user must be able to minimize and expand a node how many times as they want",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text output");

    await page
      .getByTestId("outputsText Output")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-text-output").click();
      });

    await page.waitForSelector('[data-testid="title-Text Output"]', {
      timeout: 3000,
    });

    expect(await page.getByText("Toolset", { exact: true }).count()).toBe(0);

    await page.getByTestId("title-Text Output").click();

    expect(await page.getByTestId("show-node-content").count()).toBe(1);

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("minimize-button-modal").click();

    expect(await page.getByTestId("show-node-content").count()).toBe(0);

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("expand-button-modal").click();

    expect(await page.getByTestId("show-node-content").count()).toBe(1);

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("minimize-button-modal").click();

    expect(await page.getByTestId("show-node-content").count()).toBe(0);

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("expand-button-modal").click();

    expect(await page.getByTestId("show-node-content").count()).toBe(1);

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("minimize-button-modal").click();

    expect(await page.getByTestId("show-node-content").count()).toBe(0);

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("expand-button-modal").click();

    expect(await page.getByTestId("show-node-content").count()).toBe(1);
  },
);

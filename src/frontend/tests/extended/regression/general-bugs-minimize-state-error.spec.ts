import { type Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { TEXTS } from "../../utils/constants/texts";

async function toggleNodeState(page: Page, action: "minimize" | "expand") {
  const expectedCount = action === "minimize" ? 1 : 0;
  await page.getByTestId("more-options-modal").click();
  await page.getByTestId(`${action}-button-modal`).click();
  expect(await page.getByTestId("hide-node-content").count()).toBe(
    expectedCount,
  );
}

test(
  "user must be able to minimize and expand a node how many times as they want",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill(TEXTS.searchTextOutput);

    await page
      .getByTestId("input_outputText Output")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-text-output").click();
      });

    await page.waitForSelector('[data-testid="title-Text Output"]', {
      timeout: 3000,
    });

    expect(await page.getByText("Toolset", { exact: true }).count()).toBe(0);
    await page.getByTestId("title-Text Output").click();
    expect(await page.getByTestId("hide-node-content").count()).toBe(0);

    await adjustScreenView(page, { numberOfZoomOut: 3 });

    for (let i = 0; i < 5; i++) {
      await toggleNodeState(page, "minimize");
      await toggleNodeState(page, "expand");
    }
  },
);

import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";

import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import {
  closeParametersPanel,
  openParametersPanel,
} from "../../utils/open-advanced-options";

test(
  "user should be able to use nested component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("alter metadata");

    await addLegacyComponents(page);

    await page.waitForTimeout(500);

    await page.waitForSelector('[data-testid="processingAlter Metadata"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("processingAlter Metadata")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-alter-metadata").click();
      });

    await adjustScreenView(page);

    await page.getByTestId("dict_nesteddict_metadata").first().click();
    await page.getByText("{}").last().clear();

    await page
      .getByRole("textbox")
      .last()
      .fill(
        '{"keytest": "proptest", "keytest1": "proptest1", "keytest2": "proptest2"}',
      );

    await page.getByTitle("Switch to tree mode (current mode: text)").click();
    expect(await page.getByText("keytest", { exact: true }).count()).toBe(1);
    expect(await page.getByText("keytest1", { exact: true }).count()).toBe(1);
    expect(await page.getByText("keytest2", { exact: true }).count()).toBe(1);
    expect(await page.getByText("proptest", { exact: true }).count()).toBe(1);
    expect(await page.getByText("proptest1", { exact: true }).count()).toBe(1);
    expect(await page.getByText("proptest2", { exact: true }).count()).toBe(1);

    await page.getByText(TEXTS.save).last().click();

    await page.getByTestId("div-generic-node").click();

    // LE-1810: the panel only manages parameters — the dict value is edited
    // on the node itself.
    await openParametersPanel(page);
    await closeParametersPanel(page);

    await page.getByTestId("dict_nesteddict_metadata").first().click();
    await page.getByTitle("Switch to tree mode (current mode: text)").click();
    await page.waitForSelector(".jse-bracket", {
      timeout: 3000,
    });

    expect(await page.getByText("keytest", { exact: true }).count()).toBe(1);
    expect(await page.getByText("keytest1", { exact: true }).count()).toBe(1);
    expect(await page.getByText("keytest2", { exact: true }).count()).toBe(1);
    expect(await page.getByText("proptest", { exact: true }).count()).toBe(1);
    expect(await page.getByText("proptest1", { exact: true }).count()).toBe(1);
    expect(await page.getByText("proptest2", { exact: true }).count()).toBe(1);

    await page
      .getByText("proptest", { exact: true })
      .last()
      .click({ button: "right" });
    await page.getByText("Remove").last().click();

    expect(await page.getByText("keytest", { exact: true }).count()).toBe(0);
    expect(await page.getByText("proptest", { exact: true }).count()).toBe(0);

    await page.getByText(TEXTS.save, { exact: true }).last().click();
  },
);

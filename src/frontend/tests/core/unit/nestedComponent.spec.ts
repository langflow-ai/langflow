import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to use nested component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
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

    await page.getByText("Save").last().click();

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("edit-button-modal").last().click();

    await page.getByTestId("edit_dict_nesteddict_edit_metadata").last().click();
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
  },
);

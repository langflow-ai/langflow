import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  closeAdvancedOptions,
  disableInspectPanel,
  enableInspectPanel,
  openAdvancedOptions,
} from "../../utils/open-advanced-options";

test(
  "ToggleComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("directory");

    await page.waitForSelector('[data-testid="files_and_knowledgeDirectory"]', {
      timeout: 30000,
    });
    await page
      .getByTestId("files_and_knowledgeDirectory")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await adjustScreenView(page);

    await page.getByTestId("div-generic-node").click();
    
    await adjustScreenView(page);

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeTruthy();

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeFalsy();

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeTruthy();

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeFalsy();

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeTruthy();

    await page.getByTestId("div-generic-node").click();

    await adjustScreenView(page);

    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeTruthy();


    const plusButtonLocator = page.getByTestId("toggle_bool_load_hidden");
    const elementCount = await plusButtonLocator?.count();
    if (elementCount === 0) {
      expect(true).toBeTruthy();

      await page.getByTestId("div-generic-node").click();


      await page.locator('//*[@id="showload_hidden"]').click();
      expect(
        await page.locator('//*[@id="showload_hidden"]').isChecked(),
      ).toBeTruthy();

      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeTruthy();


      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeFalsy();

      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeTruthy();

      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeFalsy();

      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeTruthy();

      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeFalsy();
    }
  },
);

import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import {
  closeParametersPanel,
  openParametersPanel,
  toggleParameterOnNode,
} from "../../utils/open-advanced-options";

test(
  "ToggleComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);

    // Open the sidebar options dropdown
    await page.getByTestId("sidebar-options-trigger").click();

    // Wait for and click the legacy switch
    await page
      .getByTestId("sidebar-legacy-switch")
      .waitFor({ state: "visible" });
    await page.getByTestId("sidebar-legacy-switch").click();
    expect(
      await page
        .getByTestId("sidebar-legacy-switch")
        .getAttribute("aria-checked"),
    ).toBe("true");

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

    // LE-1810: the parameters panel manages visibility through Add/Remove;
    // the row swaps between the two buttons.
    await openParametersPanel(page);

    await toggleParameterOnNode(page, "load_hidden");
    await expect(
      page.getByTestId("inspector-remove-load_hidden"),
    ).toBeVisible();

    await closeParametersPanel(page);

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

    await openParametersPanel(page);

    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeTruthy();

    await toggleParameterOnNode(page, "load_hidden");
    await expect(page.getByTestId("inspector-add-load_hidden")).toBeVisible();

    await toggleParameterOnNode(page, "max_concurrency");
    await expect(
      page.getByTestId("inspector-remove-max_concurrency"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "path");
    await expect(page.getByTestId("inspector-add-path")).toBeVisible();

    await toggleParameterOnNode(page, "recursive");
    await expect(page.getByTestId("inspector-remove-recursive")).toBeVisible();

    await toggleParameterOnNode(page, "silent_errors");
    await expect(
      page.getByTestId("inspector-remove-silent_errors"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "use_multithreading");
    await expect(
      page.getByTestId("inspector-remove-use_multithreading"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "max_concurrency");
    await expect(
      page.getByTestId("inspector-add-max_concurrency"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "path");
    await expect(page.getByTestId("inspector-remove-path")).toBeVisible();

    await toggleParameterOnNode(page, "recursive");
    await expect(page.getByTestId("inspector-add-recursive")).toBeVisible();

    await toggleParameterOnNode(page, "silent_errors");
    await expect(page.getByTestId("inspector-add-silent_errors")).toBeVisible();

    await toggleParameterOnNode(page, "use_multithreading");
    await expect(
      page.getByTestId("inspector-add-use_multithreading"),
    ).toBeVisible();

    await closeParametersPanel(page);

    const plusButtonLocator = page.getByTestId("toggle_bool_load_hidden");
    const elementCount = await plusButtonLocator?.count();
    if (elementCount === 0) {
      expect(true).toBeTruthy();

      await page.getByTestId("div-generic-node").click();

      await openParametersPanel(page);

      await toggleParameterOnNode(page, "load_hidden");
      await expect(
        page.getByTestId("inspector-remove-load_hidden"),
      ).toBeVisible();

      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeTruthy();

      await closeParametersPanel(page);

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

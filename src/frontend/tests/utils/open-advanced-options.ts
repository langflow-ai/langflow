import type { Page } from "@playwright/test";

export const openAdvancedOptions = async (
  page: Page,
  skipEnableFields = false,
) => {
  if ((await page.getByTestId("edit-button-modal").count()) > 0) {
    await page.getByTestId("edit-button-modal").click();
  } else if (!skipEnableFields) {
    await page.getByTestId("edit-fields-button").click();
  }
};

export const closeAdvancedOptions = async (
  page: Page,
  skipEnableFields = false,
) => {
  if ((await page.getByTestId("edit-button-close").count()) > 0) {
    await page.getByTestId("edit-button-close").click();
  } else if (!skipEnableFields) {
    await page.getByTestId("edit-fields-button").click();
  }
};

export const enableInspectPanel = async (page: Page) => {
  await page.getByTestId("canvas_controls_dropdown_help").click();
  if (
    !(await page
      .getByTestId("canvas_controls_dropdown_toggle_inspector-toggle")
      .isChecked())
  ) {
    await page.getByTestId("canvas_controls_dropdown_toggle_inspector").click();
  }
  await page
    .getByTestId("canvas_controls_dropdown_help")
    .click({ force: true });
};

export const disableInspectPanel = async (page: Page) => {
  await page.getByTestId("canvas_controls_dropdown_help").click();
  if (
    await page
      .getByTestId("canvas_controls_dropdown_toggle_inspector-toggle")
      .isChecked()
  ) {
    await page.getByTestId("canvas_controls_dropdown_toggle_inspector").click();
  }
  await page
    .getByTestId("canvas_controls_dropdown_help")
    .click({ force: true });
};

import { type Page } from "@playwright/test";

export const disableInspectionPanel = async (page: Page) => {
  await page.getByTestId("canvas_controls_dropdown_help").click();
  const checkedState = await page
    .getByTestId("canvas_controls_dropdown_toggle_inspector-toggle")
    .getAttribute("data-state");
  const checked = checkedState === "checked";
  if (checked) {
    await page
      .getByTestId("canvas_controls_dropdown_toggle_inspector-toggle")
      .click();
  }
  await page.locator(".react-flow__renderer").click();

  await page.waitForTimeout(1000);
};

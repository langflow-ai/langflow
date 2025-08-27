import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "the system must delete the handles from advanced fields when the code is updated",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("if else");

    await page
      .getByTestId("logicIf-Else")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-if-else").click();
      });
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("fit_view").click();
    await zoomOut(page, 3);
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("edit-button-modal").click();

    await page.getByTestId("showtrue_case_message").click();
    await page.getByText("Close").last().click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");
    await page.waitForSelector('[data-testid="input_outputText Input"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 100 },
      });

    await page
      .getByTestId("handle-textinput-shownode-output text-right")
      .click();

    await page
      .getByTestId("handle-conditionalrouter-shownode-case true-left")
      .click();

    await page.getByTestId("title-If-Else").click();

    await page.getByTestId("edit-button-modal").click();

    const numberOfDisabledInputs = await page
      .getByPlaceholder("Receiving input")
      .count();

    expect(numberOfDisabledInputs).toBe(2);

    const numberOfLockIcons = await page.getByTestId("icon-lock").count();

    expect(numberOfLockIcons).toBe(2);

    await page.getByText("Close").last().click();

    await page.getByTestId("title-If-Else").click();

    await page.getByTestId("code-button-modal").click();

    await page.getByTestId("checkAndSaveBtn").last().click();

    await page.getByTestId("edit-button-modal").click();

    const numberOfDisabledInputsAfter = await page
      .getByPlaceholder("Receiving input")
      .count();

    expect(numberOfDisabledInputsAfter).toBe(0);

    const numberOfLockIconsAfter = await page.getByTestId("icon-lock").count();

    expect(numberOfLockIconsAfter).toBe(0);
  },
);

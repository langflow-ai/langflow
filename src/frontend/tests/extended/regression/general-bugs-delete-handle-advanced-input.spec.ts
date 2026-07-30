import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import {
  closeParametersPanel,
  openParametersPanel,
  toggleParameterOnNode,
} from "../../utils/open-advanced-options";

test(
  "the system must delete the handles from advanced fields when the code is updated",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("if else");

    await page
      .getByTestId("flow_controlsIf-Else")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-if-else").click();
      });

    await adjustScreenView(page, { numberOfZoomOut: 3 });

    await openParametersPanel(page);

    await toggleParameterOnNode(page, "true_case_message");
    await closeParametersPanel(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill(TEXTS.searchTextInput);
    await page.waitForSelector('[data-testid="input_outputText Input"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 100 },
      });

    await adjustScreenView(page);

    await page
      .getByTestId("handle-textinput-shownode-output text-right")
      .click();

    await page
      .getByTestId("handle-conditionalrouter-shownode-case true-left")
      .click();

    await page.getByTestId("title-If-Else").click();

    await openParametersPanel(page);

    // LE-1810: values render on the node only — the connected field shows
    // "Receiving input" there and its Remove action is locked in the panel.
    const numberOfDisabledInputs = await page
      .getByPlaceholder("Receiving input")
      .count();

    expect(numberOfDisabledInputs).toBe(1);

    await expect(
      page.getByTestId("inspector-remove-true_case_message"),
    ).toBeDisabled();

    await closeParametersPanel(page);

    await page.getByTestId("title-If-Else").click();

    await page.getByTestId("code-button-modal").last().click();

    await page.getByTestId("checkAndSaveBtn").last().click();

    await openParametersPanel(page);

    const numberOfDisabledInputsAfter = await page
      .getByPlaceholder("Receiving input")
      .count();

    expect(numberOfDisabledInputsAfter).toBe(0);

    const numberOfLockIconsAfter = await page.getByTestId("icon-lock").count();

    expect(numberOfLockIconsAfter).toBe(0);

    await closeParametersPanel(page);
  },
);

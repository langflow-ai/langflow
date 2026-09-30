import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";
import { renameFlow } from "../../utils/rename-flow";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user should be able to use Run Flow without any issues",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    // Per-run unique name lets the Run Flow dropdown select this flow by search
    // instead of a fragile positional index, and avoids the duplicate-name save
    // block when a retry reuses a DB that already holds a prior run's flow.
    const targetFlowName = `Run Flow Target ${Date.now()}`;

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill(TEXTS.searchChatOutput);
    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input_outputChat Output")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-chat-output").click();
      });

    await zoomOut(page, 2);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill(TEXTS.searchChatInput);
    await page.waitForSelector('[data-testid="input_outputChat Input"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input_outputChat Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill(TEXTS.searchTextOutput);
    await page.waitForSelector('[data-testid="input_outputText Output"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input_outputText Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 300 },
      });

    await adjustScreenView(page);

    await page
      .getByTestId("handle-chatinput-noshownode-chat message-source")
      .click();

    await page.getByTestId("handle-textoutput-shownode-inputs-left").click();

    await page
      .getByTestId("handle-textoutput-shownode-output text-right")
      .click();
    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .click();

    await renameFlow(page, { flowName: targetFlowName });

    await page.getByTestId("icon-ChevronLeft").click();

    await expect(page.getByTestId(TID.newProjectBtn)).toBeVisible();
    await openTemplatesModal(page);

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("run flow");
    await page.waitForSelector('[data-testid="flow_controlsRun Flow"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("flow_controlsRun Flow")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-run-flow").click();
      });

    await adjustScreenView(page);

    await page
      .getByTestId("value-dropdown-dropdown_str_flow_name_selected")
      .click();

    await page.getByTestId("refresh-dropdown-list-flow_name_selected").click();

    await page.waitForSelector("text=Loading", { timeout: 30000 });
    await page.waitForSelector("text=Select an option", { timeout: 30000 });

    await page
      .getByTestId("value-dropdown-dropdown_str_flow_name_selected")
      .click();

    await page.getByTestId("dropdown_search_input").fill(targetFlowName);
    await page.getByTestId("dropdown-option-0-container").click();

    await page.getByTestId(/^textarea_str_chatinput.*/).click();
    await page
      .getByTestId(/^textarea_str_chatinput.*/)
      .fill("THIS IS A TEST FOR RUN FLOW COMPONENT");

    await page.getByTestId("button_run_run flow").click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000,
    });

    // Wait for and click the output inspection button using partial match
    await page.waitForSelector('[data-testid^="output-inspection-"]', {
      timeout: 30000,
    });

    await page.locator('[data-testid^="output-inspection-"]').first().click();

    const value = await page
      .getByPlaceholder(TEXTS.placeholderEmpty)
      .inputValue();

    expect(value).toBe("THIS IS A TEST FOR RUN FLOW COMPONENT");
  },
);

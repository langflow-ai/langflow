import dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";
import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user can run flow with If-Else component multiple times with different branches",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    //---------------------------------- If-Else

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("if else");
    await page.waitForSelector('[data-testid="logicIf-Else"]', {
      timeout: 2000,
    });

    await page
      .getByTestId("logicIf-Else")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-if-else").click();
      });

    await zoomOut(page, 3);

    //---------------------------------- Text Output
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text output");
    await page.waitForSelector('[data-testid="input_outputText Output"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input_outputText Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    await adjustScreenView(page);

    //---------------------------------- Text Output
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text output");
    await page.waitForSelector('[data-testid="input_outputText Output"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input_outputText Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 400 },
      });

    await adjustScreenView(page);

    await page.getByTestId("generic-node-title-arrangement").last().click();

    await page.getByTestId("edit-name-description-button").click();

    await page.getByTestId("input-title-Text Output").fill("textoutputfalse");

    await page.getByTestId("save-name-description-button").click();

    await page.waitForTimeout(500);

    await page
      .getByTestId("handle-conditionalrouter-shownode-true-right")
      .click();
    await page
      .getByTestId("handle-textoutput-shownode-inputs-left")
      .first()
      .click();

    await page
      .getByTestId("handle-conditionalrouter-shownode-false-right")
      .click();

    await page
      .getByTestId("handle-textoutput-shownode-inputs-left")
      .last()
      .click();

    await page.getByTestId("popover-anchor-input-input_text").fill("1");
    await page.getByTestId("popover-anchor-input-match_text").fill("1");

    await page.waitForTimeout(500);

    await page.getByTestId("button_run_text output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    let numberOfSuccessfullComponentsRun = 0;
    let numberOfInactiveComponentsRun = 0;

    numberOfSuccessfullComponentsRun = await page
      .getByTestId("node_duration_text output")
      .count();
    numberOfInactiveComponentsRun = await page
      .getByTestId("node_status_icon_textoutputfalse_inactive")
      .count();

    expect(numberOfSuccessfullComponentsRun).toBe(1);
    expect(numberOfInactiveComponentsRun).toBe(1);

    // Now we will change the input to make the flow go through the other branch of the If-Else component

    await page.waitForTimeout(500);

    await page.getByTestId("popover-anchor-input-input_text").fill("2");
    await page.getByTestId("button_run_textoutputfalse").click();

    await page.waitForTimeout(500);

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    numberOfSuccessfullComponentsRun = 0;
    numberOfInactiveComponentsRun = 0;

    numberOfSuccessfullComponentsRun = await page
      .getByTestId("node_duration_textoutputfalse")
      .count();
    numberOfInactiveComponentsRun = await page
      .getByTestId("node_status_icon_text output_inactive")
      .count();

    expect(numberOfSuccessfullComponentsRun).toBe(1);
    expect(numberOfInactiveComponentsRun).toBe(1);

    // retest to make sure we can run again the flow with the first branch of the If-Else component

    await page.waitForTimeout(500);

    await page.getByTestId("popover-anchor-input-input_text").fill("1");
    await page.waitForTimeout(500);

    await page.getByTestId("button_run_text output").click();

    await page.waitForTimeout(500);

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    numberOfSuccessfullComponentsRun = 0;
    numberOfInactiveComponentsRun = 0;

    numberOfSuccessfullComponentsRun = await page
      .getByTestId("node_duration_text output")
      .count();
    numberOfInactiveComponentsRun = await page
      .getByTestId("node_status_icon_textoutputfalse_inactive")
      .count();

    expect(numberOfSuccessfullComponentsRun).toBe(1);
    expect(numberOfInactiveComponentsRun).toBe(1);

    // retest to make sure we can run again the flow with the second branch of the If-Else componen
    //
    await page.waitForTimeout(500);

    await page.getByTestId("popover-anchor-input-input_text").fill("2");
    await page.getByTestId("button_run_textoutputfalse").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    numberOfSuccessfullComponentsRun = 0;
    numberOfInactiveComponentsRun = 0;

    numberOfSuccessfullComponentsRun = await page
      .getByTestId("node_duration_textoutputfalse")
      .count();
    numberOfInactiveComponentsRun = await page
      .getByTestId("node_status_icon_text output_inactive")
      .count();

    expect(numberOfSuccessfullComponentsRun).toBe(1);
    expect(numberOfInactiveComponentsRun).toBe(1);
  },
);

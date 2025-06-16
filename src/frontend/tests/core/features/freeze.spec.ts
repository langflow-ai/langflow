import { expect, test } from "@playwright/test";
import { addFlowToTestOnEmptyLangflow } from "../../utils/add-flow-to-test-on-empty-langflow";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user must be able to freeze a component",
  { tag: ["@release", "@workspace", "@components"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    const firstRunLangflow = await page
      .getByTestId("empty-project-description")
      .count();

    if (firstRunLangflow > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }

    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    //first component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");
    await page.waitForSelector('[data-testid="input_outputText Input"]', {
      timeout: 1000,
    });

    await zoomOut(page, 3);

    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");
    await page.waitForSelector('[data-testid="dataURL"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("dataURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 300 },
      });

    //third component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("split text");
    await page.waitForSelector('[data-testid="processingSplit Text"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("processingSplit Text")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 350, y: 100 },
      });

    //fourth component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("Parser");
    await page.waitForSelector('[data-testid="processingParser"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("processingParser")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 300 },
      });

    await page.getByTestId("zoom_out").click();

    //fifth component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("input_outputChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 600, y: 200 },
      });

    await page.getByTestId("div-generic-node").nth(4).click();

    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("expand-button-modal").click();

    await page.getByTestId("fit_view").click();

    let outdatedComponents = await page.getByTestId("update-button").count();

    while (outdatedComponents > 0) {
      await page.getByTestId("update-button").first().click();
      await page.waitForSelector('[data-testid="update-button"]', {
        timeout: 1000,
      });
      outdatedComponents = await page.getByTestId("update-button").count();
    }

    let filledApiKey = await page.getByTestId("remove-icon-badge").count();
    while (filledApiKey > 0) {
      await page.getByTestId("remove-icon-badge").first().click();
      filledApiKey = await page.getByTestId("remove-icon-badge").count();
    }

    await page.getByTestId("fit_view").click();
    await zoomOut(page, 2);

    //connection 1
    await page
      .getByTestId("handle-urlcomponent-shownode-extracted pages-right")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-splittext-shownode-data or dataframe-left")
      .click();

    //connection 2
    await page
      .getByTestId("handle-textinput-shownode-output text-right")
      .nth(0)
      .click();
    await page.getByTestId("handle-splittext-shownode-separator-left").click();

    //connection 3
    await page
      .getByTestId("handle-splittext-shownode-chunks-right")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-parsercomponent-shownode-data or dataframe-left")
      .click();

    //connection 4
    await page
      .getByTestId("handle-parsercomponent-shownode-parsed text-right")
      .nth(0)
      .click();
    await page.getByTestId("handle-chatoutput-shownode-inputs-left").click();

    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill("lorem ipsum");

    await page
      .getByTestId("inputlist_str_urls_0")
      .fill("https://www.lipsum.com/");

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", {
      timeout: 30000 * 3,
    });

    await page.waitForSelector(
      '[data-testid="output-inspection-output message-chatoutput"]',
      {
        timeout: 1000,
      },
    );

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const firstRunWithoutFreezing = await page
      .getByPlaceholder("Empty")
      .textContent();

    await page.getByText("Close").last().click();

    await page.getByTestId("textarea_str_input_value").first().fill(",");

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", {
      timeout: 30000 * 3,
    });

    await page.waitForSelector(
      '[data-testid="output-inspection-output message-chatoutput"]',
      {
        timeout: 1000,
      },
    );

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const secondRunWithoutFreezing = await page
      .getByPlaceholder("Empty")
      .textContent();

    await page.getByText("Close").last().click();

    await page.getByText("Split Text", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 1000,
    });

    await page.getByTestId("more-options-modal").click();

    await page.waitForSelector('[data-testid="icon-FreezeAll"]', {
      timeout: 1000,
    });

    await page.getByTestId("icon-FreezeAll").last().click();

    await page.waitForTimeout(3000);

    await page.keyboard.press("Escape");

    await page.locator('//*[@id="react-flow-id"]').click();

    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill("lorem ipsum");

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 1000,
    });

    await page.waitForTimeout(2000);

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", {
      timeout: 30000 * 3,
    });

    await page.waitForSelector(
      '[data-testid="output-inspection-output message-chatoutput"]',
      {
        timeout: 1000,
      },
    );

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const firstTextFreezed = await page.getByPlaceholder("Empty").textContent();

    await page.getByText("Close").last().click();

    await page.getByText("Split Text", { exact: true }).click();

    await page.getByText("Freeze").first().click();

    await page.waitForTimeout(3000);

    await page.keyboard.press("Escape");

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", {
      timeout: 30000 * 3,
    });

    await page.waitForSelector(
      '[data-testid="output-inspection-output message-chatoutput"]',
      {
        timeout: 1000,
      },
    );

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const thirdTextWithoutFreezing = await page
      .getByPlaceholder("Empty")
      .textContent();

    expect(firstTextFreezed).toBe(secondRunWithoutFreezing);

    expect(firstTextFreezed).not.toBe(firstRunWithoutFreezing);
    expect(firstTextFreezed).not.toBe(thirdTextWithoutFreezing);
    expect(firstRunWithoutFreezing).not.toBe(secondRunWithoutFreezing);
    expect(thirdTextWithoutFreezing).not.toBe(secondRunWithoutFreezing);
  },
);

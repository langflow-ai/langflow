import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { skipIfComponentUnavailable } from "../../utils/skip-if-component-unavailable";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user should be able to use ComposIO without getting api_key error",
  { tag: ["@release"] },
  async ({ page }) => {
    await openBlankFlow(page);
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("composio");
    await skipIfComponentUnavailable(
      page.getByTestId("composioComposio Tools"),
      "Composio",
    );

    await page.waitForSelector('[data-testid="composioComposio Tools"]', {
      timeout: 3000,
    });

    const modelElement = await page.getByTestId("composioComposio Tools");
    const targetElement = await page.locator('//*[@id="react-flow-id"]');
    await modelElement.dragTo(targetElement);

    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    await zoomOut(page, 2);

    await expect(page.getByText("api_key")).toBeVisible({
      timeout: 3000,
      visible: false,
    });
  },
);

test(
  "user should be able to use connect tools",
  { tag: ["@release", "@api", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await zoomOut(page, 3);

    //first component

    await addComponentFromSidebar(page, {
      search: "url",
      testId: "data_sourceURL",
      position: { x: 100, y: 100 },
    });

    await addComponentFromSidebar(page, {
      search: "tool calling agent",
      testId: "langchain_utilitiesTool Calling Agent",
      position: { x: 300, y: 300 },
    });

    await adjustScreenView(page);

    await page.getByTestId("title-URL").first().click();
    await expect(page.getByTestId("tool-mode-button")).toBeVisible({
      timeout: TIMEOUTS.short,
    });
    await page.getByTestId("tool-mode-button").click();

    //connection
    const urlOutput = await page
      .getByTestId("handle-urlcomponent-shownode-toolset-right")
      .first();

    await expect(urlOutput).toBeVisible({ timeout: TIMEOUTS.short });

    await urlOutput.hover();
    await page.mouse.down();
    const toolCallingAgentInput = await page
      .getByTestId("handle-toolcallingagent-shownode-tools-left")
      .nth(0);
    await toolCallingAgentInput.hover();
    await page.mouse.up();

    await expect(page.locator(".react-flow__edge-interaction")).toHaveCount(2, {
      timeout: TIMEOUTS.short,
    });
  },
);

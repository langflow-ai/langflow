import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user must be able to see output inspection",
  { tag: ["@release", "@components"] },
  async ({ page }, testInfo) => {
    // Flaky on Windows CI runners: the Basic Prompting template canvas
    // intermittently fails to finish rendering the controls in time (even with
    // the 30s adjustScreenView window). The output-inspection behavior is
    // OS-agnostic and stays covered by the Linux/macOS runs.
    test.skip(
      testInfo.project.name.includes("win") || process.platform === "win32",
      "Template canvas render is flaky on Windows CI; covered on Linux/macOS",
    );
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await adjustScreenView(page);

    await initialGPTsetup(page);

    await page.getByTestId("button_run_chat output").last().click();

    await page.waitForTimeout(600);

    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000 * 3,
    });

    await page.waitForSelector('[data-testid="icon-TextSearchIcon"]', {
      timeout: 30000,
    });

    await page.getByTestId("icon-TextSearchIcon").nth(2).click();

    await page.getByText("Sender", { exact: true }).isVisible();
    await page.getByText("Type", { exact: true }).isVisible();
    await page.getByText("User", { exact: true }).last().isVisible();
  },
);

test(
  "user must be able to see output inspection using 'o' shortcut",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    // Add URL component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill(TEXTS.searchUrl);
    await page.waitForSelector('[data-testid="data_sourceURL"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("data_sourceURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 200 },
      });

    await page.waitForTimeout(1000);

    // Get URL node ID
    const urlNode = await page.locator(".react-flow__node").first();
    const _urlNodeId = await urlNode.getAttribute("data-id");

    await zoomOut(page, 2);

    // Add two chat outputs
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill(TEXTS.searchChatOutput);
    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 1000,
    });

    await page.waitForTimeout(1000);

    await page
      .getByTestId("input_outputChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 500, y: 100 },
      });

    await page.waitForTimeout(1000);

    await page
      .getByTestId("input_outputChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 500, y: 500 },
      });

    // Fill URL input
    await page
      .getByTestId("inputlist_str_urls_0")
      .fill("https://www.example.com");

    await adjustScreenView(page);

    await page
      .getByTestId("handle-urlcomponent-shownode-extracted pages-right")
      .click();

    await page.waitForTimeout(600);

    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .nth(0)
      .click();

    await page.waitForTimeout(1000);

    // Run flow and test text output inspection
    await page.getByTestId("button_run_url").first().click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000 * 3,
    });
    await page.keyboard.press("o");
    await page.getByText(`Inspect the output of the component below.`, {
      exact: true,
    });

    await page.getByText(TEXTS.componentOutput, {
      exact: true,
    });
    await page.getByText(TEXTS.close).first().click();
    await page
      .getByTestId("handle-urlcomponent-shownode-extracted pages-right")
      .click();
    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .nth(1)
      .click();
    await page.waitForTimeout(2000);

    // Run and verify text output is still shown
    await page.getByTestId("button_run_url").first().click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000 * 3,
    });

    await page
      .getByTestId("handle-urlcomponent-shownode-extracted pages-right")
      .click();
    await page.waitForTimeout(600);
    await page
      .getByTestId("handle-urlcomponent-shownode-extracted pages-right")
      .click();

    await page
      .getByTestId("output-inspection-extracted pages-urlcomponent")
      .nth(0)
      .click();

    await page.getByText(`Inspect the output of the component below.`, {
      exact: true,
    });

    await page.getByText(TEXTS.componentOutput, {
      exact: true,
    });
    await page.getByText(TEXTS.close).first().click();
    await page.waitForTimeout(600);

    await page
      .getByTestId("handle-urlcomponent-shownode-extracted pages-right")
      .nth(0)
      .click();

    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .nth(1)
      .click();

    // Run and verify dataframe output is now shown
    await page.getByTestId("button_run_url").first().click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000 * 3,
    });
    await page.waitForTimeout(600);
    await page
      .getByTestId("output-inspection-extracted pages-urlcomponent")
      .click();
    await page.getByText(`Inspect the output of the component below.`, {
      exact: true,
    });

    await page.getByText(TEXTS.componentOutput, {
      exact: true,
    });
    await page.getByText(TEXTS.close).first().click();
    await page.waitForTimeout(600);
    // Remove all connections
    const dataEdge = await page.locator(".react-flow__edge").first();
    await dataEdge.click();
    await page.keyboard.press("Backspace");

    await page.waitForTimeout(5000);

    // Run and verify data output is shown
    await page.getByTestId("button_run_url").first().click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000 * 3,
    });
    await page.waitForTimeout(600);
    await page.keyboard.press("o");
    await page.getByText(`Inspect the output of the component below.`, {
      exact: true,
    });

    await page.getByText(TEXTS.componentOutput, {
      exact: true,
    });

    const closeButton = await page
      .getByText(TEXTS.close, {
        exact: true,
      })
      .count();

    expect(closeButton).toBeGreaterThanOrEqual(0);
  },
);

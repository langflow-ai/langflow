import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "user must be able to see output inspection",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await initialGPTsetup(page);

    await page.getByTestId("button_run_chat output").last().click();

    await page.waitForTimeout(600);

    await page.waitForSelector("text=built successfully", {
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
    await page.getByTestId("sidebar-search-input").fill("url");
    await page.waitForSelector('[data-testid="dataURL"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("dataURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 200 },
      });

    // Get URL node ID
    const urlNode = await page.locator(".react-flow__node").first();
    const urlNodeId = await urlNode.getAttribute("data-id");

    // Add two chat outputs
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("outputsChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 700, y: 200 },
      });

    await page
      .getByTestId("outputsChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 700, y: 400 },
      });

    await page.getByTestId("fit_view").click();

    // Fill URL input
    await page
      .getByTestId("inputlist_str_urls_0")
      .fill("https://www.example.com");

    await page
      .getByTestId("handle-urlcomponent-shownode-message-right")
      .nth(0)
      .click();
    await page.waitForTimeout(600);

    await page
      .getByTestId("handle-chatoutput-noshownode-text-target")
      .nth(0)
      .click();

    await page.waitForTimeout(1000);

    // Run flow and test text output inspection
    await page.getByTestId("button_run_url").first().click();
    await page.waitForSelector("text=built successfully", {
      timeout: 30000 * 3,
    });
    await page.keyboard.press("o");
    await page.getByText(`Inspect the output of the component below.`, {
      exact: true,
    });

    await page.getByText(`Component Output`, {
      exact: true,
    });
    await page.getByText("Close").first().click();

    // Connect dataframe output to second chat output
    await page
      .getByTestId("handle-urlcomponent-shownode-dataframe-right")
      .nth(0)
      .click();
    await page.waitForTimeout(600);
    await page
      .getByTestId("handle-chatoutput-noshownode-text-target")
      .nth(1)
      .click();
    await page.waitForTimeout(600);

    // Run and verify text output is still shown
    await page.getByTestId("button_run_url").first().click();
    await page.waitForSelector("text=built successfully", {
      timeout: 30000 * 3,
    });
    await page.waitForTimeout(600);
    await page.keyboard.press("o");
    await page.getByText(`Inspect the output of the component below.`, {
      exact: true,
    });

    await page.getByText(`Component Output`, {
      exact: true,
    });
    await page.getByText("Close").first().click();
    await page.waitForTimeout(600);

    // Remove text connection
    const textEdge = await page.locator(".react-flow__edge").first();
    await textEdge.click();
    await page.keyboard.press("Backspace");
    await page.waitForTimeout(600);

    // Run and verify dataframe output is now shown
    await page.getByTestId("button_run_url").first().click();
    await page.waitForSelector("text=built successfully", {
      timeout: 30000 * 3,
    });
    await page.waitForTimeout(600);
    await page.keyboard.press("o");
    await page.getByText(`Inspect the output of the component below.`, {
      exact: true,
    });

    await page.getByText(`Component Output`, {
      exact: true,
    });
    await page.getByText("Close").first().click();
    await page.waitForTimeout(600);
    // Remove all connections
    const dataEdge = await page.locator(".react-flow__edge").first();
    await dataEdge.click();
    await page.keyboard.press("Backspace");

    await page.waitForTimeout(5000);

    // Run and verify data output is shown
    await page.getByTestId("button_run_url").first().click();
    await page.waitForSelector("text=built successfully", {
      timeout: 30000 * 3,
    });
    await page.waitForTimeout(600);
    await page.keyboard.press("o");
    await page.getByText(`Inspect the output of the component below.`, {
      exact: true,
    });

    await page.getByText(`Component Output`, {
      exact: true,
    });

    const closeButton = await page
      .getByText(`Close`, {
        exact: true,
      })
      .count();

    expect(closeButton).toBeGreaterThan(1);
  },
);

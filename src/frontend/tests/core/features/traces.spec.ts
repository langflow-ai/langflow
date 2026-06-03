import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { TEXTS } from "../../utils/constants/texts";

test(
  "should able to see and interact with Traces",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page }) => {
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    // Tie the wait to the actual flow-creation network response. On Windows
    // CI the click → canvas mount can outlast a 100s wait when the backend
    // is under load, but if the POST /flows succeeds we know the page will
    // navigate; we then wait for the canvas with a generous budget.
    const flowCreatePromise = page.waitForResponse(
      (response) =>
        /\/api\/v1\/flows\/?(?:\?|$)/.test(response.url()) &&
        response.request().method() === "POST" &&
        response.status() === 201,
      { timeout: 120000 },
    );
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await flowCreatePromise;
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });
    await expect(page.getByTestId(/.*rf__node.*/).first()).toBeVisible({
      timeout: 30000,
    });
    let outdatedComponents = await page.getByTestId("update-button").count();
    const maxUpdateIterations = 20;
    let updateIterations = 0;
    while (outdatedComponents > 0) {
      if (++updateIterations > maxUpdateIterations) {
        throw new Error(
          `update-button count did not reach 0 after ${maxUpdateIterations} iterations (last count: ${outdatedComponents})`,
        );
      }
      await page.getByTestId("update-button").first().click();
      outdatedComponents = await page.getByTestId("update-button").count();
    }

    let filledApiKey = await page.getByTestId("remove-icon-badge").count();
    const maxBadgeIterations = 20;
    let badgeIterations = 0;
    while (filledApiKey > 0) {
      if (++badgeIterations > maxBadgeIterations) {
        throw new Error(
          `remove-icon-badge count did not reach 0 after ${maxBadgeIterations} iterations (last count: ${filledApiKey})`,
        );
      }
      await page.getByTestId("remove-icon-badge").first().click();
      filledApiKey = await page.getByTestId("remove-icon-badge").count();
    }

    await page.getByRole("button", { name: "Traces" }).first().click();
    await expect(
      page.getByText("No Data Available", { exact: true }),
    ).toBeVisible();
  },
);

test.skip(
  "should able to see traces after running a flow",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page }) => {
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    // Tie the wait to the actual flow-creation network response. On Windows
    // CI the click → canvas mount can outlast a 100s wait when the backend
    // is under load, but if the POST /flows succeeds we know the page will
    // navigate; we then wait for the canvas with a generous budget.
    const flowCreatePromise = page.waitForResponse(
      (response) =>
        /\/api\/v1\/flows\/?(?:\?|$)/.test(response.url()) &&
        response.request().method() === "POST" &&
        response.status() === 201,
      { timeout: 120000 },
    );
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await flowCreatePromise;
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });
    await expect(page.getByTestId(/.*rf__node.*/).first()).toBeVisible({
      timeout: 30000,
    });
    let outdatedComponents = await page.getByTestId("update-button").count();
    const maxUpdateIterations = 20;
    let updateIterations = 0;
    while (outdatedComponents > 0) {
      if (++updateIterations > maxUpdateIterations) {
        throw new Error(
          `update-button count did not reach 0 after ${maxUpdateIterations} iterations (last count: ${outdatedComponents})`,
        );
      }
      await page.getByTestId("update-button").first().click();
      outdatedComponents = await page.getByTestId("update-button").count();
    }

    let filledApiKey = await page.getByTestId("remove-icon-badge").count();
    const maxBadgeIterations = 20;
    let badgeIterations = 0;
    while (filledApiKey > 0) {
      if (++badgeIterations > maxBadgeIterations) {
        throw new Error(
          `remove-icon-badge count did not reach 0 after ${maxBadgeIterations} iterations (last count: ${filledApiKey})`,
        );
      }
      await page.getByTestId("remove-icon-badge").first().click();
      filledApiKey = await page.getByTestId("remove-icon-badge").count();
    }

    await page.getByTestId("playground-btn-flow-io").click();
    await page.getByTestId("button-send").click();
    await page.waitForFunction(
      () => {
        const text = document.body?.innerText || "";
        return /Finished|Error occurred/i.test(text);
      },
      null,
      { timeout: 60000 },
    );
    await page.getByTestId("playground-close-button").click();
    await page.getByTestId("sidebar-nav-traces").click();
    await page.waitForTimeout(50000);
    await page.getByLabel("Reload").click();
    await page.getByRole("gridcell", { name: /Hello/i }).first().click({
      timeout: 60000,
    });
    await page.getByText("Run");
  },
);

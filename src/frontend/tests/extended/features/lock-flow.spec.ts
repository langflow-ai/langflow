import { expect, type Page, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to lock a flow and it must be saved",
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
      state: "visible",
    });

    await page.getByTestId("lock_unlock").click();

    //ensure the UI is updated
    await page.waitForTimeout(500);

    await page.waitForSelector('[data-testid="icon-Lock"]', {
      timeout: 3000,
    });

    await page.getByTestId("icon-ChevronLeft").click();
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 3000,
    });

    await page.getByTestId("list-card").first().click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
      state: "visible",
    });

    //ensure the UI is updated
    await page.waitForTimeout(1000);

    await page.waitForSelector('[data-testid="icon-Lock"]', {
      timeout: 3000,
    });

    await page.getByTestId("lock_unlock").click();
    await page.waitForSelector('[data-testid="icon-LockOpen"]', {
      timeout: 3000,
    });

    await page.getByTestId("icon-ChevronLeft").click();
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 3000,
    });

    await page.getByTestId("list-card").first().click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
      state: "visible",
    });

    await page.waitForSelector('[data-testid="icon-LockOpen"]', {
      timeout: 3000,
      state: "visible",
    });

    await tryDeleteEdge(page);
    await page.locator(".react-flow__edge-path").nth(0).click();
    await page.keyboard.press("Delete");
    let numberOfEdges = await page.locator(".react-flow__edge-path").count();
    expect(numberOfEdges).toBe(2);

    await page.locator(".react-flow__edge-path").nth(0).click();
    await page.keyboard.press("Delete");
    numberOfEdges = await page.locator(".react-flow__edge-path").count();
    expect(numberOfEdges).toBe(1);

    await page.locator(".react-flow__edge-path").nth(0).click();
    await page.keyboard.press("Delete");
    numberOfEdges = await page.locator(".react-flow__edge-path").count();
    expect(numberOfEdges).toBe(0);

    await tryConnectNodes(page);

    await page.getByTestId("handle-prompt-shownode-prompt-right").click();
    await page
      .getByTestId("handle-languagemodelcomponent-shownode-system message-left")
      .click();

    await page
      .getByTestId("handle-chatinput-shownode-chat message-right")
      .click();
    await page
      .getByTestId("handle-languagemodelcomponent-shownode-input-left")
      .click();

    await page
      .getByTestId(
        "handle-languagemodelcomponent-shownode-model response-right",
      )
      .click();
    await page.getByTestId("handle-chatoutput-shownode-inputs-left").click();
    numberOfEdges = await page.locator(".react-flow__edge-path").count();

    expect(numberOfEdges).toBe(3);
  },
);

async function tryConnectNodes(page: Page) {
  await page.getByTestId("lock_unlock").click();

  const numberOfTries = 5;
  let numberOfEdges = await page.locator(".react-flow__edge-path").count();

  for (let i = 0; i < numberOfTries; i++) {
    try {
      await page.getByTestId("handle-prompt-shownode-prompt-right").click({
        timeout: 500,
      });
    } catch (e) {
      numberOfEdges = await page.locator(".react-flow__edge-path").count();
      expect(numberOfEdges).toBe(0);
    }

    try {
      await page
        .getByTestId(
          "handle-languagemodelcomponent-shownode-system message-left",
        )
        .click({
          timeout: 500,
        });
    } catch (e) {
      numberOfEdges = await page.locator(".react-flow__edge-path").count();
      expect(numberOfEdges).toBe(0);
    }
  }

  await page.getByTestId("lock_unlock").click();
}

async function tryDeleteEdge(page: Page) {
  await page.getByTestId("lock_unlock").click();

  let numberOfEdges = await page.locator(".react-flow__edge-path").count();
  expect(numberOfEdges).toBe(3);
  const numberOfTries = 50;

  for (let i = 0; i < numberOfTries; i++) {
    await page.locator(".react-flow__edge-path").nth(0).click();
    await page.keyboard.press("Delete");
    await page.locator(".react-flow__edge-path").nth(1).click();
    await page.keyboard.press("Delete");
    await page.locator(".react-flow__edge-path").nth(2).click();
    await page.keyboard.press("Delete");
    numberOfEdges = await page.locator(".react-flow__edge-path").count();
    expect(numberOfEdges).toBe(3);
  }
  //unlock the flow
  await page.getByTestId("lock_unlock").click();
}

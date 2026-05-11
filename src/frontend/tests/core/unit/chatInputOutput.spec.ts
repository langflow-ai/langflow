import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test("chat_io_teste", { tag: ["@release", "@workspace"] }, async ({ page }) => {
  await awaitBootstrapTest(page);

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });

  await page.getByTestId("blank-flow").click();
  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    state: "visible",
  });
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat output");
  await page.waitForSelector('[data-testid="input_outputChat Output"]', {
    timeout: 2000,
  });

  await page
    .getByTestId("input_outputChat Output")
    .hover()
    .then(async () => {
      await page.getByTestId("add-component-button-chat-output").click();
    });

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat input");
  await page.waitForSelector('[data-testid="input_outputChat Input"]', {
    timeout: 2000,
  });

  await page
    .getByTestId("input_outputChat Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'), {
      targetPosition: { x: 100, y: 100 },
    });

  await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
    timeout: 100000,
  });

  await adjustScreenView(page);

  await page
    .getByTestId("handle-chatinput-noshownode-chat message-source")
    .click();
  await page.getByTestId("handle-chatoutput-noshownode-inputs-target").click();

  await page.getByText("Playground", { exact: true }).last().click();
  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });
  await page.getByTestId("input-chat-playground").click();
  await page.getByTestId("input-chat-playground").fill("teste");
  await page.getByTestId("button-send").first().click();

  await page.waitForSelector('[data-testid="div-chat-message"]', {
    timeout: 30000,
  });

  // Wait for the message content to be populated (not just the element to exist)
  await expect(page.getByTestId("div-chat-message")).toHaveText("teste", {
    timeout: 30000,
  });
});

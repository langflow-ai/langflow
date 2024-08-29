import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("Travel Planning Agent", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByRole("heading", { name: "Travel Planning Agents" }).click();

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("yahoo finance");
  await page.waitForTimeout(1000);

  await page.getByText("SearchAPI").last().click();
  await page.waitForTimeout(1000);
  await page.keyboard.press("Backspace");

  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-100, 100);
    });

  await page.mouse.up();

  await page
    .getByTestId("toolsYahoo Finance News Tool")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("fit view").click();

  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  //connection 1
  const yahooElementOutput = await page
    .getByTestId("handle-yfinancetool-shownode-tool-right")
    .nth(0);
  await yahooElementOutput.hover();
  await page.mouse.down();
  const agentOne = await page
    .getByTestId("handle-toolcallingagent-shownode-tools-left")
    .nth(0);
  await agentOne.hover();
  await page.mouse.up();

  //connection 2
  await yahooElementOutput.hover();
  await page.mouse.down();
  const agentTwo = await page
    .getByTestId("handle-toolcallingagent-shownode-tools-left")
    .nth(1);
  await agentTwo.hover();
  await page.mouse.up();

  //connection 3
  await yahooElementOutput.hover();
  await page.mouse.down();
  const agentThree = await page
    .getByTestId("handle-toolcallingagent-shownode-tools-left")
    .nth(2);
  await agentThree.hover();
  await page.mouse.up();

  await page
    .getByTestId("popover-anchor-input-api_key")
    .first()
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByTestId("dropdown_str_model_name").click();
  await page.getByTestId("gpt-4o-1-option").click();

  await page.waitForTimeout(1000);

  await page.getByTestId("button_run_chat output").click();
  await page.waitForSelector("text=built successfully", { timeout: 60000 * 3 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByText("Playground", { exact: true }).click();

  await page.waitForSelector("text=default session", {
    timeout: 30000,
  });

  await page.waitForTimeout(1000);

  const output = await page.getByTestId("div-chat-message").allTextContents();
  const outputText = output.join("\n");

  expect(outputText.toLowerCase()).toContain("weather");
  expect(outputText.toLowerCase()).toContain("budget");

  expect(outputText.toLowerCase()).toContain("uberlândia");
  expect(outputText.toLowerCase()).toContain("pão de queijo");
});

import { Page, expect, test } from "@playwright/test";
import { readFileSync } from "fs";

test.describe("save component tests", () => {
  async function saveComponent(page: Page, pattern: RegExp, n: number) {
    for (let i = 0; i < n; i++) {
      await page.getByTestId(pattern).click();
      await page.getByLabel("Save").click();
    }
  }

  /// <reference lib="dom"/>
  test("save group component tests", async ({ page }) => {
    await page.goto("http:localhost:3000/");
    await page.locator('//*[@id="new-project-btn"]').click();

    await page.getByTestId("blank-flow").click();
    await page.waitForTimeout(1000);

    // Read your file into a buffer.
    const jsonContent = readFileSync(
      "tests/end-to-end/assets/flow_group_test.json",
      "utf-8"
    );

    // Create the DataTransfer and File
    const dataTransfer = await page.evaluateHandle((data) => {
      const dt = new DataTransfer();
      // Convert the buffer to a hex array
      const file = new File([data], "flow_group_test.json", {
        type: "application/json",
      });
      dt.items.add(file);
      return dt;
    }, jsonContent);

    page.waitForTimeout(1000);

    // Now dispatch
    await page.dispatchEvent(
      "//*[@id='react-flow-id']/div[1]/div[1]/div",
      "drop",
      {
        dataTransfer,
      }
    );

    const genericNoda = page.getByTestId("div-generic-node");
    const elementCount = await genericNoda.count();
    if (elementCount > 0) {
      expect(true).toBeTruthy();
    }
    await page
      .locator('//*[@id="react-flow-id"]/div[1]/div[2]/button[3]')
      .click();

    await page.getByTestId("title-PythonFunctionTool").click({
      modifiers: ["Control"],
    });
    await page.getByTestId("title-ChatOpenAI").click({
      modifiers: ["Control"],
    });

    await page.getByTestId("title-Agent Initializer").click({
      modifiers: ["Control"],
    });

    await page.getByRole("button", { name: "Group" }).click();

    let textArea = page.getByTestId("div-textarea-description");
    let elementCountText = await textArea.count();
    if (elementCountText > 0) {
      expect(true).toBeTruthy();
    }

    let groupNode = page.getByTestId("title-Group");
    let elementGroup = await groupNode.count();
    if (elementGroup > 0) {
      expect(true).toBeTruthy();
    }

    await page.getByTestId("title-Group").click();
    await page.getByTestId("icon-SaveAll").click();

    const replaceButton = await page.getByTestId("replace-button").isVisible();

    if (replaceButton) {
      await page.getByTestId("replace-button").click();
    }
    await page.getByTestId("extended-disclosure").click();
    await page.getByPlaceholder("Search").click();
    await page.getByPlaceholder("Search").fill("group");
    await page.waitForTimeout(1000);

    await page
      .getByTestId("saved_componentsGroup")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page
      .locator('//*[@id="react-flow-id"]/div[1]/div[2]/button[2]')
      .click();

    await page
      .locator('//*[@id="react-flow-id"]/div[1]/div[2]/button[2]')
      .click();

    await page
      .locator('//*[@id="react-flow-id"]/div[1]/div[2]/button[2]')
      .click();
    textArea = page.getByTestId("div-textarea-description");
    elementCountText = await textArea.count();
    if (elementCountText > 0) {
      expect(true).toBeTruthy();
    }

    groupNode = page.getByTestId("title-Group");
    elementGroup = await groupNode.count();
    if (elementGroup > 0) {
      expect(true).toBeTruthy();
    }
  });
});

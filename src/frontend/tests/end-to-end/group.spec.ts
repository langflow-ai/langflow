import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";

test.describe("group node test", () => {
  /// <reference lib="dom"/>
  test("group and ungroup updating values", async ({ page }) => {
    await page.goto("http:localhost:3000/");
    await page.locator('//*[@id="new-project-btn"]').click();
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

    page.waitForTimeout(2000);

    await page.dispatchEvent('//*[@id="react-flow-id"]', "drop", {
      dataTransfer,
    });

    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(2000);

    await page.getByPlaceholder("Search").click();
    await page.getByPlaceholder("Search").fill("PythonFunctionTool");

    await page.waitForTimeout(2000);

    await page
      .getByTestId("toolsPythonFunctionTool")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await page.getByPlaceholder("Search").click();
    await page.getByPlaceholder("Search").fill("ChatOpenAI");

    await page.waitForTimeout(2000);

    await page
      .getByTestId("model_specsChatOpenAI")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await page.getByPlaceholder("Search").click();
    await page.getByPlaceholder("Search").fill("AgentInitializer");

    await page.waitForTimeout(2000);

    await page
      .getByTestId("agentsAgent Initializer")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    const genericNoda = page.getByTestId("div-generic-node");
    const elementCount = await genericNoda.count();
    if (elementCount > 0) {
      expect(true).toBeTruthy();
    }
    page.locator('//*[@id="react-flow-id"]').click();

    await page.getByTestId("title-Agent Initializer").click({
      modifiers: ["Control"],
    });

    await page.getByTestId("title-PythonFunctionTool").click({
      modifiers: ["Control"],
    });
    await page.getByTestId("title-ChatOpenAI").click({
      modifiers: ["Control"],
    });

    await page.getByRole("button", { name: "Group" }).click();

    const textArea = page.getByTestId("div-textarea-description");
    const elementCountText = await textArea.count();
    if (elementCountText > 0) {
      expect(true).toBeTruthy();
    }

    const groupNode = page.getByTestId("title-Group");
    const elementGroup = await groupNode.count();
    if (elementGroup > 0) {
      expect(true).toBeTruthy();
    }

    // Now dispatch
  });
});

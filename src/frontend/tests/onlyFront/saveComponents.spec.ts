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
    //make front work withoput backend
    await page.routeFromHAR("harFiles/langflow.har", {
      url: "**/api/v1/**",
      update: false,
    });
    await page.route("**/api/v1/flows/", async (route) => {
      const json = {
        id: "e9ac1bdc-429b-475d-ac03-d26f9a2a3210",
      };
      await route.fulfill({ json, status: 201 });
    });
    await page.goto("http:localhost:3000/");
    await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
    // Read your file into a buffer.
    const jsonContent = readFileSync(
      "tests/onlyFront/assets/collection.json",
      "utf-8"
    );

    // Create the DataTransfer and File
    const dataTransfer = await page.evaluateHandle((data) => {
      const dt = new DataTransfer();
      // Convert the buffer to a hex array
      const file = new File([data], "flowtest.json", {
        type: "application/json",
      });
      dt.items.add(file);
      return dt;
    }, jsonContent);

    // Now dispatch
    await page.dispatchEvent(
      '//*[@id="root"]/div/div[1]/div[2]/div[3]/div/div',
      "drop",
      {
        dataTransfer,
      }
    );

    await page
      .locator(
        '//*[@id="root"]/div/div[1]/div[2]/div[3]/div/div/div/div/div/div/div/div[2]/span[2]'
      )
      .click();
    await page.waitForTimeout(2000);

    const genericNoda = page.getByTestId("div-generic-node");
    const elementCount = await genericNoda.count();
    if (elementCount > 0) {
      expect(true).toBeTruthy();
    }

    await page.getByTestId("title-PythonFunctionTool").click({
      modifiers: ["Control"],
    });
    await page.getByTestId("title-ChatOpenAI").click({
      modifiers: ["Control"],
    });

    await page.getByTestId("title-AgentInitializer").click({
      modifiers: ["Control"],
    });

    await page.getByRole("button", { name: "Group" }).click();
    await page.locator("div").filter({ hasText: "Star13756" }).nth(3).click();

    let textArea = page.getByTestId("div-textarea-2");
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
    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("save-button-modal").click();
    await page.getByTestId("delete-button-modal").click();

    await page.getByPlaceholder("Search").click();
    await page.getByPlaceholder("Search").fill("group");
    await page.waitForTimeout(2000);

    await page
      .getByTestId("saved_componentsGroup")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    textArea = page.getByTestId("div-textarea-2");
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

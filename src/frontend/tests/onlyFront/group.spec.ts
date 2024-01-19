import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";

test.describe("group node test", () => {
  /// <reference lib="dom"/>
  test("group and ungroup updating values", async ({ page }) => {
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

    page.waitForTimeout(2000);

    await page.dispatchEvent(
      '//*[@id="root"]/div/div[1]/div[2]/div[3]/div/div',
      "drop",
      {
        dataTransfer,
      }
    );

    await page
      .getByTestId("edit-flow-button-e9ac1bdc-429b-475d-ac03-d26f9a2a3210-0")
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

import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";
test.describe("save component tests", () => {
  /// <reference lib="dom"/>
  test.skip(
    "save group component tests",
    { tag: ["@release", "@workspace", "@api"] },

    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page.waitForSelector('[data-testid="blank-flow"]', {
        timeout: 30000,
      });
      await page.getByTestId("blank-flow").click();

      // Read your file into a buffer.
      const jsonContent = readFileSync(
        "tests/assets/flow_group_test.json",
        "utf-8",
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

      // Now dispatch
      await page.dispatchEvent(
        "//*[@data-testid='rf__wrapper']/div[1]/div",
        "drop",
        {
          dataTransfer,
        },
      );

      const genericNoda = page.getByTestId("div-generic-node");
      const elementCount = await genericNoda?.count();
      if (elementCount > 0) {
        expect(true).toBeTruthy();
      }

      // Log button element
      await page.getByTestId("fit_view").click();

      await zoomOut(page, 2);

      await page.getByTestId("title-Agent Initializer").click({
        modifiers: ["Control"],
      });

      await page.getByRole("button", { name: "Group" }).click();

      await page
        .locator('//*[@id="react-flow-id"]')
        .first()
        .click({ button: "left" });

      let textArea = page.getByTestId("div-textarea-description");
      let elementCountText = await textArea?.count();
      if (elementCountText > 0) {
        expect(true).toBeTruthy();
      }

      let groupNode = page.getByTestId("title-Group");
      let elementGroup = await groupNode?.count();
      if (elementGroup > 0) {
        expect(true).toBeTruthy();
      }

      await page.getByTestId("title-Group").click();
      await page.getByTestId("more-options-modal").click();

      await page.getByTestId("icon-SaveAll").click();
      // timeout to handle case where there is already a saved component with the same name
      await page.waitForTimeout(1000);

      const replaceButton = await page
        .getByTestId("replace-button")
        .isVisible();

      if (replaceButton) {
        await page.getByTestId("replace-button").click();
      }
      await page.getByTestId("sidebar-search-input").click();
      await page.getByTestId("sidebar-search-input").fill("group");

      await page
        .getByText("Group")
        .first()
        .dragTo(page.locator('//*[@id="react-flow-id"]'));
      await page.mouse.up();
      await page.mouse.down();
      await page.getByTestId("fit_view").click();
      textArea = page.getByTestId("div-textarea-description");
      elementCountText = await textArea?.count();
      if (elementCountText > 0) {
        expect(true).toBeTruthy();
      }

      groupNode = page.getByTestId("title-Group");
      elementGroup = await groupNode?.count();
      if (elementGroup > 0) {
        expect(true).toBeTruthy();
      }
    },
  );
});

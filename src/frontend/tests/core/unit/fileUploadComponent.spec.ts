import { expect, test } from "@playwright/test";
import fs from "fs";
import path from "path";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { generateRandomFilename } from "../../utils/generate-filename";

test(
  "should be able to upload a file",
  {
    tag: ["@release", "@workspace"],
  },
  async ({ page }) => {
    // Generate unique filenames for this test run
    const sourceFileName = generateRandomFilename();
    const jsonFileName = generateRandomFilename();
    const renamedJsonFile = generateRandomFilename();
    const renamedTxtFile = generateRandomFilename();
    const newTxtFile = generateRandomFilename();

    // Read the test file content
    const testFilePath = path.join(__dirname, "../../assets/test_file.txt");
    const fileContent = fs.readFileSync(testFilePath);

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("file");

    await page.waitForSelector('[data-testid="dataFile"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("dataFile")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);
    const fileManagement = await page
      .getByTestId("button_open_file_management")
      ?.isVisible();
    if (fileManagement) {
      // Test upload file
      await page.getByTestId("button_open_file_management").click();
      const drag = await page.getByTestId("drag-files-component");
      const fileChooserPromise = page.waitForEvent("filechooser");
      await drag.click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles([
        {
          name: `${sourceFileName}.txt`,
          mimeType: "text/plain",
          buffer: fileContent,
        },
      ]);

      await expect(page.getByText(`${sourceFileName}.txt`).last()).toBeVisible({
        timeout: 1000,
      });

      await expect(
        page.getByTestId(`checkbox-${sourceFileName}`).last(),
      ).toHaveAttribute("data-state", "checked", { timeout: 1000 });

      // Create DataTransfer object and file
      const dataTransfer = await page.evaluateHandle((jsonFileName) => {
        const data = new DataTransfer();
        const file = new File(
          ['{ "test": "content" }'],
          `${jsonFileName}.json`,
          {
            type: "application/json",
          },
        );
        data.items.add(file);
        return data;
      }, jsonFileName);

      // Trigger drag events
      await page.dispatchEvent(
        '[data-testid="drag-files-component"]',
        "dragover",
        {
          dataTransfer,
        },
      );
      await page.dispatchEvent('[data-testid="drag-files-component"]', "drop", {
        dataTransfer,
      });

      await expect(page.getByText(`${jsonFileName}.json`).last()).toBeVisible({
        timeout: 1000,
      });

      await expect(
        page.getByTestId(`checkbox-${sourceFileName}`).last(),
      ).toHaveAttribute("data-state", "checked", { timeout: 1000 });

      // Test checkbox

      await expect(
        page.getByTestId(`checkbox-${sourceFileName}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${jsonFileName}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await page.getByTestId(`checkbox-${sourceFileName}`).last().click();
      await page.getByTestId(`checkbox-${jsonFileName}`).last().click();

      await expect(
        page.getByTestId(`checkbox-${sourceFileName}`).last(),
      ).toHaveAttribute("data-state", "unchecked");
      await expect(
        page.getByTestId(`checkbox-${jsonFileName}`).last(),
      ).toHaveAttribute("data-state", "unchecked");

      // Test search

      await page.getByTestId("search-files-input").fill(jsonFileName);
      await expect(page.getByText(`${jsonFileName}.json`).first()).toBeVisible({
        timeout: 1000,
      });
      await expect(page.getByText(`${sourceFileName}.txt`).first()).toBeHidden({
        timeout: 1000,
      });

      await page.getByTestId("search-files-input").fill(sourceFileName);
      await expect(page.getByText(`${sourceFileName}.txt`).first()).toBeVisible(
        {
          timeout: 1000,
        },
      );
      await expect(page.getByText(`${jsonFileName}.json`).first()).toBeHidden({
        timeout: 1000,
      });

      await page.getByTestId("search-files-input").fill("txt");
      await expect(page.getByText(`${sourceFileName}.txt`).first()).toBeVisible(
        {
          timeout: 1000,
        },
      );
      await expect(page.getByText(`${jsonFileName}.json`).first()).toBeHidden({
        timeout: 1000,
      });

      await page.getByTestId("search-files-input").fill("json");
      await expect(page.getByText(`${jsonFileName}.json`).first()).toBeVisible({
        timeout: 1000,
      });
      await expect(page.getByText(`${sourceFileName}.txt`).first()).toBeHidden({
        timeout: 1000,
      });

      await page.getByTestId("search-files-input").fill("");
      await expect(page.getByText(`${sourceFileName}.txt`).first()).toBeVisible(
        {
          timeout: 1000,
        },
      );
      await expect(page.getByText(`${jsonFileName}.json`).first()).toBeVisible({
        timeout: 1000,
      });

      await page
        .getByText(`${jsonFileName}.json`)
        .first()
        .click({ clickCount: 2 });
      await page
        .getByTestId(`rename-input-${jsonFileName}`)
        .fill(renamedJsonFile);
      await page.getByTestId(`rename-input-${jsonFileName}`).blur();
      await expect(
        page.getByText(`${renamedJsonFile}.json`).first(),
      ).toBeVisible({
        timeout: 1000,
      });
      await expect(page.getByText(`${jsonFileName}.json`).first()).toBeHidden({
        timeout: 1000,
      });

      await page.getByTestId(`context-menu-button-${sourceFileName}`).click();
      await page.getByTestId("btn-rename-file").click();
      await page
        .getByTestId(`rename-input-${sourceFileName}`)
        .fill(renamedTxtFile);
      await page.getByTestId(`rename-input-${sourceFileName}`).blur();
      await expect(page.getByText(`${renamedTxtFile}.txt`).first()).toBeVisible(
        {
          timeout: 1000,
        },
      );
      await expect(page.getByText(`${sourceFileName}.txt`).first()).toBeHidden({
        timeout: 1000,
      });

      await page.getByTestId(`checkbox-${renamedTxtFile}`).last().click();
      await page.getByTestId(`checkbox-${renamedJsonFile}`).last().click();

      await expect(
        page.getByTestId(`checkbox-${renamedTxtFile}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${renamedJsonFile}`).last(),
      ).toHaveAttribute("data-state", "checked");

      await page.getByTestId("select-files-modal-button").click();

      await expect(page.getByText(`${renamedTxtFile}.txt`).first()).toBeVisible(
        {
          timeout: 1000,
        },
      );
      await expect(
        page.getByText(`${renamedJsonFile}.json`).first(),
      ).toBeVisible({
        timeout: 1000,
      });
    } else {
      const fileChooserPromise = page.waitForEvent("filechooser");
      await page.getByTestId("button_upload_file").click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles([
        {
          name: `${sourceFileName}.txt`,
          mimeType: "text/plain",
          buffer: fileContent,
        },
      ]);
      await page.getByText(`${sourceFileName}.txt`).isVisible();
    }

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");

    await page
      .getByTestId("outputsChat Output")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 0, y: 0 },
      });

    await adjustScreenView(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("data to message");
    await page
      .getByTestId("processingData to Message")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 400 },
      });

    let visibleElementHandle;

    const elementsFile = await page
      .getByTestId("handle-file-shownode-data-right")
      .all();

    for (const element of elementsFile) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    // Click and hold on the first element
    await visibleElementHandle.hover();
    await page.mouse.down();

    // Move to the second element

    const parseDataElement = await page
      .getByTestId("handle-parsedata-shownode-data-left")
      .all();

    for (const element of parseDataElement) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    await visibleElementHandle.hover();

    // Release the mouse
    await page.mouse.up();

    await page
      .getByTestId("handle-parsedata-shownode-message-right")
      .first()
      .click();
    await page
      .getByTestId("handle-chatoutput-noshownode-text-target")
      .first()
      .click();

    await page.getByText("Playground", { exact: true }).last().click();

    await page.waitForSelector("text=Run Flow", {
      timeout: 30000,
    });

    await page.getByText("Run Flow", { exact: true }).last().click();

    await expect(page.getByText("this is a test file")).toBeVisible({
      timeout: 3000,
    });

    if (fileManagement) {
      await expect(page.getByText('{"test":"content"}')).toBeVisible({
        timeout: 3000,
      });
      await page.getByText("Close", { exact: true }).last().click();
      await page.getByTestId("button_open_file_management").click();
      await page.getByTestId(`context-menu-button-${renamedJsonFile}`).click();
      await page.getByTestId("btn-delete-file").click();
      await page.getByTestId("replace-button").click();
      await expect(page.getByText(`${renamedJsonFile}.txt`).first()).toBeHidden(
        {
          timeout: 1000,
        },
      );

      const dataTransfer = await page.evaluateHandle((newTxtFile) => {
        const data = new DataTransfer();
        const file = new File(["this is a new test"], `${newTxtFile}.txt`, {
          type: "text/plain",
        });
        data.items.add(file);
        return data;
      }, newTxtFile);

      // Trigger drag events
      await page.dispatchEvent(
        '[data-testid="drag-files-component"]',
        "dragover",
        {
          dataTransfer,
        },
      );
      await page.dispatchEvent('[data-testid="drag-files-component"]', "drop", {
        dataTransfer,
      });

      await expect(page.getByText(`${newTxtFile}.txt`).last()).toBeVisible({
        timeout: 1000,
      });

      await expect(
        page.getByTestId(`checkbox-${newTxtFile}`).last(),
      ).toHaveAttribute("data-state", "checked", { timeout: 1000 });

      await page.getByTestId("select-files-modal-button").click();
      await expect(page.getByText(`${renamedJsonFile}.txt`).first()).toBeHidden(
        {
          timeout: 1000,
        },
      );
      await expect(page.getByText(`${newTxtFile}.txt`).first()).toBeVisible({
        timeout: 1000,
      });
      await page.getByTestId(`remove-file-button-${renamedTxtFile}`).click();
      await page.getByText("Playground", { exact: true }).last().click();
      await page.getByTestId("icon-MoreHorizontal").last().click();
      await page.getByText("Delete", { exact: true }).last().click();

      await page.waitForSelector("text=Run Flow", {
        timeout: 30000,
      });

      await page.getByText("Run Flow", { exact: true }).last().click();

      await expect(page.getByText("this is a test file")).toBeHidden({
        timeout: 3000,
      });
      await expect(page.getByText('{ "test": "content" }')).toBeHidden({
        timeout: 3000,
      });
      await expect(page.getByText("this is a new test")).toBeVisible({
        timeout: 3000,
      });
    }
  },
);

import path from "path";

import { Page, expect } from "@playwright/test";
import fs from "fs";
import { generateRandomFilename } from "./generate-filename";

export async function uploadFile(page: Page, fileName: string) {
  const fileManagement = await page
    .getByTestId("button_open_file_management")
    ?.isVisible();

  if (!fileManagement) {
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("button_upload_file").click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(path.join(__dirname, `../assets/${fileName}`));
    await page.getByText(fileName).isVisible();
    return;
  }
  await page.getByTestId("button_open_file_management").first().click();
  const drag = await page.getByTestId("drag-files-component");
  const sourceFileName = generateRandomFilename();
  const testFilePath = path.join(__dirname, `../assets/${fileName}`);
  const testFileType = fileName.split(".").pop();
  const fileContent = fs.readFileSync(testFilePath);

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

  await page
    .getByText(sourceFileName + `.${testFileType}`)
    .last()
    .waitFor({ state: "visible", timeout: 1000 });

  const checkbox = page.getByTestId(`checkbox-${sourceFileName}`).last();
  await expect(checkbox).toHaveAttribute("data-state", "checked", {
    timeout: 3000,
  });

  await page.getByTestId("select-files-modal-button").click();

  await page
    .getByText(sourceFileName + `.${testFileType}`)
    .first()
    .waitFor({ state: "visible", timeout: 1000 });
}

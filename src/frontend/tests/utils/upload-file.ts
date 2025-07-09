import path from "path";

import { type Page, expect } from "@playwright/test";
import fs from "fs";
import { generateRandomFilename } from "./generate-filename";

// Function to get the correct mimeType based on file extension
function getMimeType(extension: string): string {
  const mimeTypes: Record<string, string> = {
    pdf: "application/pdf",
    json: "application/json",
    txt: "text/plain",
    csv: "text/csv",
    xml: "application/xml",
    html: "text/html",
    htm: "text/html",
    js: "text/javascript",
    css: "text/css",
    png: "image/png",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    gif: "image/gif",
    svg: "image/svg+xml",
    ico: "image/x-icon",
    yaml: "application/x-yaml",
    yml: "application/x-yaml",
    py: "text/x-python",
    md: "text/markdown",
  };

  return mimeTypes[extension.toLowerCase()] || "application/octet-stream";
}

export async function uploadFile(page: Page, fileName: string) {
  await page.getByTestId("fit_view").click();
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
  const testFileType = fileName.split(".").pop() || "";
  const fileContent = fs.readFileSync(testFilePath);

  const fileChooserPromise = page.waitForEvent("filechooser");
  await drag.click();

  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles([
    {
      name: `${sourceFileName}.${testFileType}`,
      mimeType: getMimeType(testFileType),
      buffer: fileContent,
    },
  ]);

  await page
    .getByText(sourceFileName + `.${testFileType}`)
    .last()
    .waitFor({ state: "visible", timeout: 3000 });

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

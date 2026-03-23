import type { Page } from "@playwright/test";
import fs from "fs";
import path from "path";
import { expect } from "../fixtures";
import { ensureCheckboxChecked } from "./ensure-checkbox-checked";
import { generateRandomFilename } from "./generate-filename";
import { unselectNodes } from "./unselect-nodes";

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
  await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
    timeout: 100000,
  });

  await page.getByTestId("canvas_controls_dropdown").click();
  await page.getByTestId("fit_view").click();
  await page.getByTestId("canvas_controls_dropdown").click({ force: true });

  try {
    await page
      .getByText("File", { exact: true })
      .last()
      .click({ timeout: 5000 });
  } catch (error) {
    // do nothing, means that it's using file management v1
  }

  const fileManagement = await page
    .getByTestId("button_open_file_management")
    .first()
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

  // Wait for the upload success toast to confirm the upload actually completed.
  // On Windows CI, a race condition in createFileUpload (focus fires before
  // change) can cause the upload to silently not happen, leaving only the
  // optimistic "temp" entry. Waiting for the toast ensures the HTTP upload
  // finished and handleUpload was called.
  await expect(page.getByText("uploaded successfully")).toBeVisible({
    timeout: 30000,
  });

  const checkbox = page.getByTestId(`checkbox-${sourceFileName}`).last();
  await ensureCheckboxChecked(checkbox);

  await page.getByTestId("select-files-modal-button").click();

  await page
    .getByText(sourceFileName + `.${testFileType}`)
    .first()
    .waitFor({ state: "visible", timeout: 1000 });

  await unselectNodes(page);
}

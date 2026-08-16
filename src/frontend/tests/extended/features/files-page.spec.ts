import type { Page, Response } from "@playwright/test";
import fs from "fs";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { generateRandomFilename } from "../../utils/generate-filename";

test.describe.configure({ mode: "serial" });

async function openFilesPage(page: Page) {
  await awaitBootstrapTest(page, {
    skipModal: true,
  });
  const filesResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === "/api/v2/files",
  );
  await page.getByText(TEXTS.labelMyFiles, { exact: true }).first().click();
  await page.waitForURL(/\/assets\/files\/?$/);
  const filesResponse = await filesResponsePromise;
  expect(filesResponse.ok()).toBe(true);
  expect(await filesResponse.finished()).toBeNull();
  await expect(page.getByTestId("mainpage_title")).toContainText("Files");
  await expect(page.getByTestId("drag-wrap-component")).toBeVisible();
}

const fileRow = (page: Page, filename: string) =>
  page.locator(".ag-row").filter({
    has: page.getByText(filename, { exact: true }),
  });

async function runAndWaitForUploads(
  page: Page,
  count: number,
  action: () => Promise<void>,
) {
  const responses: Response[] = [];
  const collectUpload = (response: Response) => {
    if (
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v2/files"
    ) {
      responses.push(response);
    }
  };
  page.on("response", collectUpload);

  try {
    await action();
    await expect
      .poll(() => responses.length, { timeout: TIMEOUTS.standard })
      .toBe(count);
    for (const response of responses) {
      expect(response.ok()).toBe(true);
    }
  } finally {
    page.off("response", collectUpload);
  }
}

test(
  "should navigate to files page and show empty state",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await openFilesPage(page);

    // Check for empty state when no files are present
    await expect(page.getByText("No files")).toBeVisible();
    await expect(
      page.getByText("Upload files or import from your preferred cloud."),
    ).toBeVisible();
    await expect(page.getByTestId("upload-file-btn")).toBeVisible();
  },
);

test(
  "should upload file using upload button",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    const fileName = generateRandomFilename();
    const testFilePath = path.join(__dirname, "../../assets/test-file.txt");
    const fileContent = fs.readFileSync(testFilePath);

    await openFilesPage(page);
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("upload-file-btn").click();

    const fileChooser = await fileChooserPromise;
    await runAndWaitForUploads(page, 1, () =>
      fileChooser.setFiles([
        {
          name: `${fileName}.txt`,
          mimeType: "text/plain",
          buffer: fileContent,
        },
      ]),
    );

    // Wait for upload success message
    await expect(page.getByText("File uploaded successfully")).toBeVisible();

    // Verify file appears in the list
    await expect(fileRow(page, `${fileName}.txt`)).toBeVisible();
  },
);

test(
  "should upload file using drag and drop",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    const fileName = generateRandomFilename();

    await openFilesPage(page);

    // Create DataTransfer object and file
    const dataTransfer = await page.evaluateHandle((fileName) => {
      const data = new DataTransfer();
      const file = new File(["test content"], `${fileName}.txt`, {
        type: "text/plain",
      });
      data.items.add(file);
      return data;
    }, fileName);

    // Trigger drag events
    await runAndWaitForUploads(page, 1, async () => {
      await page.dispatchEvent(
        '[data-testid="drag-wrap-component"]',
        "dragover",
        {
          dataTransfer,
        },
      );
      await page.dispatchEvent('[data-testid="drag-wrap-component"]', "drop", {
        dataTransfer,
      });
    });

    // Wait for upload success message
    await expect(page.getByText("File uploaded successfully")).toBeVisible();

    // Verify file appears in the list
    await expect(fileRow(page, `${fileName}.txt`)).toBeVisible();
  },
);

test(
  "should upload multiple files with different types",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    const fileNames = {
      txt: generateRandomFilename(),
      json: generateRandomFilename(),
      py: generateRandomFilename(),
    };

    const testFiles = [
      path.join(__dirname, "../../assets/test-file.txt"),
      path.join(__dirname, "../../assets/test-file.json"),
      path.join(__dirname, "../../assets/test-file.py"),
    ];

    const fileContents = testFiles.map((file) => fs.readFileSync(file));

    await openFilesPage(page);
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("upload-file-btn").click();

    // Create a file input for upload
    const fileChooser = await fileChooserPromise;

    // Upload multiple test files
    await runAndWaitForUploads(page, 3, () =>
      fileChooser.setFiles([
        {
          name: `${fileNames.txt}.txt`,
          mimeType: "text/plain",
          buffer: fileContents[0],
        },
        {
          name: `${fileNames.json}.json`,
          mimeType: "application/json",
          buffer: fileContents[1],
        },
        {
          name: `${fileNames.py}.py`,
          mimeType: "text/x-python",
          buffer: fileContents[2],
        },
      ]),
    );

    // Wait for upload success message
    await expect(page.getByText("Files uploaded successfully")).toBeVisible();

    // Verify all files appear in the list
    for (const [extension, name] of Object.entries(fileNames)) {
      await expect(fileRow(page, `${name}.${extension}`)).toBeVisible();
    }
  },
);

test(
  "should search uploaded files",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    const fileNames = {
      txt: generateRandomFilename(),
      json: generateRandomFilename(),
      py: generateRandomFilename(),
    };

    const testFiles = [
      path.join(__dirname, "../../assets/test-file.txt"),
      path.join(__dirname, "../../assets/test-file.json"),
      path.join(__dirname, "../../assets/test-file.py"),
    ];

    const fileContents = testFiles.map((file) => fs.readFileSync(file));

    await openFilesPage(page);
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("upload-file-btn").click();

    const fileChooser = await fileChooserPromise;

    await runAndWaitForUploads(page, 3, () =>
      fileChooser.setFiles([
        {
          name: `${fileNames.txt}.txt`,
          mimeType: "text/plain",
          buffer: fileContents[0],
        },
        {
          name: `${fileNames.json}.json`,
          mimeType: "application/json",
          buffer: fileContents[1],
        },
        {
          name: `${fileNames.py}.py`,
          mimeType: "text/x-python",
          buffer: fileContents[2],
        },
      ]),
    );

    await expect(page.getByText("Files uploaded successfully")).toBeVisible();

    const txtRow = fileRow(page, `${fileNames.txt}.txt`);
    const jsonRow = fileRow(page, `${fileNames.json}.json`);
    const pyRow = fileRow(page, `${fileNames.py}.py`);

    // Test search by file name
    const searchInput = await page.getByTestId("search-store-input");
    await searchInput.fill(fileNames.json);

    // Verify only JSON file is visible
    await expect(jsonRow).toBeVisible();
    await expect(txtRow).toHaveCount(0);
    await expect(pyRow).toHaveCount(0);

    // Test search by file type
    await searchInput.fill(".py");

    // Verify only Python file is visible
    await expect(pyRow).toBeVisible();
    await expect(jsonRow).toHaveCount(0);
    await expect(txtRow).toHaveCount(0);

    // Clear search and verify all files are visible again
    await searchInput.fill("");
    await expect(txtRow).toBeVisible();
    await expect(jsonRow).toBeVisible();
    await expect(pyRow).toBeVisible();
  },
);

test(
  "should handle bulk actions for multiple files",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    const fileNames = {
      txt: generateRandomFilename(),
      json: generateRandomFilename(),
      py: generateRandomFilename(),
    };

    const testFiles = [
      path.join(__dirname, "../../assets/test-file.txt"),
      path.join(__dirname, "../../assets/test-file.json"),
      path.join(__dirname, "../../assets/test-file.py"),
    ];

    const fileContents = testFiles.map((file) => fs.readFileSync(file));

    await openFilesPage(page);
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("upload-file-btn").click();

    const fileChooser = await fileChooserPromise;
    await runAndWaitForUploads(page, 3, () =>
      fileChooser.setFiles([
        {
          name: `${fileNames.txt}.txt`,
          mimeType: "text/plain",
          buffer: fileContents[0],
        },
        {
          name: `${fileNames.json}.json`,
          mimeType: "application/json",
          buffer: fileContents[1],
        },
        {
          name: `${fileNames.py}.py`,
          mimeType: "text/x-python",
          buffer: fileContents[2],
        },
      ]),
    );

    // Wait for upload success message
    await expect(page.getByText("Files uploaded successfully")).toBeVisible();

    // Verify all files appear in the list
    for (const [extension, name] of Object.entries(fileNames)) {
      await expect(fileRow(page, `${name}.${extension}`)).toBeVisible();
    }

    // Select files using their specific row checkboxes
    const txtRow = fileRow(page, `${fileNames.txt}.txt`);
    const jsonRow = fileRow(page, `${fileNames.json}.json`);
    const pyRow = fileRow(page, `${fileNames.py}.py`);
    const txtCheckbox = txtRow.locator('input[data-ref="eInput"]');
    const jsonCheckbox = jsonRow.locator('input[data-ref="eInput"]');
    const pyCheckbox = pyRow.locator('input[data-ref="eInput"]');

    await txtCheckbox.click();
    await jsonCheckbox.click();
    await pyCheckbox.click();

    await expect(txtCheckbox).toBeChecked();
    await expect(jsonCheckbox).toBeChecked();
    await expect(pyCheckbox).toBeChecked();

    // Check if the bulk actions toolbar appears
    const deleteButton = await page.getByTestId("bulk-delete-btn");
    await expect(deleteButton).toBeVisible();

    // Deselect one file (checkbox on the grid)
    await pyCheckbox.click();
    await expect(pyCheckbox).not.toBeChecked();

    // Check if the bulk actions toolbar still appears
    await expect(deleteButton).toBeVisible();

    // Test delete functionality
    await deleteButton.click();

    // Confirm the delete in the modal
    const confirmDeleteButton = await page.getByRole("button", {
      name: TEXTS.delete,
    });
    const [deleteResponse] = await Promise.all([
      page.waitForResponse(
        (response) =>
          response.request().method() === "DELETE" &&
          new URL(response.url()).pathname === "/api/v2/files/batch/",
      ),
      confirmDeleteButton.click(),
    ]);
    expect(deleteResponse.ok()).toBe(true);

    // Check for success message
    await expect(page.getByText("Files deleted successfully")).toBeVisible();
    await expect(txtRow).toHaveCount(0);
    await expect(jsonRow).toHaveCount(0);
    await expect(pyRow).toBeVisible();
  },
);

import { expect, test } from "@playwright/test";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "should navigate to files page and show empty state",
  { tag: ["@release", "@files"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    // Wait for the sidebar to be visible
    await page.waitForSelector('[data-testid="folder-sidebar"]', {
      timeout: 30000,
    });

    // Click on the files button
    await page.getByText("My Files").first().click();

    // Check if we're on the files page
    await page.waitForSelector('[data-testid="mainpage_title"]');
    const title = await page.getByTestId("mainpage_title");
    expect(await title.textContent()).toContain("My Files");

    // Check for empty state when no files are present
    const noFilesText = await page.getByText("No files");
    expect(noFilesText).toBeTruthy();

    const uploadMessage = await page.getByText(
      "Upload files or import from your preferred cloud.",
    );
    expect(uploadMessage).toBeTruthy();

    // Check if upload buttons are present
    const uploadButton = await page.getByText("Upload");
    expect(uploadButton).toBeTruthy();
  },
);

test(
  "should upload file using upload button",
  { tag: ["@release", "@files"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    // Navigate to files page
    await page.waitForSelector('[data-testid="folder-sidebar"]', {
      timeout: 30000,
    });
    await page.getByText("My Files").first().click();
    await page.getByTestId("upload-file-btn").click();

    // Create a file input for upload
    const fileInput = await page.waitForSelector('input[type="file"]', {
      state: "attached",
    });

    // Upload a test file
    const testFilePath = path.join(__dirname, "../../assets/test-file.txt");
    await fileInput.setInputFiles(testFilePath);

    // Wait for upload success message
    const successMessage = await page.getByText("File uploaded successfully");
    expect(successMessage).toBeTruthy();

    // Verify file appears in the list
    const fileName = await page.getByText("test-file");
    const fileType = await page.getByText("TXT", { exact: true });
    expect(await fileName.isVisible()).toBeTruthy();
    expect(await fileType.isVisible()).toBeTruthy();
  },
);

test(
  "should upload file using drag and drop",
  { tag: ["@release", "@files"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    // Navigate to files page
    await page.waitForSelector('[data-testid="folder-sidebar"]', {
      timeout: 30000,
    });
    await page.getByText("My Files").first().click();

    // Create DataTransfer object and file
    const dataTransfer = await page.evaluateHandle(() => {
      const data = new DataTransfer();
      const file = new File(["test content"], "drag-test.txt", {
        type: "text/plain",
      });
      data.items.add(file);
      return data;
    });

    // Trigger drag events
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

    // Wait for upload success message
    const successMessage = await page.getByText("File uploaded successfully");
    expect(successMessage).toBeTruthy();

    // Verify file appears in the list
    const fileName = await page.getByText("drag-test");
    const fileType = await page.getByText("TXT", { exact: true }).last();
    expect(await fileName.isVisible()).toBeTruthy();
    expect(await fileType.isVisible()).toBeTruthy();
  },
);

test(
  "should upload multiple files with different types",
  { tag: ["@release", "@files"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    // Navigate to files page
    await page.waitForSelector('[data-testid="folder-sidebar"]', {
      timeout: 30000,
    });
    await page.getByText("My Files").first().click();
    await page.getByTestId("upload-file-btn").click();

    // Create a file input for upload
    const fileInput = await page.waitForSelector('input[type="file"]', {
      state: "attached",
    });

    // Upload multiple test files
    const testFiles = [
      path.join(__dirname, "../../assets/test-file.txt"),
      path.join(__dirname, "../../assets/test-file.json"),
      path.join(__dirname, "../../assets/test-file.py"),
    ];
    await fileInput.setInputFiles(testFiles);

    // Wait for upload success message
    const successMessage = await page.getByText("Files uploaded successfully");
    expect(successMessage).toBeTruthy();

    // Verify all files appear in the list
    const file = await page.getByText("test-file").last();

    expect(file).toBeTruthy();

    // Verify file types are displayed correctly
    const txtType = await page.getByText("TXT", { exact: true });
    const jsonType = await page.getByText("JSON", { exact: true });
    const pyType = await page.getByText("PY", { exact: true });

    expect(txtType).toBeTruthy();
    expect(jsonType).toBeTruthy();
    expect(pyType).toBeTruthy();
  },
);

test(
  "should search uploaded files",
  { tag: ["@release", "@files"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    // Navigate to files page
    await page.waitForSelector('[data-testid="folder-sidebar"]', {
      timeout: 30000,
    });
    await page.getByText("My Files").first().click();
    await page.getByTestId("upload-file-btn").click();

    // Upload test files first
    const fileInput = await page.waitForSelector('input[type="file"]', {
      state: "attached",
    });
    const testFiles = [
      path.join(__dirname, "../../assets/test-file.txt"),
      path.join(__dirname, "../../assets/test-file.json"),
      path.join(__dirname, "../../assets/test-file.py"),
    ];
    await fileInput.setInputFiles(testFiles);
    const successMessage = await page.getByText("Files uploaded successfully");
    expect(successMessage).toBeTruthy();

    // Test search by file name
    const searchInput = await page.getByTestId("search-store-input");
    await searchInput.fill("json");
    await page.waitForTimeout(100);

    let file = await page.getByText("test-file");

    // Verify only JSON file is visible
    const jsonFile = await page.getByText("JSON", { exact: true }).last();
    expect(await file.last().isVisible()).toBeTruthy();
    expect(jsonFile).toBeTruthy();

    // Verify other files are not visible
    const txtFile = await page.getByText("TXT", { exact: true }).last();
    const pyFile = await page.getByText("PY", { exact: true }).last();
    expect(await txtFile.isVisible()).toBeFalsy();
    expect(await pyFile.isVisible()).toBeFalsy();

    // Test search by file type
    await searchInput.fill("py");
    await page.waitForTimeout(100);
    file = await page.getByText("test-file");

    // Verify only Python file is visible
    expect(await file.last().isVisible()).toBeTruthy();
    expect(await pyFile.isVisible()).toBeTruthy();
    expect(await jsonFile.isVisible()).toBeFalsy();
    expect(await txtFile.isVisible()).toBeFalsy();

    // Clear search and verify all files are visible again
    await searchInput.fill("");
    await page.waitForTimeout(100);
    file = await page.getByText("test-file");

    expect(await file.last().isVisible()).toBeTruthy();
    expect(await txtFile.isVisible()).toBeTruthy();
    expect(await jsonFile.isVisible()).toBeTruthy();
    expect(await pyFile.isVisible()).toBeTruthy();
  },
);

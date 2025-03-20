import { expect, test } from "@playwright/test";
import fs from "fs";
import path from "path";
import { addFlowToTestOnEmptyLangflow } from "../../utils/add-flow-to-test-on-empty-langflow";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { generateRandomFilename } from "../../utils/generate-filename";

// Configure tests to run serially with a delay between each test
test(
  "should navigate to files page and show empty state",
  { tag: ["@release", "@files"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-folder-description")
      .count();

    if (firstRunLangflow > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }

    await page.waitForSelector('[data-testid="mainpage_title"]', {
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
    const fileName = generateRandomFilename();
    const testFilePath = path.join(__dirname, "../../assets/test-file.txt");
    const fileContent = fs.readFileSync(testFilePath);

    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-folder-description")
      .count();

    if (firstRunLangflow > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.getByText("My Files").first().click();
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("upload-file-btn").click();

    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles([
      {
        name: `${fileName}.txt`,
        mimeType: "text/plain",
        buffer: fileContent,
      },
    ]);

    // Wait for upload success message
    const successMessage = await page.getByText("File uploaded successfully");
    expect(successMessage).toBeTruthy();

    // Verify file appears in the list
    const uploadedFileName = await page.getByText(fileName + ".txt");
    expect(await uploadedFileName.isVisible()).toBeTruthy();
  },
);

test(
  "should upload file using drag and drop",
  { tag: ["@release", "@files"] },
  async ({ page }) => {
    const fileName = generateRandomFilename();

    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-folder-description")
      .count();

    if (firstRunLangflow > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.getByText("My Files").first().click();

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
    const uploadedFileName = await page.getByText(fileName + ".txt").last();
    await expect(uploadedFileName).toBeVisible({
      timeout: 1000,
    });
  },
);

test(
  "should upload multiple files with different types",
  { tag: ["@release", "@files"] },
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

    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-folder-description")
      .count();

    if (firstRunLangflow > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.getByText("My Files").first().click();
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("upload-file-btn").click();

    // Create a file input for upload
    const fileChooser = await fileChooserPromise;

    // Upload multiple test files
    await fileChooser.setFiles([
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
    ]);

    // Wait for upload success message
    const successMessage = await page.getByText("Files uploaded successfully");
    expect(successMessage).toBeTruthy();

    // Verify all files appear in the list
    for (const name of Object.values(fileNames)) {
      const file = await page.getByText(name).last();
      await expect(file).toBeVisible({
        timeout: 1000,
      });
    }
  },
);

test(
  "should search uploaded files",
  { tag: ["@release", "@files"] },
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

    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-folder-description")
      .count();

    if (firstRunLangflow > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.getByText("My Files").first().click();
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("upload-file-btn").click();

    const fileChooser = await fileChooserPromise;

    await fileChooser.setFiles([
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
    ]);

    const successMessage = await page.getByText("Files uploaded successfully");
    expect(successMessage).toBeTruthy();

    // Test search by file name
    const searchInput = await page.getByTestId("search-store-input");
    await searchInput.fill(fileNames.json);
    await page.waitForTimeout(100);

    // Verify only JSON file is visible
    expect(
      await page.getByText(fileNames.json + ".json").isVisible(),
    ).toBeTruthy();

    // Verify other files are not visible
    expect(
      await page.getByText(fileNames.txt + ".txt").isVisible(),
    ).toBeFalsy();
    expect(await page.getByText(fileNames.py + ".py").isVisible()).toBeFalsy();

    // Test search by file type
    await searchInput.fill("py");
    await page.waitForTimeout(100);

    // Verify only Python file is visible
    expect(await page.getByText(fileNames.py + ".py").isVisible()).toBeTruthy();

    expect(
      await page.getByText(fileNames.json + ".json").isVisible(),
    ).toBeFalsy();
    expect(
      await page.getByText(fileNames.txt + ".txt").isVisible(),
    ).toBeFalsy();

    // Clear search and verify all files are visible again
    await searchInput.fill("");
    await page.waitForTimeout(100);

    for (const name of Object.values(fileNames)) {
      expect(await page.getByText(name).isVisible()).toBeTruthy();
    }
  },
);

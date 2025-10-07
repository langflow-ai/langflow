import fs from "fs";
import path from "path";
import { expect, test } from "../../fixtures";
import { addFlowToTestOnEmptyLangflow } from "../../utils/add-flow-to-test-on-empty-langflow";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { generateRandomFilename } from "../../utils/generate-filename";

// Configure tests to run serially with a delay between each test
test(
  "should navigate to files page and show empty state",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-project-description")
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
    expect(await title.textContent()).toContain("Files");

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
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    const fileName = generateRandomFilename();
    const testFilePath = path.join(__dirname, "../../assets/test-file.txt");
    const fileContent = fs.readFileSync(testFilePath);

    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-project-description")
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
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    const fileName = generateRandomFilename();

    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-project-description")
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

    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-project-description")
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

    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-project-description")
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

    await awaitBootstrapTest(page, { skipModal: true });

    const firstRunLangflow = await page
      .getByTestId("empty-project-description")
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

    // Select files with shift (checkbox on the grid)

    await page.keyboard.down("Shift");
    await page.locator('input[data-ref="eInput"]').nth(5).click();
    await page.locator('input[data-ref="eInput"]').nth(7).click();
    await page.keyboard.up("Shift");

    expect(
      await page.locator('input[data-ref="eInput"]').nth(5).isChecked(),
    ).toBe(true);
    expect(
      await page.locator('input[data-ref="eInput"]').nth(6).isChecked(),
    ).toBe(true);
    expect(
      await page.locator('input[data-ref="eInput"]').nth(7).isChecked(),
    ).toBe(true);

    // Check if the bulk actions toolbar appears
    const selectedCountText = await page.getByText("3 selected");
    await expect(selectedCountText).toBeVisible();

    // Check if download button is visible
    const downloadButton = await page.getByTestId("bulk-download-btn");
    await expect(downloadButton).toBeVisible();

    // Set up download listener
    const downloadPromise = page.waitForEvent("download");

    // Click download button
    await downloadButton.click();

    // Wait for download to start
    const download = await downloadPromise;

    // Verify the download was initiated
    await expect(download).toBeTruthy();

    // Check for success message
    const downloadSuccessMessage = await page.getByText(
      /Files? downloaded successfully/,
    );
    await expect(downloadSuccessMessage).toBeTruthy();

    // Select both files (checkbox on the grid)

    await page.locator('input[data-ref="eInput"]').nth(7).click();

    // Check if the bulk actions toolbar appears
    const selectedCountTextDelete = await page.getByText("2 selected");
    await expect(selectedCountTextDelete).toBeVisible();

    const deleteButton = await page.getByTestId("bulk-delete-btn");
    await expect(deleteButton).toBeVisible();

    // Test delete functionality
    await deleteButton.click();

    // Confirm the delete in the modal
    const confirmDeleteButton = await page.getByRole("button", {
      name: "Delete",
    });
    await confirmDeleteButton.click();

    // Check for success message
    const deleteSuccessMessage = await page.getByText(
      "Files deleted successfully",
    );
    await expect(deleteSuccessMessage).toBeTruthy();
    await page.waitForTimeout(500);

    // Verify the deleted files are no longer visible
    const remainingFileCount =
      (await page.getByText(fileNames.py + ".py").count()) +
      (await page.getByText(fileNames.txt + ".txt").count()) +
      (await page.getByText(fileNames.json + ".json").count());
    await expect(remainingFileCount).toBe(1);
  },
);

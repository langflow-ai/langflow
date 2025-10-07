import fs from "fs";
import path from "path";
import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
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

    await addLegacyComponents(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("file");

    await page.waitForSelector('[data-testid="dataRead File"]', {
      timeout: 10000,
    });

    await page
      .getByTestId("dataRead File")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);
    await page.waitForTimeout(2000);
    const fileManagement = await page
      .getByTestId("button_open_file_management")
      ?.isVisible({ timeout: 10000 });
    if (fileManagement) {
      // Test upload file
      await page.getByTestId("button_open_file_management").click();

      const drag = await page.getByTestId("drag-files-component");
      const fileChooserPromise = page.waitForEvent("filechooser", {
        timeout: 30000,
      });
      await drag.click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles([
        {
          name: `${sourceFileName}.txt`,
          mimeType: "text/plain",
          buffer: fileContent,
        },
      ]);

      // Test available types
      await expect(page.getByText("csv, json, pdf")).toBeVisible();
      await page.getByTestId("info-types").hover();
      await expect(
        page.getByText(
          "adoc, asc, asciidoc, bmp, bz2, docm, docx, dotm, dotx, gz, htm, html, jpeg, jpg, js, md, mdx, png, potm, potx, ppsm, ppsx, pptm, pptx, py, sh, sql, tar, tgz, tiff, ts, tsx, txt, webp, xhtml, xls, xlsx, xml, yaml, yml, zip",
          { exact: false },
        ),
      ).toBeVisible();

      await page.getByText("My Files").first().hover();
      await page.waitForTimeout(500);

      await expect(page.getByText(`${sourceFileName}.txt`).last()).toBeVisible({
        timeout: 5000,
      });

      await expect(
        page.getByTestId(`checkbox-${sourceFileName}`).last(),
      ).toHaveAttribute("data-state", "checked", { timeout: 5000 });

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
        timeout: 5000,
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

      await page.getByTestId(`context-menu-button-${jsonFileName}`).click();
      await page.getByTestId("btn-rename-file").click();
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
      const fileChooserPromise = page.waitForEvent("filechooser", {
        timeout: 30000,
      });
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
      .getByTestId("input_outputChat Output")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 200 },
      });

    await adjustScreenView(page);

    await page.getByTestId("handle-file-shownode-files-right").first().click();

    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .first()
      .click();

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await page.waitForSelector("text=Run Flow", {
      timeout: 30000,
    });

    await page.getByText("Run Flow", { exact: true }).last().click();

    await expect(page.getByText("this is a test file")).toBeVisible({
      timeout: 10000,
    });

    if (fileManagement) {
      await expect(page.getByText('{"test":"content"}')).toBeVisible({
        timeout: 10000,
      });
      await page.getByText("Close", { exact: true }).last().click();
      await page.getByTestId("button_open_file_management").click();
      await page.getByTestId(`context-menu-button-${renamedJsonFile}`).click();
      await page.getByTestId("btn-delete-file").click();
      await page.getByTestId("replace-button").click();
      await expect(page.getByText(`${renamedJsonFile}.txt`).first()).toBeHidden(
        {
          timeout: 10000,
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
      ).toHaveAttribute("data-state", "checked", { timeout: 10000 });

      await page.getByTestId("select-files-modal-button").click();
      await expect(page.getByText(`${renamedJsonFile}.txt`).first()).toBeHidden(
        {
          timeout: 10000,
        },
      );
      await expect(page.getByText(`${newTxtFile}.txt`).first()).toBeVisible({
        timeout: 10000,
      });
      await page.getByTestId(`remove-file-button-${renamedTxtFile}`).click();

      await page
        .getByTestId("handle-file-shownode-raw content-right")
        .first()
        .click();

      await page
        .getByTestId("handle-chatoutput-noshownode-inputs-target")
        .first()
        .click();

      await page
        .getByRole("button", { name: "Playground", exact: true })
        .click();
      await page.getByTestId("icon-MoreHorizontal").last().click();
      await page.getByText("Delete", { exact: true }).last().click();

      await page.waitForSelector("text=Run Flow", {
        timeout: 30000,
      });

      await page.getByText("Run Flow", { exact: true }).last().click();

      await expect(page.getByText("this is a test file")).toBeHidden({
        timeout: 10000,
      });
      await expect(page.getByText('{ "test": "content" }')).toBeHidden({
        timeout: 10000,
      });
      await expect(page.getByText("this is a new test")).toBeVisible({
        timeout: 10000,
      });
    }
  },
);

test(
  "should be able to select multiple files with shift-click",
  {
    tag: ["@release", "@workspace"],
  },
  async ({ page }) => {
    // Generate unique filenames for this test run
    const file1 = generateRandomFilename();
    const file2 = generateRandomFilename();
    const file3 = generateRandomFilename();
    const file4 = generateRandomFilename();
    const file5 = generateRandomFilename();

    // Read the test file content
    const testFilePath = path.join(__dirname, "../../assets/test_file.txt");
    const _fileContent = fs.readFileSync(testFilePath);

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("file");

    await page.waitForSelector('[data-testid="dataRead File"]', {
      timeout: 10000,
    });

    await page
      .getByTestId("dataRead File")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    // Check if file management button is visible
    const fileManagement = await page
      .getByTestId("button_open_file_management")
      ?.isVisible();

    if (fileManagement) {
      // Open file management modal
      await page.getByTestId("button_open_file_management").click();

      // Upload 5 files for testing shift-click selection
      // Upload file 1
      const createFileTransfer = async (
        filename: string,
        content: string,
        type: string,
      ) => {
        return page.evaluateHandle(
          (params) => {
            const data = new DataTransfer();
            const file = new File(
              [params.content],
              `${params.filename}.${params.type}`,
              { type: params.mimeType },
            );
            data.items.add(file);
            return data;
          },
          {
            filename,
            content,
            type,
            mimeType: type === "txt" ? "text/plain" : "application/json",
          },
        );
      };

      // Upload five files
      const files = [
        { name: file1, content: "file content 1", type: "txt" },
        { name: file2, content: "file content 2", type: "txt" },
        { name: file3, content: "file content 3", type: "txt" },
        { name: file4, content: "file content 4", type: "txt" },
        { name: file5, content: "file content 5", type: "txt" },
      ];

      for (const file of files) {
        const dataTransfer = await createFileTransfer(
          file.name,
          file.content,
          file.type,
        );

        // Trigger drag events
        await page.dispatchEvent(
          '[data-testid="drag-files-component"]',
          "dragover",
          { dataTransfer },
        );
        await page.dispatchEvent(
          '[data-testid="drag-files-component"]',
          "drop",
          { dataTransfer },
        );

        // Verify file was uploaded
        await expect(
          page.getByText(`${file.name}.${file.type}`).last(),
        ).toBeVisible({
          timeout: 1000,
        });
      }

      // Unselect all files first
      for (const file of files) {
        if (
          (await page
            .getByTestId(`checkbox-${file.name}`)
            .last()
            .getAttribute("data-state")) === "checked"
        ) {
          await page.getByTestId(`checkbox-${file.name}`).last().click();
          await page.waitForTimeout(500);
        }
      }

      // Test 1: Select first file, then shift-click the third file
      // First file
      await page.getByTestId(`checkbox-${file1}`).last().click();
      await page.waitForTimeout(500);

      // Hold shift and click third file
      await page.keyboard.down("Shift");
      await page.getByTestId(`checkbox-${file3}`).last().click();
      await page.waitForTimeout(500);
      await page.keyboard.up("Shift");
      await page.waitForTimeout(500);

      // Verify files 1, 2, and 3 are selected
      await expect(
        page.getByTestId(`checkbox-${file1}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file2}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file3}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file4}`).last(),
      ).toHaveAttribute("data-state", "unchecked");
      await expect(
        page.getByTestId(`checkbox-${file5}`).last(),
      ).toHaveAttribute("data-state", "unchecked");

      // Test 2: Shift-click to extend selection to file 5
      await page.keyboard.down("Shift");
      await page.getByTestId(`checkbox-${file5}`).last().click();
      await page.keyboard.up("Shift");

      // Verify all files are selected
      await expect(
        page.getByTestId(`checkbox-${file1}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file2}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file3}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file4}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file5}`).last(),
      ).toHaveAttribute("data-state", "checked");

      // Test 3: Unselect a range with shift-click
      // First select only file 2
      for (const file of files) {
        if (
          (await page
            .getByTestId(`checkbox-${file.name}`)
            .last()
            .getAttribute("data-state")) === "checked"
        ) {
          await page.getByTestId(`checkbox-${file.name}`).last().click();
        }
      }
      await page.getByTestId(`checkbox-${file2}`).last().click();

      // Select file 2 through 4
      await page.keyboard.down("Shift");
      await page.getByTestId(`checkbox-${file4}`).last().click();
      await page.keyboard.up("Shift");

      // Verify files 2, 3, and 4 are selected
      await expect(
        page.getByTestId(`checkbox-${file1}`).last(),
      ).toHaveAttribute("data-state", "unchecked");
      await expect(
        page.getByTestId(`checkbox-${file2}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file3}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file4}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file5}`).last(),
      ).toHaveAttribute("data-state", "unchecked");

      // Now use shift-click on an already selected range to deselect
      await page.keyboard.down("Shift");
      await page.getByTestId(`checkbox-${file2}`).last().click();
      await page.keyboard.up("Shift");

      // Verify the range is now deselected
      await expect(
        page.getByTestId(`checkbox-${file1}`).last(),
      ).toHaveAttribute("data-state", "unchecked");
      await expect(
        page.getByTestId(`checkbox-${file2}`).last(),
      ).toHaveAttribute("data-state", "checked");
      await expect(
        page.getByTestId(`checkbox-${file3}`).last(),
      ).toHaveAttribute("data-state", "unchecked");
      await expect(
        page.getByTestId(`checkbox-${file4}`).last(),
      ).toHaveAttribute("data-state", "unchecked");
      await expect(
        page.getByTestId(`checkbox-${file5}`).last(),
      ).toHaveAttribute("data-state", "unchecked");

      // Close the modal
      await page.getByTestId("select-files-modal-button").click();
    }
  },
);

test(
  "should show PSD file as disabled in file component",
  {
    tag: ["@release", "@workspace"],
  },
  async ({ page }) => {
    // Generate unique filenames for this test run
    const psdFileName = generateRandomFilename();
    const txtFileName = generateRandomFilename();

    // Create PSD content (just a mock)
    const psdFileContent = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
      "base64",
    );

    // Read the test file content for text file
    const testFilePath = path.join(__dirname, "../../assets/test_file.txt");
    const txtFileContent = fs.readFileSync(testFilePath);

    // Step 1: First navigate to files page and upload both files
    await awaitBootstrapTest(page, { skipModal: true });

    // Navigate to My Files page
    await page.getByText("My Files").first().click();

    // Check if we're on the files page
    await page.waitForSelector('[data-testid="mainpage_title"]');
    const title = await page.getByTestId("mainpage_title");
    expect(await title.textContent()).toContain("Files");

    // Upload the PSD file
    const fileChooserPromisePsd = page.waitForEvent("filechooser", {
      timeout: 30000,
    });
    await page.getByTestId("upload-file-btn").click();

    const fileChooserPsd = await fileChooserPromisePsd;
    await fileChooserPsd.setFiles([
      {
        name: `${psdFileName}.psd`,
        mimeType: "image/vnd.adobe.photoshop",
        buffer: psdFileContent,
      },
    ]);

    // Wait for upload success message
    await expect(page.getByText("File uploaded successfully")).toBeVisible({
      timeout: 10000,
    });

    // Verify PSD file appears in the list
    await expect(page.getByText(`${psdFileName}.psd`)).toBeVisible({
      timeout: 5000,
    });

    // Upload the TXT file
    const fileChooserPromiseTxt = page.waitForEvent("filechooser", {
      timeout: 30000,
    });
    await page.getByTestId("upload-file-btn").click();

    const fileChooserTxt = await fileChooserPromiseTxt;
    await fileChooserTxt.setFiles([
      {
        name: `${txtFileName}.txt`,
        mimeType: "text/plain",
        buffer: txtFileContent,
      },
    ]);

    // Wait for upload success message
    await expect(page.getByText("File uploaded successfully")).toBeVisible({
      timeout: 10000,
    });

    // Verify TXT file appears in the list
    await expect(page.getByText(`${txtFileName}.txt`)).toBeVisible({
      timeout: 5000,
    });

    // Step 2: Create a flow with File component and check if PSD file is disabled
    // Navigate to workspace page
    await page.getByText("Starter Project").first().click();

    await awaitBootstrapTest(page, { skipGoto: true });

    // Create a new flow
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    // Add a file component to the flow
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("file");

    await page.waitForSelector('[data-testid="dataRead File"]', {
      timeout: 10000,
    });

    await page
      .getByTestId("dataRead File")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    // Open the file management modal
    await page.getByTestId("button_open_file_management").click();
    console.warn(psdFileName);

    // Check if the PNG file has the disabled class (greyed out)
    await expect(page.getByTestId(`file-item-${psdFileName}`)).toHaveClass(
      /pointer-events-none cursor-not-allowed opacity-50/,
    );

    // Check that the TXT file is not disabled
    await expect(page.getByTestId(`file-item-${txtFileName}`)).not.toHaveClass(
      /pointer-events-none cursor-not-allowed opacity-50/,
    );

    // Verify the tooltip for PSD file states it's not supported
    await page
      .locator(`[data-testid="file-item-${psdFileName}"]`)
      .locator("..")
      .hover();

    // Select the TXT file (should work normally)
    await page.getByTestId(`checkbox-${txtFileName}`).click();

    // Verify the TXT file checkbox becomes checked
    await expect(page.getByTestId(`checkbox-${txtFileName}`)).toHaveAttribute(
      "data-state",
      "checked",
    );

    // Submit the file selection
    await page.getByTestId("select-files-modal-button").click();

    // Verify that only the TXT file was selected in the component
    await expect(page.getByText(`${txtFileName}.txt`)).toBeVisible();
    await expect(page.getByText(`${psdFileName}.psd`)).not.toBeVisible();
  },
);

import { expect, test } from "@playwright/test";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

// Add this line to declare Node.js global variables
declare const process: any;
declare const __dirname: string;

withEventDeliveryModes(
  "Vector Store RAG",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.ASTRA_DB_APPLICATION_TOKEN,
      "ASTRA_DB_APPLICATION_TOKEN required to run this test",
    );
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Vector Store RAG" })
      .first()
      .click();
    await page.waitForSelector('[title="fit view"]', {
      timeout: 20000,
    });

    await page.getByTestId("fit_view").click();

    await initialGPTsetup(page);

    await page.waitForSelector('[data-testid="title-Astra DB"]', {
      timeout: 3000,
    });

    await page.waitForTimeout(500);
    await page.getByTestId("fit_view").click();

    // Astra DB tokens
    await page
      .getByTestId("popover-anchor-input-token")
      .nth(0)
      .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");

    await page
      .locator('[data-testid="dropdown_str_database_name"]')
      .nth(0)
      .waitFor({
        timeout: 15000,
        state: "visible",
      });

    let databaseDropdownCount = await page
      .locator('[data-testid="dropdown_str_database_name"]')
      .nth(0)
      .count();

    while (databaseDropdownCount === 0) {
      await page
        .getByTestId("popover-anchor-input-token")
        .nth(0)
        .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");

      await page.waitForTimeout(2000);

      await page
        .locator('[data-testid="dropdown_str_database_name"]')
        .nth(0)
        .waitFor({
          timeout: 15000,
          state: "visible",
        });

      databaseDropdownCount = await page
        .locator('[data-testid="dropdown_str_database_name"]')
        .nth(0)
        .count();
    }

    await page.waitForTimeout(2000);

    await page.getByTestId("dropdown_str_database_name").nth(0).click();

    await page.waitForTimeout(2000);

    let langflowCount = await page
      .locator('[data-testid="langflow-0-option"]')
      .count();

    while (langflowCount === 0) {
      await page.waitForTimeout(1000);
      await page.getByTestId("icon-RefreshCcw").click();

      await page.getByTestId("dropdown_str_database_name").nth(0).click();

      await page.waitForTimeout(1000);

      langflowCount = await page
        .locator('[data-testid="langflow-0-option"]')
        .count();
    }

    await page.locator('[data-testid="langflow-0-option"]').nth(0).waitFor({
      timeout: 15000,
      state: "visible",
    });

    await page.getByTestId("langflow-0-option").nth(0).click();

    await page
      .locator('[data-testid="dropdown_str_collection_name"]')
      .nth(0)
      .waitFor({
        timeout: 15000,
        state: "visible",
      });

    await page.waitForTimeout(2000);

    await page.getByTestId("dropdown_str_collection_name").nth(0).click();

    await page.locator('[data-testid="fe_tests-0-option"]').nth(0).waitFor({
      timeout: 15000,
      state: "visible",
    });

    await page.getByTestId("fe_tests-0-option").nth(0).click();

    await page
      .getByTestId("popover-anchor-input-token")
      .nth(1)
      .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");

    await page
      .locator('[data-testid="dropdown_str_database_name"]')
      .nth(1)
      .waitFor({
        timeout: 15000,
        state: "visible",
      });

    databaseDropdownCount = await page
      .locator('[data-testid="dropdown_str_database_name"]')
      .nth(0)
      .count();

    while (databaseDropdownCount === 0) {
      await page
        .getByTestId("popover-anchor-input-token")
        .nth(0)
        .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");

      await page.waitForTimeout(2000);

      await page
        .locator('[data-testid="dropdown_str_database_name"]')
        .nth(1)
        .waitFor({
          timeout: 15000,
          state: "visible",
        });

      databaseDropdownCount = await page
        .locator('[data-testid="dropdown_str_database_name"]')
        .nth(0)
        .count();
    }

    await page.getByTestId("dropdown_str_database_name").nth(1).click();

    await page.waitForTimeout(2000);

    langflowCount = await page
      .locator('[data-testid="langflow-0-option"]')
      .count();

    while (langflowCount === 0) {
      await page.waitForTimeout(1000);
      await page.getByTestId("icon-RefreshCcw").click();

      const loadingOptions = page.getByText("Loading options...");
      await loadingOptions.waitFor({ state: "visible", timeout: 30000 });

      if (await loadingOptions.isVisible()) {
        await expect(loadingOptions).toBeHidden({ timeout: 120000 });
      }

      await page.getByTestId("dropdown_str_database_name").nth(1).click();

      await page.waitForTimeout(1000);

      langflowCount = await page
        .locator('[data-testid="langflow-0-option"]')
        .count();
    }

    await page.getByTestId("langflow-0-option").nth(0).click();

    await page.waitForTimeout(2000);

    await page
      .locator('[data-testid="dropdown_str_collection_name"]')
      .nth(1)
      .waitFor({
        timeout: 15000 * 3,
        state: "visible",
      });

    await page.getByTestId("dropdown_str_collection_name").nth(1).click();

    await page.waitForTimeout(2000);

    await page.locator('[data-testid="fe_tests-0-option"]').nth(0).waitFor({
      timeout: 15000,
      state: "visible",
    });

    await page.getByTestId("fe_tests-0-option").nth(0).click();

    await page.getByTestId("input-file-component").last().click();
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("drag-files-component").last().click();

    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(
      path.join(__dirname, "../../assets/test_file.txt"),
    );
    await page.getByText("test_file.txt").last().isVisible();
    await page.waitForSelector("text=file uploaded successfully", {
      timeout: 10000,
    });
    await page.waitForTimeout(3000);
    await page.getByTestId("select-files-modal-button").click();
    await page.getByTestId("button_run_astra db").last().click();
    await page.waitForSelector("text=built successfully", {
      timeout: 60000 * 2,
    });

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", {
      timeout: 60000 * 2,
    });

    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 60000,
    });
    await page.getByTestId("input-chat-playground").last().fill("hello");
    await page.getByTestId("input-chat-playground").last().click();
    await page.keyboard.press("Enter");

    await page
      .getByText("This is a test file.", { exact: true })
      .last()
      .isVisible();
    await page.getByText("Chat", { exact: true }).last().click();
    await page.getByText("Default Session").last().click();
    await page.getByRole("combobox").click();
    await page.getByLabel("Message logs").click();
    await page.getByText("timestamp", { exact: true }).last().isVisible();
    await page.getByText("text", { exact: true }).last().isVisible();
    await page.getByText("sender", { exact: true }).last().isVisible();
    await page.getByText("sender_name", { exact: true }).last().isVisible();
    await page.getByText("session_id", { exact: true }).last().isVisible();
    await page.getByText("files", { exact: true }).last().isVisible();
    await page.getByRole("gridcell").last().isVisible();
    await page.getByRole("combobox").click();
    await page.getByLabel("Delete").click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 60000,
    });
    await page.getByTestId("input-chat-playground").last().isVisible();
  },
  { timeout: 60000 },
);

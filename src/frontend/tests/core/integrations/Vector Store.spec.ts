import { Page, test } from "@playwright/test";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { extractAndCleanCode } from "../../utils/extract-and-clean-code";

test(
  "Vector Store RAG",
  { tag: ["@release", "@starter-project"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );
    test.skip(
      !process?.env?.ASTRA_DB_API_ENDPOINT,
      "ASTRA_DB_API_ENDPOINT required to run this test",
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
      timeout: 100000,
    });
    await page.getByTitle("fit view").click();
    await page.getByTitle("zoom out").click();
    await page.getByTitle("zoom out").click();
    await page.getByTitle("zoom out").click();
    let outdatedComponents = await page
      .getByTestId("icon-AlertTriangle")
      .count();
    while (outdatedComponents > 0) {
      await page.getByTestId("icon-AlertTriangle").first().click();
      outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
    }
    let filledApiKey = await page.getByTestId("remove-icon-badge").count();
    while (filledApiKey > 0) {
      await page.getByTestId("remove-icon-badge").first().click();
      filledApiKey = await page.getByTestId("remove-icon-badge").count();
    }
    if (process?.env?.ASTRA_DB_API_ENDPOINT?.includes("astra-dev")) {
      await page.getByTestId("title-Astra DB").first().click();
      await page.getByTestId("code-button-modal").click();
      await page.waitForSelector("text=Edit Code", {
        timeout: 3000,
      });
      let cleanCode = await extractAndCleanCode(page);
      cleanCode = cleanCode!.replace(
        '"pre_delete_collection": self.pre_delete_collection or False,',
        '"pre_delete_collection": self.pre_delete_collection or False,\n            "environment": "dev",',
      );
      await page.locator("textarea").last().press(`ControlOrMeta+a`);
      await page.keyboard.press("Backspace");
      await page.locator("textarea").last().fill(cleanCode);
      await page.locator('//*[@id="checkAndSaveBtn"]').click();
      await page.waitForSelector('[data-testid="title-Astra DB"]', {
        timeout: 3000,
      });
      await page.getByTestId("title-Astra DB").last().click();
      await page.getByTestId("code-button-modal").click();
      await page.waitForSelector("text=Edit Code", {
        timeout: 3000,
      });
      await page.locator("textarea").last().press(`ControlOrMeta+a`);
      await page.keyboard.press("Backspace");
      await page.locator("textarea").last().fill(cleanCode);
      await page.locator('//*[@id="checkAndSaveBtn"]').click();
    }
    const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
    const isApiKeyInputVisible = await apiKeyInput.isVisible();
    if (isApiKeyInputVisible) {
      await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
    }
    await page
      .getByTestId("popover-anchor-input-api_key") // input ID without "anchor-"
      .nth(0)
      .fill(process.env.OPENAI_API_KEY ?? "");
    await page
      .getByTestId("popover-anchor-input-openai_api_key")
      .nth(1)
      .fill(process.env.OPENAI_API_KEY ?? "");
    await page
      .getByTestId("popover-anchor-input-openai_api_key")
      .nth(0)
      .fill(process.env.OPENAI_API_KEY ?? "");
    // Astra DB tokens
    await page
      .getByTestId("popover-anchor-input-token")
      .nth(0)
      .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");
    await page
      .getByTestId("popover-anchor-input-token")
      .nth(1)
      .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");
    // Astra DB endpoints
    await page
      .getByTestId("popover-anchor-input-api_endpoint")
      .nth(0)
      .fill(process.env.ASTRA_DB_API_ENDPOINT ?? "");
    await page
      .getByTestId("popover-anchor-input-api_endpoint")
      .nth(1)
      .fill(process.env.ASTRA_DB_API_ENDPOINT ?? "");

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("input-file-component").last().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(
      path.join(__dirname, "../../assets/test_file.txt"),
    );
    await page.getByText("test_file.txt").isVisible();
    await page.getByTestId("button_run_astra db").last().click();
    await page.waitForSelector("text=built successfully", {
      timeout: 60000 * 2,
    });
    await page.getByText("built successfully").last().click({
      timeout: 30000,
    });
    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", {
      timeout: 60000 * 2,
    });
    await page.getByText("built successfully").last().click({
      timeout: 30000,
    });

    await page.getByText("Playground", { exact: true }).last().click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
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
      timeout: 100000,
    });
    await page.getByTestId("input-chat-playground").last().isVisible();
  },
);

import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test(
  "should able to see and interact with logs",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

    let modalCount = 0;
    try {
      const modalTitleElement = await page?.getByTestId("modal-title");
      if (modalTitleElement) {
        modalCount = await modalTitleElement.count();
      }
    } catch (error) {
      modalCount = 0;
    }

    while (modalCount === 0) {
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await expect(page.getByTestId(/.*rf__node.*/).first()).toBeVisible({
      timeout: 1000,
    });
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

    await page.getByTestId("icon-ChevronDown").click();
    await page.getByText("Logs").click();
    await page.getByText("No Data Available", { exact: true }).isVisible();
    await page.keyboard.press("Escape");

    const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
    const isApiKeyInputVisible = await apiKeyInput.isVisible();

    if (isApiKeyInputVisible) {
      await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
    }

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("gpt-4o-1-option").click();

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 1000,
    });
    await page.getByTestId("button_run_chat output").first().click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page
      .getByText("Chat Output built successfully", { exact: true })
      .isVisible();
    await page.getByTestId("icon-ChevronDown").click();
    await page.getByText("Logs").click();

    await page.getByText("timestamp").first().isVisible();
    await page.getByText("flow_id").first().isVisible();
    await page.getByText("source").first().isVisible();
    await page.getByText("target", { exact: true }).first().isVisible();
    await page.getByText("target_args", { exact: true }).first().isVisible();
    await page.getByRole("gridcell").first().isVisible();

    await page.keyboard.press("Escape");

    await page.getByTestId("user-profile-settings").first().click();
    await page.getByText("Settings", { exact: true }).click();

    await page.getByText("Messages", { exact: true }).click();
    await page.getByText("index", { exact: true }).last().isVisible();
    await page.getByText("timestamp", { exact: true }).isVisible();
    await page.getByText("flow_id", { exact: true }).isVisible();
    await page.getByText("source", { exact: true }).isVisible();
    await page.getByText("target", { exact: true }).isVisible();
    await page.getByText("vertex_id", { exact: true }).isVisible();
    await page.getByText("status", { exact: true }).isVisible();
    await page.getByText("error", { exact: true }).isVisible();
    await page.getByText("outputs", { exact: true }).isVisible();
    await page.getByText("inputs", { exact: true }).isVisible();

    await page.getByRole("gridcell").first().isVisible();
  },
);

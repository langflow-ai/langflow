import { test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test(
  "Blog Writer",
  { tag: ["@release", "@starter-project"] },
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
    await page.getByRole("heading", { name: "Blog Writer" }).click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 5000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

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

    const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
    const isApiKeyInputVisible = await apiKeyInput.isVisible();

    if (isApiKeyInputVisible) {
      await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
    }

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("gpt-4o-1-option").click();

    await page
      .getByTestId("inputlist_str_urls_0")
      .nth(0)
      .fill(
        "https://www.natgeokids.com/uk/discover/animals/sea-life/turtle-facts/",
      );
    await page
      .getByTestId("inputlist_str_urls_1")
      .nth(0)
      .fill("https://www.originaldiving.com/blog/top-ten-turtle-facts");

    await page
      .getByTestId("textarea_str_input_value")
      .fill(
        "Use the references above for style to write a new blog/tutorial about turtles. Suggest non-covered topics.",
      );

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 30000,
    });

    await page.getByText("Playground", { exact: true }).last().click();
    await page
      .getByPlaceholder(
        "No chat input variables found. Click to run your flow.",
        { exact: true },
      )
      .last()
      .isVisible();

    await page.getByText("turtles").last().isVisible();
    await page.getByText("sea").last().isVisible();
    await page.getByText("survival").last().isVisible();
  },
);

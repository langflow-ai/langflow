import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test(
  "user must be able to edit an empty prompt",
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
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();

    let outdatedComponents = await page
      .getByTestId("icon-AlertTriangle")
      .count();

    while (outdatedComponents > 0) {
      await page.getByTestId("icon-AlertTriangle").first().click();
      outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
    }

    await page.getByTestId("promptarea_prompt_template").click();

    await page.keyboard.press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");

    await page.getByText("Edit Prompt", { exact: true }).click();

    await page.getByTestId("edit-prompt-sanitized").click();

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("THIS IS A TEST");

    await page.getByText("Edit Prompt", { exact: true }).click();

    let promptSanitizedText = await page
      .getByTestId("edit-prompt-sanitized")
      .textContent();

    expect(promptSanitizedText).toBe("THIS IS A TEST");

    await page.getByTestId("edit-prompt-sanitized").click();

    await page.keyboard.press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");

    await page.getByText("Edit Prompt", { exact: true }).click();

    await page.getByTestId("edit-prompt-sanitized").click();

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("THIS IS A TEST 2");

    await page.getByText("Edit Prompt", { exact: true }).click();

    promptSanitizedText = await page
      .getByTestId("edit-prompt-sanitized")
      .textContent();

    expect(promptSanitizedText).toBe("THIS IS A TEST 2");
  },
);

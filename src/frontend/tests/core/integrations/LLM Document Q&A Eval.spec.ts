import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "LLM Document Q&A Eval",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.LANGWATCH_API_KEY,
      "LANGWATCH_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "LLM Document Q&A Eval" }).click();

    await page.waitForSelector('[title="fit view"]', {
      timeout: 100000,
    });

    await page.getByTestId("refresh-button-evaluator_name").click();

    await page.waitForTimeout(5000);

    await page.getByTestId("dropdown_str_evaluator_name").click();

    await page.getByRole("option").first().click();

    await page.waitForTimeout(500);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(0)
      .fill(process.env.OPENAI_API_KEY ?? "");

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(2)
      .fill(process.env.OPENAI_API_KEY ?? "");

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(1)
      .fill(process.env.LANGWATCH_API_KEY ?? "");

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("button_upload_file").click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(
      path.join(__dirname, "../../assets/test_file.txt"),
    );
    await page.getByText("test_file.txt").isVisible();

    await page.waitForTimeout(500);

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 3000,
    });

    await page.getByTestId("button_run_chat output").click();

    try {
      await page.waitForSelector("text=built successfully", {
        timeout: 30000,
      });
    } catch (e) {
      await page
        .getByTestId("popover-anchor-input-api_key")
        .nth(1)
        .fill(process.env.LANGWATCH_API_KEY ?? "");

      await page.getByTestId("button_run_chat output").click();

      await page.waitForSelector("text=built successfully", {
        timeout: 30000,
      });
    }

    await page.getByText("Playground", { exact: true }).last().click();
    await page
      .getByText("No input message provided.", { exact: true })
      .last()
      .isVisible();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    const output = await page
      .getByTestId("div-chat-message")
      .last()
      .innerText();
    expect(output.length).toBeGreaterThan(300);
    expect(output.toLowerCase()).toContain("summary");
  },
);

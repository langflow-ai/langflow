import { expect, test } from "@playwright/test";
import dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must not experience message duplication in mathematical expressions with agent component",
  { tag: ["@release", "@components", "@workspace"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.ANTHROPIC_API_KEY,
      "ANTHROPIC_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Simple Agent" }).first().click();

    await page.getByTestId("value-dropdown-dropdown_str_agent_llm").click();

    await page.waitForTimeout(200);

    await page.getByText("Anthropic").last().click();

    await page
      .getByTestId("popover-anchor-input-api_key")
      .fill(process.env.ANTHROPIC_API_KEY || "");

    await page.getByTestId("playground-btn-flow-io").click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    // Test simple math expression
    await page.getByTestId("input-chat-playground").fill("2+2");

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();
    // Wait for response completion
    await page.waitForSelector(
      '[data-testid="header-icon"] svg[data-testid="icon-Check"]',
      {
        timeout: 30000,
      },
    );

    // Click on the execution section to expand and reveal the JSON blocks
    await page.locator('[data-testid="header-icon"]').first().click();

    // Wait for the JSON code blocks to appear after clicking
    await page.waitForSelector('[data-testid="chat-code-tab"]', {
      timeout: 10000,
    });

    // Get all the JSON code content to check both input and output
    const codeBlocks = await page
      .locator('[data-testid="chat-code-tab"] code.language-json')
      .allTextContents();

    // First code block should contain the input expression
    const inputJson = codeBlocks[0];
    expect(inputJson).toContain('"expression": "2+2"');

    // Verify the input is NOT duplicated (should not contain "2+22+2")
    expect(inputJson).not.toContain('"expression": "2+22+2"');
    expect(inputJson).not.toContain('"expression": "22+2"');

    // Second code block should contain the output result
    const outputJson = codeBlocks[1];
    expect(outputJson).toContain('"result": "4"');

    // Ensure the result is not 26 (which would be 2+22+2)
    expect(outputJson).not.toContain('"result": "26"');
  },
);

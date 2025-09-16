import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to select a value from dropdown that is not in the list",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("openai");

    await page.waitForSelector('[data-testid="openaiOpenAI"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("openaiOpenAI")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-openai").last().click();
      });
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("dropdown_search_input").click();
    await page
      .getByTestId("dropdown_search_input")
      .fill("this is a test langflow");
    await page.keyboard.press("Enter");

    await page.waitForTimeout(500);

    let value = await page
      .getByTestId("value-dropdown-dropdown_str_model_name")
      .textContent();

    await page.getByTestId("generic-node-title-arrangement").click();
    await page.keyboard.press("Delete");

    await page.getByTestId("sidebar-search-input").fill("agent");

    await page.getByTestId("agentsAgent").hover();
    await page.getByTestId("add-component-button-agent").click();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("dropdown_search_input").click();
    await page
      .getByTestId("dropdown_search_input")
      .fill("this is a test langflow");
    await page.keyboard.press("Enter");

    await page.waitForTimeout(500);

    value = await page
      .getByTestId("value-dropdown-dropdown_str_model_name")
      .textContent();

    await page.getByTestId("dropdown_str_model_name").click();

    expect(await page.getByText("ollama").count()).toBe(0);
    expect(await page.getByText("claude").count()).toBe(0);
    expect(await page.getByText("gpt").count()).toBeGreaterThanOrEqual(1);

    await page.waitForTimeout(500);

    await page.getByTestId("value-dropdown-dropdown_str_agent_llm").click();

    await page.waitForTimeout(500);

    await page.getByText("Anthropic").click();

    await page.waitForTimeout(500);
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("dropdown_search_input").click();

    expect(await page.getByText("llama").count()).toBe(0);
    expect(await page.getByText("claude").count()).toBeGreaterThanOrEqual(1);
    expect(await page.getByText("gpt").count()).toBe(0);

    await page.waitForTimeout(500);
  },
);

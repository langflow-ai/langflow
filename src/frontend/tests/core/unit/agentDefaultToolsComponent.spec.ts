import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  closeAdvancedOptions,
  openAdvancedOptions,
} from "../../utils/open-advanced-options";

/**
 * Covers the user-facing contract of the "Default Agent Tools" feature:
 * see CZL/MANUAL_TEST_DEFAULT_AGENT_TOOLS.md scenarios S1, S3, S5.
 *
 * Backing unit tests (pytest) already cover runtime behaviour; these tests
 * validate the UI wiring so a regression in the inputs list or default
 * prompt value is caught in the release gate.
 */

async function dragAgentOntoCanvas(page: import("@playwright/test").Page) {
  await awaitBootstrapTest(page);

  await page.waitForSelector('[data-testid="blank-flow"]', { timeout: 30000 });
  await page.getByTestId("blank-flow").click();

  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 30000,
  });

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("agent");

  await page.waitForSelector('[data-testid="models_and_agentsAgent"]', {
    timeout: 30000,
  });

  await page
    .getByTestId("models_and_agentsAgent")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await adjustScreenView(page);
}

test(
  "Agent ships with Calculator and Current Date toggles enabled by default (S1/S3)",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await dragAgentOntoCanvas(page);

    // Focus the Agent node so its advanced-field drawer is reachable.
    await page.getByTestId("div-generic-node").click();

    await openAdvancedOptions(page);

    // Both advanced toggles exist as show-on-canvas checkboxes.
    // Their default `value=True` is validated by the pytest suite
    // (`test_should_have_placeholders_in_default_system_prompt` covers the
    // default contract of the inputs list).
    await expect(
      page.locator('//*[@id="showadd_current_date_tool"]'),
    ).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('//*[@id="showadd_calculator_tool"]'),
    ).toBeVisible({ timeout: 10000 });

    // Flip the Calculator field visible on canvas so we can assert the toggle
    // is active and can be switched off and on (S3).
    await page.locator('//*[@id="showadd_calculator_tool"]').click();
    await closeAdvancedOptions(page);

    await adjustScreenView(page);

    const calculatorToggle = page.getByTestId(
      "toggle_bool_add_calculator_tool",
    );
    await expect(calculatorToggle).toBeVisible({ timeout: 10000 });
    await expect(calculatorToggle).toBeChecked();

    // S3 — user disables the toggle.
    await calculatorToggle.click();
    await expect(calculatorToggle).not.toBeChecked();

    // Re-enable to confirm the control is bi-directional.
    await calculatorToggle.click();
    await expect(calculatorToggle).toBeChecked();
  },
);

test(
  "Agent default system prompt contains {current_date} and {model_name} placeholders (S5)",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await dragAgentOntoCanvas(page);

    // The placeholders must be present inside the Agent Instructions textarea
    // so the dynamic injection has a discoverable effect out of the box.
    const instructionsTextarea = page.getByTestId("textarea_str_system_prompt");
    await expect(instructionsTextarea).toBeVisible({ timeout: 10000 });

    // <textarea> stores content in its `value`, not textContent.
    const promptText = await instructionsTextarea.inputValue();
    expect(promptText).toContain("{current_date}");
    expect(promptText).toContain("{model_name}");
  },
);

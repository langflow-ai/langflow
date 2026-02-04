import type { Page } from "@playwright/test";
import { expect } from "../fixtures";
import { adjustScreenView } from "./adjust-screen-view";
import { unselectNodes } from "./unselect-nodes";

export const selectAnthropicModel = async (page: Page) => {
  const nodes = page.locator(".react-flow__node", {
    has: page.getByTestId("title-language model"),
  });

  const gptModelDropdownCount = await nodes.count();

  for (let i = 0; i < gptModelDropdownCount; i++) {
    const node = nodes.nth(i);
    try {
      await expect(node.getByTestId("model_model").last()).toBeVisible({
        timeout: 10000,
      });
    } catch (error) {
      console.log("Node model not visible, proceeding...", error);
      node.click();
    }

    const model = (await node.getByTestId("model_model").last().isVisible())
      ? node.getByTestId("model_model").last()
      : page.getByTestId("model_model").last();
    await adjustScreenView(page);

    await expect(model).toBeVisible({ timeout: 10000 });
    await model.click();
    await page.waitForSelector('[role="listbox"]', { timeout: 10000 });

    const gptOMiniOption = await page
      .getByTestId("claude-sonnet-4-5-20250929-option")
      .count();

    await page.waitForTimeout(500);

    if (gptOMiniOption === 0) {
      await page.getByTestId("manage-model-providers").click();
      await page.waitForSelector("text=Model providers", { timeout: 30000 });

      await page.getByTestId("provider-item-Anthropic").click();
      await page.waitForTimeout(500);

      const checkExistingKey = await page.getByTestId("input-end-icon").count();
      if (checkExistingKey === 0) {
        await page
          .getByPlaceholder("Add API key")
          .fill(process.env.ANTHROPIC_API_KEY!);
        await page.waitForSelector("text=Anthropic Api Key Saved", {
          timeout: 30000,
        });
        await page.getByTestId("llm-toggle-claude-sonnet-4-5-20250929").click();
        await page.getByText("Close").last().click();
      } else {
        await page.waitForTimeout(500);

        const isChecked = await page
          .getByTestId("llm-toggle-claude-sonnet-4-5-20250929")
          .isChecked();
        if (!isChecked) {
          await page
            .getByTestId("llm-toggle-claude-sonnet-4-5-20250929")
            .click();
        }
        await page.getByText("Close").last().click();
        await page.getByTestId("model_model").nth(i).click();
      }
    }
    await page.waitForTimeout(500);
    await page.getByTestId("claude-sonnet-4-5-20250929-option").click();
    if (i < gptModelDropdownCount - 1) {
      await unselectNodes(page);
    }
  }
};

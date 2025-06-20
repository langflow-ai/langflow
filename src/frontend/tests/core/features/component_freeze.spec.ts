import { expect, test } from "@playwright/test";
import { addFlowToTestOnEmptyLangflow } from "../../utils/add-flow-to-test-on-empty-langflow";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to freeze a component",
  { tag: ["@release", "@workspace", "@components"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    const firstRunLangflow = await page
      .getByTestId("empty-project-description")
      .count();

    if (firstRunLangflow > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }

    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text input");
    await page.waitForSelector('[data-testid="input_outputText Input"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    await page.getByTestId("textarea_str_input_value").fill("hello world");

    await page.getByTestId("div-generic-node").getByRole("button").click();

    await page.waitForSelector('[data-testid="div-generic-node"]', {
      timeout: 10000,
    });

    await page.getByTestId("output-inspection-output text-textinput").click();

    const firstOutputText = await page.getByPlaceholder("Empty").textContent();

    expect(firstOutputText).toBe("hello world");

    await page.getByText("Close").last().click();

    await page.getByTestId("textarea_str_input_value").fill("goodbye world");

    await page.getByTestId("div-generic-node").click();

    await page.waitForSelector('[data-testid="freeze-all-button-modal"]', {
      timeout: 1000,
    });

    await page.getByTestId("freeze-all-button-modal").click();

    // Use polling approach to wait for frozen icon with better error handling
    let frozenIconVisible = false;
    let attempts = 0;
    const maxAttempts = 40; // 40 seconds total

    while (!frozenIconVisible && attempts < maxAttempts) {
      try {
        // Check if frozen icon is visible
        const frozenIcon = page.getByTestId("frozen-icon");
        const isVisible = await frozenIcon.isVisible().catch(() => false);

        if (isVisible) {
          frozenIconVisible = true;
          break;
        }

        // Wait before next attempt
        await page.waitForTimeout(1000);
        attempts++;

        // Log progress every 10 seconds for debugging
        if (attempts % 10 === 0) {
          console.log(
            `Waiting for frozen icon... Attempt ${attempts}/${maxAttempts}`,
          );
        }
      } catch (error) {
        console.log(
          `Error checking frozen icon on attempt ${attempts}:`,
          error,
        );
        await page.waitForTimeout(1000);
        attempts++;
      }
    }

    await page.waitForTimeout(1000);
    // Final assertion
    await expect(page.getByTestId("frozen-icon")).toBeVisible();
    await page.keyboard.press("Escape");

    await page.getByTestId("div-generic-node").getByRole("button").click();

    await page.waitForTimeout(2000);

    await page.getByTestId("output-inspection-output text-textinput").click();

    const secondOutputText = await page.getByPlaceholder("Empty").textContent();

    expect(secondOutputText).toBe(firstOutputText);
    expect(secondOutputText).toBe("hello world");
  },
);

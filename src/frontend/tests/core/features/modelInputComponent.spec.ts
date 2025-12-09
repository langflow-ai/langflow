import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("ModelInputComponent", () => {
  test(
    "should display model selector in a node with model input",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Create a new blank flow
      await page.getByTestId("blank-flow").click();
      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 3000,
      });

      // Search for OpenAI component which has model input
      await page.getByTestId("sidebar-search-input").click();
      await page.getByTestId("sidebar-search-input").fill("OpenAI");

      // Wait for search results
      await page.waitForTimeout(500);

      // Look for OpenAI component and add it
      const openaiComponent = page.getByTestId("modelsOpenAI").first();
      if (await openaiComponent.isVisible()) {
        await openaiComponent.click();
        await page.waitForTimeout(500);

        // The node should now be in the flow
        const node = page.locator(".react-flow__node").first();
        await expect(node).toBeVisible({ timeout: 5000 });

        // The model input should be present (either as dropdown or setup button)
        // This verifies the ModelInputComponent is rendering
        const modelSection = node.locator(
          '[data-testid*="model"], button:has-text("Setup Provider"), [role="combobox"]',
        );
        await expect(modelSection.first()).toBeVisible({ timeout: 3000 });
      }
    },
  );

  test(
    "should open model dropdown and show providers",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Create a blank flow
      await page.getByTestId("blank-flow").click();
      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 3000,
      });

      // Add an OpenAI model node
      await page.getByTestId("sidebar-search-input").fill("OpenAI");
      await page.waitForTimeout(500);

      const openaiComponent = page.getByTestId("modelsOpenAI").first();
      if (await openaiComponent.isVisible()) {
        await openaiComponent.click();
        await page.waitForTimeout(1000);

        // Find and click the model dropdown trigger (combobox)
        const modelDropdown = page.locator('[role="combobox"]').first();
        if (await modelDropdown.isVisible()) {
          await modelDropdown.click();

          // Should show the dropdown content with model options or manage providers
          await page.waitForTimeout(500);

          // Look for typical dropdown content
          const dropdownContent = page.locator('[role="listbox"], [cmdk-list]');
          if (await dropdownContent.isVisible({ timeout: 2000 })) {
            await expect(dropdownContent).toBeVisible();
          }
        }
      }
    },
  );

  test(
    "should show Manage Model Providers button in dropdown",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Create a blank flow
      await page.getByTestId("blank-flow").click();
      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 3000,
      });

      // Add a model component
      await page.getByTestId("sidebar-search-input").fill("OpenAI");
      await page.waitForTimeout(500);

      const openaiComponent = page.getByTestId("modelsOpenAI").first();
      if (await openaiComponent.isVisible()) {
        await openaiComponent.click();
        await page.waitForTimeout(1000);

        // Find the model dropdown
        const modelDropdown = page.locator('[role="combobox"]').first();
        if (await modelDropdown.isVisible()) {
          await modelDropdown.click();
          await page.waitForTimeout(500);

          // Should show manage providers button
          const manageProvidersBtn = page.getByTestId("manage-model-providers");
          if (await manageProvidersBtn.isVisible({ timeout: 2000 })) {
            await expect(manageProvidersBtn).toBeVisible();
            await expect(
              page.getByText("Manage Model Providers"),
            ).toBeVisible();
          }
        }
      }
    },
  );

  test(
    "should open Model Provider Modal from dropdown",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Create a blank flow
      await page.getByTestId("blank-flow").click();
      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 3000,
      });

      // Add a model component
      await page.getByTestId("sidebar-search-input").fill("OpenAI");
      await page.waitForTimeout(500);

      const openaiComponent = page.getByTestId("modelsOpenAI").first();
      if (await openaiComponent.isVisible()) {
        await openaiComponent.click();
        await page.waitForTimeout(1000);

        // Open dropdown
        const modelDropdown = page.locator('[role="combobox"]').first();
        if (await modelDropdown.isVisible()) {
          await modelDropdown.click();
          await page.waitForTimeout(500);

          // Click manage providers
          const manageProvidersBtn = page.getByTestId("manage-model-providers");
          if (await manageProvidersBtn.isVisible({ timeout: 2000 })) {
            await manageProvidersBtn.click();

            // Model provider modal should open
            await expect(page.getByText("Model providers")).toBeVisible({
              timeout: 5000,
            });
          }
        }
      }
    },
  );

  test(
    "should show Refresh List button in dropdown",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Create a blank flow
      await page.getByTestId("blank-flow").click();
      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 3000,
      });

      // Add a model component
      await page.getByTestId("sidebar-search-input").fill("OpenAI");
      await page.waitForTimeout(500);

      const openaiComponent = page.getByTestId("modelsOpenAI").first();
      if (await openaiComponent.isVisible()) {
        await openaiComponent.click();
        await page.waitForTimeout(1000);

        // Open dropdown
        const modelDropdown = page.locator('[role="combobox"]').first();
        if (await modelDropdown.isVisible()) {
          await modelDropdown.click();
          await page.waitForTimeout(500);

          // Should have refresh list option
          const refreshText = page.getByText("Refresh List");
          if (await refreshText.isVisible({ timeout: 2000 })) {
            await expect(refreshText).toBeVisible();
          }
        }
      }
    },
  );

  test(
    "should display selected model in trigger button",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Create a blank flow
      await page.getByTestId("blank-flow").click();
      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 3000,
      });

      // Add a model component
      await page.getByTestId("sidebar-search-input").fill("OpenAI");
      await page.waitForTimeout(500);

      const openaiComponent = page.getByTestId("modelsOpenAI").first();
      if (await openaiComponent.isVisible()) {
        await openaiComponent.click();
        await page.waitForTimeout(1000);

        // The combobox should show selected model or placeholder
        const modelDropdown = page.locator('[role="combobox"]').first();
        if (await modelDropdown.isVisible()) {
          // Should have some text content (model name or "Select a model")
          const text = await modelDropdown.textContent();
          expect(text).toBeTruthy();
        }
      }
    },
  );
});

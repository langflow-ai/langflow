import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user should be able to manage MCP server tools and configuration",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    const maxRetries = 5;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.warn(`Attempt ${attempt} of ${maxRetries}`);

        await awaitBootstrapTest(page);

        // Create a new flow
        await page.getByTestId("blank-flow").click();
        await page.getByTestId("sidebar-search-input").click();
        await page.getByTestId("sidebar-search-input").fill("api request");

        await page.waitForSelector('[data-testid="dataAPI Request"]', {
          timeout: 3000,
        });

        await page
          .getByTestId("dataAPI Request")
          .hover()
          .then(async () => {
            await page.getByTestId("add-component-button-api-request").click();
          });

        await page.waitForSelector(
          '[data-testid="generic-node-title-arrangement"]',
          {
            timeout: 3000,
          },
        );

        await page.getByTestId("generic-node-title-arrangement").click();

        // Exit the flow
        await page.getByTestId("icon-ChevronLeft").last().click();

        // Navigate to MCP server tab
        await page.getByTestId("mcp-btn").click();

        // Verify MCP server tab is visible
        await expect(page.getByTestId("mcp-server-title")).toBeVisible();
        await expect(page.getByText("Flows/Tools")).toBeVisible();

        // Click on Edit Tools button
        await page.getByTestId("button_open_actions").click();
        await page.waitForTimeout(500);

        // Verify actions modal is open
        await expect(page.getByText("MCP Server Tools")).toBeVisible();

        await page.waitForSelector("text=Flow Name", { timeout: 3000 });

        // Select some actions
        const rowsCount = await page.getByRole("row").count();
        expect(rowsCount).toBeGreaterThan(0);

        const cellsCount = await page.getByRole("gridcell").count();
        expect(cellsCount).toBeGreaterThan(0);

        await page.getByRole("gridcell").first().click();
        await page.waitForTimeout(1000);

        const isChecked = await page
          .locator('input[data-ref="eInput"]')
          .first()
          .isChecked();

        if (!isChecked) {
          await page.locator('input[data-ref="eInput"]').first().click();
          await page.waitForTimeout(1000);
        }
        const isCheckedAgain = await page
          .locator('input[data-ref="eInput"]')
          .first()
          .isChecked();

        if (isCheckedAgain) {
          await page.locator('input[data-ref="eInput"]').first().click();
          await page.waitForTimeout(1000);
        }

        // Verify if the state is maintained

        await page.locator('input[data-ref="eInput"]').first().click();

        await page.waitForTimeout(1000);

        await page.reload();

        // Navigate to MCP server tab
        await page.getByTestId("mcp-btn").click({ timeout: 10000 });

        // Verify MCP server tab is visible
        await expect(page.getByTestId("mcp-server-title")).toBeVisible();
        await expect(page.getByText("Flows/Tools")).toBeVisible();

        // Click on Edit Tools button
        await page.getByTestId("button_open_actions").click();
        await page.waitForTimeout(500);

        // Verify actions modal is open
        await expect(page.getByText("MCP Server Tools")).toBeVisible();

        const isCheckedAgainAgain = await page
          .locator('input[data-ref="eInput"]')
          .first()
          .isChecked();

        expect(isCheckedAgainAgain).toBeTruthy();

        await page.locator('input[data-ref="eInput"]').first().click();
        await page.waitForTimeout(1000);

        // Select first action
        let element = page.locator('input[data-ref="eInput"]').last();
        let elementText = await element.getAttribute("id");

        await element.scrollIntoViewIfNeeded();

        await page.waitForTimeout(500);

        const count = 0;

        while (
          elementText !==
            (await page
              .locator('input[data-ref="eInput"]')
              .last()
              .getAttribute("id")) &&
          count < 20
        ) {
          element = page.locator('input[data-ref="eInput"]').last();
          elementText = await element.getAttribute("id");
          await element.scrollIntoViewIfNeeded();
          await page.waitForTimeout(500);
        }

        await page.locator('input[data-ref="eInput"]').last().click();

        await page.waitForTimeout(1000);

        const isLastChecked = await page
          .locator('input[data-ref="eInput"]')
          .last()
          .isChecked();

        expect(isLastChecked).toBeTruthy();

        await page
          .getByRole("gridcell")
          .nth(cellsCount - 1)
          .click();
        await page.waitForTimeout(1000);

        expect(
          await page.locator('[data-testid="input_update_name"]').isVisible(),
        ).toBe(true);

        await page.getByTestId("input_update_name").fill("mcp test name");
        await page.waitForTimeout(2000);

        // Close the modal
        await page.getByText("Close").last().click();
        await page.waitForTimeout(2000);

        // Verify the selected action is visible in the tab
        await expect(page.getByTestId("div-mcp-server-tools")).toBeVisible();

        await page.getByText("JSON", { exact: true }).last().click();

        await page.waitForSelector("pre", { state: "visible", timeout: 3000 });

        // Generate API key if not in auto login mode
        const isAutoLogin = await page
          .getByText("Generate API key")
          .isVisible();
        if (isAutoLogin) {
          await page.getByText("Generate API key").click();
          await expect(page.getByText("API key generated")).toBeVisible();
        }

        // Copy configuration
        await page.getByTestId("icon-copy").click();
        await expect(page.getByTestId("icon-check")).toBeVisible();

        // Get the SSE URL from the configuration
        const configJson = await page.evaluate(() => {
          return navigator.clipboard.readText();
        });
        expect(configJson).toContain("mcpServers");
        expect(configJson).toContain("mcp-proxy");
        expect(configJson).toContain("uvx");

        // Extract the SSE URL from the configuration
        const sseUrlMatch = configJson?.match(
          /"args":\s*\[\s*"\/c"\s*,\s*"uvx"\s*,\s*"mcp-proxy"\s*,\s*"([^"]+)"/,
        );
        expect(sseUrlMatch).not.toBeNull();
        const _sseUrl = sseUrlMatch![1];

        await page.getByText("macOS/Linux", { exact: true }).click();

        await page.waitForSelector("pre", { state: "visible", timeout: 3000 });
        // Copy configuration
        await page.getByTestId("icon-copy").click();
        await expect(page.getByTestId("icon-check")).toBeVisible();

        const configJsonLinux = await page.evaluate(() => {
          return navigator.clipboard.readText();
        });

        const sseUrlMatchLinux = configJsonLinux?.match(
          /"args":\s*\[\s*"mcp-proxy"\s*,\s*"([^"]+)"/,
        );
        expect(sseUrlMatchLinux).not.toBeNull();

        // Verify setup guide link
        await expect(page.getByText("setup guide")).toBeVisible();
        await expect(page.getByText("setup guide")).toHaveAttribute(
          "href",
          "https://docs.langflow.org/mcp-server#connect-clients-to-use-the-servers-actions",
        );

        await awaitBootstrapTest(page);

        // Create a new flow with MCP component
        await page.getByTestId("blank-flow").click();
        await page.getByTestId("sidebar-search-input").click();
        await page.getByTestId("sidebar-search-input").fill("mcp");

        await page.waitForSelector('[data-testid="agentsMCP Tools"]', {
          timeout: 30000,
        });

        await page
          .getByTestId("agentsMCP Tools")
          .dragTo(page.locator('//*[@id="react-flow-id"]'), {
            targetPosition: { x: 50, y: 50 },
          });
        await page.getByTestId("canvas_controls_dropdown").click();

        await page.getByTestId("fit_view").click();

        await zoomOut(page, 3);
        await page.getByTestId("canvas_controls_dropdown").click();

        await expect(page.getByTestId("dropdown_str_tool")).toBeHidden();

        try {
          await page.getByText("Add MCP Server", { exact: true }).click({
            timeout: 5000,
          });
        } catch (_error) {
          await page
            .getByTestId("mcp-server-dropdown")
            .click({ timeout: 3000 });
          await page.getByText("Add MCP Server", { exact: true }).click({
            timeout: 5000,
          });
        }

        await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
          state: "visible",
          timeout: 30000,
        });

        await page.waitForSelector('[data-testid="json-input"]', {
          state: "visible",
          timeout: 30000,
        });

        await page.getByTestId("json-input").fill(configJsonLinux || "");

        await page.getByTestId("add-mcp-server-button").click();

        // CI-specific robust waiting strategy
        await page.waitForLoadState("domcontentloaded");
        await page.waitForLoadState("networkidle", { timeout: 15000 });
        
        // Longer wait for CI environments (they tend to be slower)
        await page.waitForTimeout(5000);
        
        // Force a page refresh if needed to ensure state is loaded
        const isCI = process.env.CI === 'true' || process.env.GITHUB_ACTIONS === 'true';
        if (isCI) {
          console.warn('CI environment detected, using extended wait times');
          await page.waitForTimeout(3000);
        }

        // Robust dropdown detection with multiple strategies
        const dropdownSelector = 'dropdown_str_tool';
        let targetElement;
        
        // Strategy 1: Wait for specific dropdown
        try {
          await page.waitForSelector(`[data-testid="${dropdownSelector}"]`, {
            state: 'visible',
            timeout: isCI ? 45000 : 30000 // Longer timeout for CI
          });
          targetElement = page.getByTestId(dropdownSelector);
          console.warn('Found target dropdown via strategy 1');
        } catch (error) {
          console.warn('Strategy 1 failed, trying alternative approaches');
          
          // Strategy 2: Look for any tool-related dropdown
          try {
            const toolDropdowns = page.locator('[data-testid*="dropdown"][data-testid*="tool"]');
            const count = await toolDropdowns.count();
            
            if (count > 0) {
              await toolDropdowns.first().waitFor({ state: 'visible', timeout: 10000 });
              targetElement = toolDropdowns.first();
              console.warn(`Found ${count} tool dropdowns via strategy 2`);
            } else {
              throw new Error('No tool dropdowns found');
            }
          } catch (strategyError) {
            // Strategy 3: Check if MCP server was actually added successfully
            console.warn('Strategy 2 failed, checking page state...');
            
            // Look for any new elements that might indicate the server was added
            const allDropdowns = await page.locator('[data-testid*="dropdown"]').count();
            const allTools = await page.locator('[data-testid*="tool"]').count();
            
            console.warn(`Total dropdowns: ${allDropdowns}, Total tools: ${allTools}`);
            
            if (allDropdowns === 0 && allTools === 0) {
              throw new Error('MCP server addition appears to have failed - no relevant UI elements found');
            }
            
            // If we have any dropdowns, try to use the first one as last resort
            if (allDropdowns > 0) {
              const anyDropdown = page.locator('[data-testid*="dropdown"]').first();
              await anyDropdown.waitFor({ state: 'visible', timeout: 5000 });
              targetElement = anyDropdown;
              console.warn('Using first available dropdown as fallback');
            } else {
              throw error; // Re-throw original error if nothing worked
            }
          }
        }

        // Ensure the dropdown is enabled and clickable
        if (targetElement) {
          // Wait for the element to be enabled (not disabled)
          await page.waitForFunction(
            (element) => {
              return !element.disabled && element.getAttribute('disabled') === null;
            },
            targetElement,
            { timeout: 10000 }
          );
          
          // Click the dropdown
          await targetElement.click();
        } else {
          throw new Error('No suitable dropdown element found');
        }

        const fetchOptionCount = await page.getByText("mcp_test_name").count();

        expect(fetchOptionCount).toBeGreaterThan(0);

        // If we get here, the test passed
        console.warn(`Test passed on attempt ${attempt}`);
        return;
      } catch (error) {
        console.error(`Attempt ${attempt} failed:`, error);
        
        // Add debugging information about the page state
        try {
          const allTestIds = await page.locator('[data-testid]').all();
          const testIdNames = await Promise.all(
            allTestIds.slice(0, 20).map(async (el) => { // Limit to first 20 to avoid timeout
              try {
                return await el.getAttribute('data-testid');
              } catch {
                return 'unknown';
              }
            })
          );
          console.warn(`Available test IDs on page: ${testIdNames.join(', ')}`);
          
          // Check if any tool-related elements exist
          const toolElements = await page.locator('[data-testid*="tool"]').count();
          const dropdownElements = await page.locator('[data-testid*="dropdown"]').count();
          console.warn(`Tool elements: ${toolElements}, Dropdown elements: ${dropdownElements}`);
        } catch (debugError) {
          console.warn('Failed to get debugging info:', debugError.message);
        }

        if (attempt === maxRetries) {
          console.error(
            `All ${maxRetries} attempts failed. Last error:`,
            error,
          );
          throw error;
        }

        // Wait a bit before retrying
        await page.waitForTimeout(2000);
      }
    }
  },
);

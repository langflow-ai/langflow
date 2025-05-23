import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user should be able to manage MCP server actions and configuration",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    const maxRetries = 5;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.log(`Attempt ${attempt} of ${maxRetries}`);

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
        await expect(page.getByText("Flows/Actions")).toBeVisible();

        // Click on Edit Actions button
        await page.getByTestId("button_open_actions").click();
        await page.waitForTimeout(500);

        // Verify actions modal is open
        await expect(page.getByText("MCP Server Actions")).toBeVisible();

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

        const isCheckedAgainAgain = await page
          .locator('input[data-ref="eInput"]')
          .first()
          .isChecked();

        expect(isCheckedAgainAgain).toBeFalsy();

        // Select first action
        await page
          .locator('input[data-ref="eInput"]')
          .last()
          .scrollIntoViewIfNeeded();
        await page.locator('input[data-ref="eInput"]').last().click();
        await page.waitForTimeout(1000);

        await page
          .getByRole("gridcell")
          .nth(cellsCount - 1)
          .click();
        await page.waitForTimeout(1000);

        const isLastChecked = await page
          .locator('input[data-ref="eInput"]')
          .last()
          .isChecked();

        expect(isLastChecked).toBeTruthy();

        expect(
          await page.locator('[data-testid="input_update_name"]').isVisible(),
        ).toBe(true);

        await page.getByTestId("input_update_name").fill("mcp test name");
        await page.waitForTimeout(500);

        // Close the modal
        await page.getByText("Close").last().click();
        await page.waitForTimeout(500);

        // Verify the selected action is visible in the tab
        await expect(page.getByTestId("div-mcp-server-tools")).toBeVisible();

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
        const configJson = await page.locator("pre").textContent();
        expect(configJson).toContain("mcpServers");
        expect(configJson).toContain("mcp-proxy");
        expect(configJson).toContain("uvx");

        // Extract the SSE URL from the configuration
        const sseUrlMatch = configJson?.match(
          /"args":\s*\[\s*"mcp-proxy"\s*,\s*"([^"]+)"/,
        );
        expect(sseUrlMatch).not.toBeNull();
        const sseUrl = sseUrlMatch![1];

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
        await page.getByTestId("sidebar-search-input").fill("mcp connection");

        await page.waitForSelector('[data-testid="toolsMCP Connection"]', {
          timeout: 30000,
        });

        await page
          .getByTestId("toolsMCP Connection")
          .dragTo(page.locator('//*[@id="react-flow-id"]'), {
            targetPosition: { x: 0, y: 0 },
          });

        await page.getByTestId("fit_view").click();
        await zoomOut(page, 3);

        // Switch to SSE tab and paste the URL
        await page.getByTestId("tab_1_sse").click();

        await page.waitForSelector('[data-testid="textarea_str_sse_url"]', {
          state: "visible",
          timeout: 30000,
        });
        await page.waitForTimeout(2000);

        await page.getByTestId("textarea_str_sse_url").fill("");
        await page.getByTestId("textarea_str_sse_url").fill(sseUrl);

        await page.waitForTimeout(2000);

        // Wait for the tools to become available
        let attempts = 0;
        const maxAttempts = 3;
        let dropdownEnabled = false;

        while (attempts < maxAttempts && !dropdownEnabled) {
          await page.getByTestId("refresh-button-sse_url").click();

          try {
            await page.waitForSelector(
              '[data-testid="dropdown_str_tool"]:not([disabled])',
              {
                timeout: 10000,
                state: "visible",
              },
            );
            dropdownEnabled = true;
          } catch (error) {
            attempts++;
            console.log(`Retry attempt ${attempts} for refresh button`);
          }
        }

        if (!dropdownEnabled) {
          throw new Error(
            "Dropdown did not become enabled after multiple refresh attempts",
          );
        }

        // Verify tools are available
        await page.waitForTimeout(3000);
        await page.getByTestId("dropdown_str_tool").click();
        await page.waitForTimeout(3000);

        const fetchOptionCount = await page.getByText("mcp_test_name").count();
        expect(fetchOptionCount).toBeGreaterThan(0);

        // If we get here, the test passed
        console.log(`Test passed on attempt ${attempt}`);
        return;
      } catch (error) {
        error = error as Error;
        console.log(`Attempt ${attempt} failed:`, error);

        if (attempt === maxRetries) {
          console.log(`All ${maxRetries} attempts failed. Last error:`, error);
          throw error;
        }

        // Wait a bit before retrying
        await page.waitForTimeout(2000);
      }
    }
  },
);

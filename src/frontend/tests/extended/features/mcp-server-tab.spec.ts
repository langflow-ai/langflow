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
        await expect(page.getByText("Flows/Tools")).toBeVisible();

        // Click on Edit Tools button
        await page.getByTestId("button_open_actions").click();
        await page.waitForTimeout(500);

        // Verify actions modal is open
        await expect(page.getByText("MCP Server Tools")).toBeVisible();

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
        let element = page.locator('input[data-ref="eInput"]').last();
        let elementText = await element.getAttribute("id");

        await element.scrollIntoViewIfNeeded();

        await page.waitForTimeout(500);

        let count = 0;

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
        const sseUrl = sseUrlMatch![1];

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
            targetPosition: { x: 0, y: 0 },
          });

        await page.getByTestId("fit_view").click();

        await zoomOut(page, 3);

        await expect(page.getByTestId("dropdown_str_tool")).toBeHidden();

        try {
          await page.getByText("Add MCP Server", { exact: true }).click({
            timeout: 5000,
          });
        } catch (error) {
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

        await expect(page.getByTestId("dropdown_str_tool")).toBeVisible({
          timeout: 30000,
        });

        await page.waitForSelector(
          '[data-testid="dropdown_str_tool"]:not([disabled])',
          {
            timeout: 10000,
            state: "visible",
          },
        );

        await page.getByTestId("dropdown_str_tool").click();

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

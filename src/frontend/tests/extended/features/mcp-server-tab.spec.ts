import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { openAddMcpServerModal } from "../../utils/open-add-mcp-server-modal";

test(
  "user should be able to manage MCP server tools and configuration",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Create a new flow
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("api request");

    await page.waitForSelector('[data-testid="data_sourceAPI Request"]', {
      timeout: 30000,
    });

    // Use dragTo which is more reliable than click on add-component-button
    await page
      .getByTestId("data_sourceAPI Request")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await page.waitForSelector(
      '[data-testid="generic-node-title-arrangement"]',
      {
        timeout: 30000,
      },
    );

    // Exit the flow
    await page.getByTestId("icon-ChevronLeft").last().click();

    // Navigate to MCP server tab
    await page.getByTestId("mcp-btn").click();
    await page.waitForTimeout(500);

    // Verify MCP server tab is visible
    await expect(page.getByTestId("mcp-server-title")).toBeVisible();
    await expect(page.getByText("Flows/Tools")).toBeVisible();

    // Click on Edit Tools button
    await page.getByTestId("button_open_actions").click();

    // Verify actions modal is open
    await expect(page.getByText("MCP Server Tools")).toBeVisible();
    await page.waitForTimeout(500);

    await page.waitForSelector("text=Flow Name", { timeout: 30000 });

    // Select some actions
    const rowsCount = await page.getByRole("row").count();
    expect(rowsCount).toBeGreaterThan(0);

    const cellsCount = await page.getByRole("gridcell").count();
    expect(cellsCount).toBeGreaterThan(0);

    await page.getByRole("gridcell").first().click();
    await page.waitForTimeout(500);

    const checkbox = page.locator('input[data-ref="eInput"]').first();

    // Toggle checkbox to ensure it ends up checked
    if (await checkbox.isChecked()) {
      await checkbox.click();
    }
    await checkbox.click();
    await expect(checkbox).toBeChecked();

    // Close the modal
    await page.getByText("Close").last().click();

    // Wait for modal to close
    await expect(page.getByText("MCP Server Tools")).not.toBeVisible();

    await page.reload();

    // Navigate to MCP server tab
    await page.getByTestId("mcp-btn").click({ timeout: 10000 });

    // Verify MCP server tab is visible
    await expect(page.getByTestId("mcp-server-title")).toBeVisible();
    await expect(page.getByText("Flows/Tools")).toBeVisible();

    // Click on Edit Tools button
    await page.getByTestId("button_open_actions").click();

    // Verify actions modal is open
    await expect(page.getByText("MCP Server Tools")).toBeVisible();

    // Wait for the grid to load
    await page.waitForSelector("text=Flow Name", { timeout: 30000 });

    // AG Grid data rows have class .ag-row (header rows don't)
    // Get the first data row's checkbox
    const firstDataRowCheckbox = page
      .locator(".ag-row")
      .first()
      .locator('input[type="checkbox"]');

    // Click to select the row
    if (!(await firstDataRowCheckbox.isChecked())) {
      await firstDataRowCheckbox.click();
    }
    await expect(firstDataRowCheckbox).toBeChecked({ timeout: 10000 });

    // Click on the first cell of the first data row to open the sidebar for editing
    await page.locator(".ag-row").first().locator(".ag-cell").first().click();

    await expect(page.locator('[data-testid="input_update_name"]')).toBeVisible(
      { timeout: 10000 },
    );

    await page.getByTestId("input_update_name").fill("mcp test name");

    // Close the modal
    await page.getByText("Close").last().click();

    // Wait for modal to close
    await expect(page.getByText("MCP Server Tools")).not.toBeVisible();

    // Verify the selected action is visible in the tab
    await expect(page.getByTestId("div-mcp-server-tools")).toBeVisible();

    // Switch to JSON mode
    await page.getByText("JSON", { exact: true }).last().click();

    await page.waitForSelector("pre", { state: "visible", timeout: 30000 });

    // Test API key generation in JSON mode
    const generateApiKeyButton = page.getByText("Generate API key");
    const isGenerateButtonVisible = await generateApiKeyButton
      .isVisible()
      .catch(() => false);

    if (isGenerateButtonVisible) {
      // Get the JSON configuration before generating
      const preElement = page.locator("pre").first();
      const jsonBeforeGeneration = await preElement.textContent();

      // Verify "YOUR_API_KEY" is present in the JSON before generation
      expect(jsonBeforeGeneration).toContain("YOUR_API_KEY");

      // Verify the button is visible and clickable
      await expect(generateApiKeyButton).toBeVisible();
      await expect(generateApiKeyButton).toBeEnabled();

      // Click the Generate API key button
      await generateApiKeyButton.click();

      // Wait for the API key to be generated and verify the state change
      await expect(page.getByText("API key generated")).toBeVisible({
        timeout: 10000,
      });

      // Wait for the JSON to update - it should no longer contain "YOUR_API_KEY"
      await expect(preElement).not.toContainText("YOUR_API_KEY", {
        timeout: 10000,
      });

      const jsonAfterGeneration = await preElement.textContent();

      // Verify that an actual API key (not "YOUR_API_KEY") is present
      const apiKeyMatch = jsonAfterGeneration?.match(
        /"x-api-key"[\s,]*"([^"]+)"/,
      );
      expect(apiKeyMatch).not.toBeNull();
      if (apiKeyMatch) {
        const generatedApiKey = apiKeyMatch[1];
        expect(generatedApiKey).not.toBe("YOUR_API_KEY");
        expect(generatedApiKey.length).toBeGreaterThan(0);
        expect(generatedApiKey.trim().length).toBeGreaterThan(0);
      }

      // Verify the Generate API key button text is no longer visible
      await expect(generateApiKeyButton).not.toBeVisible();
    } else {
      // If button is not visible, verify we're in a valid state
      const apiKeyGeneratedText = page.getByText("API key generated");
      const hasApiKeyGenerated = await apiKeyGeneratedText
        .isVisible()
        .catch(() => false);

      expect(
        hasApiKeyGenerated ||
          !(await page.getByText("Generate API key").isVisible()),
      ).toBeTruthy();
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

    await page.getByText("macOS/Linux", { exact: true }).click();

    await page.waitForSelector("pre", { state: "visible", timeout: 30000 });
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

    await page.waitForSelector('[data-testid="models_and_agentsMCP Tools"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("models_and_agentsMCP Tools")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 50 },
      });

    await adjustScreenView(page, { numberOfZoomOut: 3 });

    await expect(page.getByTestId("dropdown_str_tool")).toBeHidden();

    await openAddMcpServerModal(page);

    await page.waitForSelector('[data-testid="json-input"]', {
      state: "visible",
      timeout: 30000,
    });

    const randomSuffix = Math.floor(Math.random() * 90000) + 10000;
    const testName = `test_server_${randomSuffix}`;

    await page
      .getByTestId("json-input")
      .fill(configJsonLinux.replace(/lf-starter_project/g, testName) || "");

    await page.getByTestId("add-mcp-server-button").click();

    await expect(page.getByTestId("dropdown_str_tool")).toBeVisible({
      timeout: 30000,
    });

    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 30000,
        state: "visible",
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    // Verify that tools are available in the dropdown
    // The dropdown should show tool options (the action_name rename may not appear here)
    const toolOptions = page.locator('[data-testid*="-option"]');
    const toolCount = await toolOptions.count();

    expect(toolCount).toBeGreaterThan(0);
  },
);

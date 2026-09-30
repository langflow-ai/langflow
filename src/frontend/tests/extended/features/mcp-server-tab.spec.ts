import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { fillLocalMcpServerCommand } from "../../utils/fill-local-mcp-server-command";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { openAddMcpServerModal } from "../../utils/open-add-mcp-server-modal";

test(
  "user should be able to manage MCP server tools and configuration",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await openBlankFlow(page);
    await addComponentFromSidebar(page, {
      search: "api request",
      testId: "data_sourceAPI Request",
      hoverAdd: true,
    });

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
    await page.getByText(TEXTS.close).last().click();

    // Wait for modal to close
    await expect(page.getByText("MCP Server Tools")).not.toBeVisible();

    await page.reload();

    // Navigate to MCP server tab
    await expect(page.getByTestId("mcp-btn")).toBeVisible({ timeout: 30000 });
    await page.getByTestId("mcp-btn").click();

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
    await page.getByText(TEXTS.close).last().click();

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

    // Create a new flow with MCP component
    const mcpFlowId = await openBlankFlow(page);
    await page.getByTestId("sidebar-nav-mcp").click();
    const mcpNodes = page.getByRole("application", { name: "MCP Tools node" });
    const previousMcpNodeCount = await mcpNodes.count();
    await expect(page.getByTestId("canvas-add-note-button")).toBeEnabled({
      timeout: 30_000,
    });
    const mcpRow = page.getByTestId("mcp_lf-starter_project_draggable");
    await expect(mcpRow).toBeAttached({ timeout: 30_000 });
    await mcpRow.evaluate((element) =>
      element.scrollIntoView({ block: "center", behavior: "instant" }),
    );
    const addMcpNodeButton = page.getByTestId(
      "add-component-button-lf-starter_project",
    );
    await expect(addMcpNodeButton).toBeVisible({ timeout: 30_000 });
    await addMcpNodeButton.click();
    await expect(mcpNodes).toHaveCount(previousMcpNodeCount + 1, {
      timeout: 30_000,
    });

    await adjustScreenView(page, { numberOfZoomOut: 3 });

    await openAddMcpServerModal(page);

    // The generated uvx/mcp-proxy configuration is validated structurally
    // above. Exercise component-side discovery with the checked-in fixture so
    // this blocking test never downloads or executes an external MCP client.
    await page.getByTestId("stdio-tab").click();
    await page.waitForSelector('[data-testid="stdio-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    const randomSuffix = Math.floor(Math.random() * 90000) + 10000;
    const testName = `test_server_${randomSuffix}`;
    await page.getByTestId("stdio-name-input").fill(testName);
    await fillLocalMcpServerCommand(page);

    const serverSaveResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname.endsWith(
          `/api/v2/mcp/servers/${encodeURIComponent(testName)}`,
        ),
      { timeout: 30_000 },
    );
    const componentRefreshResponse = page.waitForResponse(
      (response) => {
        if (
          response.request().method() !== "POST" ||
          new URL(response.url()).pathname !== "/api/v1/custom_component/update"
        ) {
          return false;
        }
        try {
          const payload = response.request().postDataJSON();
          return (
            payload.field === "mcp_server" &&
            payload.field_value?.name === testName
          );
        } catch {
          return false;
        }
      },
      { timeout: 30_000 },
    );
    const flowSaveResponse = page.waitForResponse(
      (response) => {
        if (
          response.request().method() !== "PATCH" ||
          new URL(response.url()).pathname !== `/api/v1/flows/${mcpFlowId}`
        ) {
          return false;
        }
        try {
          const payload = response.request().postDataJSON();
          return payload.data?.nodes?.some(
            (node) =>
              node.data?.node?.template?.mcp_server?.value?.name === testName,
          );
        } catch {
          return false;
        }
      },
      { timeout: 30_000 },
    );
    await page.getByTestId("add-mcp-server-button").click();
    const [savedServer, refreshedComponent, savedFlow] = await Promise.all([
      serverSaveResponse,
      componentRefreshResponse,
      flowSaveResponse,
    ]);
    expect(savedServer.ok()).toBeTruthy();
    expect(refreshedComponent.ok()).toBeTruthy();
    expect(savedFlow.ok()).toBeTruthy();
    await Promise.all([
      savedServer.finished(),
      refreshedComponent.finished(),
      savedFlow.finished(),
    ]);

    await expect(page.getByTestId("add-mcp-server-button")).toBeHidden({
      timeout: 30_000,
    });

    await expect(page.getByTestId("dropdown_str_tool")).toBeVisible({
      timeout: 60000,
    });

    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 60000,
        state: "visible",
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    await expect(page.getByTestId("fetch-0-option")).toBeVisible({
      timeout: 30_000,
    });

    await page.keyboard.press("Escape");
    await page.getByTestId("icon-ChevronLeft").last().click();
    await expect(page.getByTestId("mainpage_title")).toBeVisible({
      timeout: 30_000,
    });
  },
);

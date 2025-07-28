import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user must be able to change mode of MCP tools without any issues",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("mcp tools");

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
    } catch (_error) {
      await page.getByTestId("mcp-server-dropdown").click({ timeout: 3000 });
      await page.getByText("Add MCP Server", { exact: true }).click({
        timeout: 5000,
      });
    }

    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "visible",
      timeout: 30000,
    });

    await page.getByTestId("stdio-tab").click();

    await page.waitForSelector('[data-testid="stdio-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    const randomSuffix = Math.floor(Math.random() * 90000) + 10000; // 5-digit random number
    const testName = `test_server_${randomSuffix}`;
    await page.getByTestId("stdio-name-input").fill(testName);

    await page.getByTestId("stdio-command-input").fill("uvx mcp-server-fetch");

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

    const fetchOptionCount = await page.getByTestId("fetch-0-option").count();

    expect(fetchOptionCount).toBeGreaterThan(0);

    await page.getByTestId("fetch-0-option").click();

    await page.waitForTimeout(2000);

    await page.getByTestId("fit_view").click();

    await page.waitForSelector('[data-testid="int_int_max_length"]', {
      state: "visible",
      timeout: 30000,
    });

    const maxLengthOptionCount = await page
      .getByTestId("int_int_max_length")
      .count();

    expect(maxLengthOptionCount).toBeGreaterThan(0);

    const urlOptionCount = await page
      .getByTestId("anchor-popover-anchor-input-url")
      .count();

    expect(urlOptionCount).toBeGreaterThan(0);

    await page.getByTestId("user_menu_button").click({ timeout: 3000 });

    await page.getByTestId("menu_settings_button").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Servers"]', {
      timeout: 30000,
    });

    await page.getByTestId("sidebar-nav-MCP Servers").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 3000,
    });

    await expect(page.getByText(testName)).toBeVisible({
      timeout: 3000,
    });

    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 3000 });

    await page
      .getByText("Edit", { exact: true })
      .first()
      .click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "visible",
      timeout: 30000,
    });

    await expect(page.getByTestId("json-tab")).toBeDisabled({
      timeout: 3000,
    });

    await expect(page.getByTestId("stdio-tab")).not.toBeDisabled({
      timeout: 3000,
    });

    await expect(page.getByTestId("sse-tab")).toBeDisabled({
      timeout: 3000,
    });

    expect(await page.getByTestId("stdio-command-input").inputValue()).toBe(
      "uvx mcp-server-fetch",
    );

    await page.getByTestId("add-mcp-server-button").click();

    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 3000 });

    await page
      .getByText("Delete", { exact: true })
      .first()
      .click({ timeout: 3000 });

    await page.waitForSelector(
      '[data-testid="btn_delete_delete_confirmation_modal"]',
      {
        timeout: 3000,
      },
    );

    await page
      .getByTestId("btn_delete_delete_confirmation_modal")
      .click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 3000,
    });

    await page.waitForTimeout(3000);

    await expect(page.getByText(testName)).not.toBeVisible({
      timeout: 3000,
    });

    await awaitBootstrapTest(page, { skipModal: true });
    await page.getByText("Untitled document").first().click();

    await page.waitForTimeout(1000);

    await page.waitForSelector('[data-testid="save-mcp-server-button"]', {
      timeout: 10000,
    });

    await page.getByTestId("save-mcp-server-button").click({ timeout: 10000 });

    await page.waitForTimeout(1000);

    await expect(page.getByTestId("save-mcp-server-button")).toBeHidden({
      timeout: 10000,
    });

    await page.getByTestId("mcp-server-dropdown").click({ timeout: 10000 });
    await expect(page.getByText(testName)).toHaveCount(2, {
      timeout: 10000,
    });
  },
);

test(
  "STDIO MCP server fields should persist after saving and editing",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("mcp tools");

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

    try {
      await page.getByText("Add MCP Server", { exact: true }).click({
        timeout: 5000,
      });
    } catch (_error) {
      await page.getByTestId("mcp-server-dropdown").click({ timeout: 3000 });
      await page.getByText("Add MCP Server", { exact: true }).click({
        timeout: 5000,
      });
    }

    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "visible",
      timeout: 30000,
    });

    // Go to STDIO tab and fill all fields
    await page.getByTestId("stdio-tab").click();
    await page.waitForSelector('[data-testid="stdio-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    // Test data with random suffix
    const randomSuffix = Math.floor(Math.random() * 90000) + 10000; // 5-digit random number
    const testName = `test_stdio_server_${randomSuffix}`;
    const testCommand = "uvx mcp-server-test";
    const testArg1 = "--verbose";
    const testArg2 = "--port=8080";
    const testArg3 = "--config=test.json";
    const testEnvKey1 = "NODE_ENV";
    const testEnvValue1 = "production";
    const testEnvKey2 = "DEBUG_MODE";
    const testEnvValue2 = "true";

    // Fill basic fields
    await page.getByTestId("stdio-name-input").fill(testName);
    await page.getByTestId("stdio-command-input").fill(testCommand);

    // Add first argument
    await page.getByTestId("stdio-args_0").fill(testArg1);

    // Add second argument by clicking plus button
    await page.getByTestId("input-list-plus-btn_-0").click();
    await page.getByTestId("stdio-args_1").fill(testArg2);

    // Add third argument
    await page.getByTestId("input-list-plus-btn_-0").click();
    await page.getByTestId("stdio-args_2").fill(testArg3);

    // Add first environment variable
    await page.getByTestId("stdio-env-key-0").fill(testEnvKey1);
    await page.getByTestId("stdio-env-value-0").fill(testEnvValue1);

    // Add second environment variable
    await page.getByTestId("stdio-env-plus-btn-0").click();
    await page.getByTestId("stdio-env-key-1").fill(testEnvKey2);
    await page.getByTestId("stdio-env-value-1").fill(testEnvValue2);

    // Save the server
    await page.getByTestId("add-mcp-server-button").click();

    // Wait for server to be created
    await page.waitForTimeout(2000);

    // Go to settings to edit the server
    await page.getByTestId("user_menu_button").click({ timeout: 3000 });
    await page.getByTestId("menu_settings_button").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Servers"]', {
      timeout: 30000,
    });
    await page.getByTestId("sidebar-nav-MCP Servers").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 3000,
    });

    // Find and edit the server
    await expect(page.getByText(testName)).toBeVisible({
      timeout: 3000,
    });

    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 3000 });

    await page
      .getByText("Edit", { exact: true })
      .first()
      .click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "visible",
      timeout: 30000,
    });

    // Verify all fields persisted correctly
    expect(await page.getByTestId("stdio-name-input").inputValue()).toBe(
      testName,
    );
    expect(await page.getByTestId("stdio-command-input").inputValue()).toBe(
      testCommand,
    );
    expect(await page.getByTestId("stdio-args_0").inputValue()).toBe(testArg1);
    expect(await page.getByTestId("stdio-args_1").inputValue()).toBe(testArg2);
    expect(await page.getByTestId("stdio-args_2").inputValue()).toBe(testArg3);
    expect(await page.getByTestId("stdio-env-key-0").last().inputValue()).toBe(
      testEnvKey1,
    );
    expect(
      await page.getByTestId("stdio-env-value-0").last().inputValue(),
    ).toBe(testEnvValue1);
    expect(await page.getByTestId("stdio-env-key-1").last().inputValue()).toBe(
      testEnvKey2,
    );
    expect(
      await page.getByTestId("stdio-env-value-1").last().inputValue(),
    ).toBe(testEnvValue2);

    // Clean up - cancel the edit modal
    await page.keyboard.press("Escape");

    // Delete the test server
    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 3000 });

    await page
      .getByText("Delete", { exact: true })
      .first()
      .click({ timeout: 3000 });

    await page.waitForSelector(
      '[data-testid="btn_delete_delete_confirmation_modal"]',
      {
        timeout: 3000,
      },
    );

    await page
      .getByTestId("btn_delete_delete_confirmation_modal")
      .click({ timeout: 3000 });
  },
);

test(
  "SSE MCP server fields should persist after saving and editing",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("mcp tools");

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

    try {
      await page.getByText("Add MCP Server", { exact: true }).click({
        timeout: 5000,
      });
    } catch (_error) {
      await page.getByTestId("mcp-server-dropdown").click({ timeout: 3000 });
      await page.getByText("Add MCP Server", { exact: true }).click({
        timeout: 5000,
      });
    }

    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "visible",
      timeout: 30000,
    });

    // Go to SSE tab and fill all fields
    await page.getByTestId("sse-tab").click();
    await page.waitForSelector('[data-testid="sse-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    // Test data with random suffix
    const randomSuffix = Math.floor(Math.random() * 90000) + 10000; // 5-digit random number
    const testName = `test_sse_server_${randomSuffix}`;
    const testUrl = "https://api.example.com/mcp";
    const testHeaderKey1 = "Authorization";
    const testHeaderValue1 = "Bearer token123";
    const testHeaderKey2 = "Content-Type";
    const testHeaderValue2 = "application/json";
    const testEnvKey1 = "API_TIMEOUT";
    const testEnvValue1 = "30000";
    const testEnvKey2 = "RETRY_COUNT";
    const testEnvValue2 = "3";

    // Fill basic fields
    await page.getByTestId("sse-name-input").fill(testName);
    await page.getByTestId("sse-url-input").fill(testUrl);

    // Add first header
    await page.getByTestId("sse-headers-key-0").fill(testHeaderKey1);
    await page.getByTestId("sse-headers-value-0").fill(testHeaderValue1);

    // Add second header
    await page.getByTestId("sse-headers-plus-btn-0").click();
    await page.getByTestId("sse-headers-key-1").fill(testHeaderKey2);
    await page.getByTestId("sse-headers-value-1").fill(testHeaderValue2);

    // Add first environment variable
    await page.getByTestId("sse-env-key-0").fill(testEnvKey1);
    await page.getByTestId("sse-env-value-0").fill(testEnvValue1);

    // Add second environment variable
    await page.getByTestId("sse-env-plus-btn-0").click();
    await page.getByTestId("sse-env-key-1").fill(testEnvKey2);
    await page.getByTestId("sse-env-value-1").fill(testEnvValue2);

    // Save the server
    await page.getByTestId("add-mcp-server-button").click();

    // Wait for server to be created
    await page.waitForTimeout(2000);

    // Go to settings to edit the server
    await page.getByTestId("user_menu_button").click({ timeout: 3000 });
    await page.getByTestId("menu_settings_button").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Servers"]', {
      timeout: 30000,
    });
    await page.getByTestId("sidebar-nav-MCP Servers").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 3000,
    });

    // Find and edit the server
    await expect(page.getByText(testName)).toBeVisible({
      timeout: 3000,
    });

    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 3000 });

    await page
      .getByText("Edit", { exact: true })
      .first()
      .click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "visible",
      timeout: 30000,
    });

    // Verify all fields persisted correctly
    expect(await page.getByTestId("sse-name-input").inputValue()).toBe(
      testName,
    );
    expect(await page.getByTestId("sse-url-input").inputValue()).toBe(testUrl);
    expect(await page.getByTestId("sse-headers-key-0").inputValue()).toBe(
      testHeaderKey1,
    );
    expect(await page.getByTestId("sse-headers-value-0").inputValue()).toBe(
      testHeaderValue1,
    );
    expect(await page.getByTestId("sse-headers-key-1").inputValue()).toBe(
      testHeaderKey2,
    );
    expect(await page.getByTestId("sse-headers-value-1").inputValue()).toBe(
      testHeaderValue2,
    );
    expect(await page.getByTestId("sse-env-key-0").inputValue()).toBe(
      testEnvKey1,
    );
    expect(await page.getByTestId("sse-env-value-0").inputValue()).toBe(
      testEnvValue1,
    );
    expect(await page.getByTestId("sse-env-key-1").inputValue()).toBe(
      testEnvKey2,
    );
    expect(await page.getByTestId("sse-env-value-1").inputValue()).toBe(
      testEnvValue2,
    );

    // Clean up - cancel the edit modal
    await page.keyboard.press("Escape");

    // Delete the test server
    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 3000 });

    await page
      .getByText("Delete", { exact: true })
      .first()
      .click({ timeout: 3000 });

    await page.waitForSelector(
      '[data-testid="btn_delete_delete_confirmation_modal"]',
      {
        timeout: 3000,
      },
    );

    await page
      .getByTestId("btn_delete_delete_confirmation_modal")
      .click({ timeout: 3000 });
  },
);

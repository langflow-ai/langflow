import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
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
        targetPosition: { x: 100, y: 100 },
      });

    // See if the color matches

    const isDark = await page.evaluate(() => {
      return document.body.classList.contains("dark");
    });

    for (const path of await page
      .getByTestId("generic-node-title-arrangement")
      .getByTestId("icon-Mcp")
      .locator("path")
      .all()) {
      const color = await path.evaluate(
        (el) => window.getComputedStyle(el).fill,
      );
      expect(color).toBe(isDark ? "rgb(255, 255, 255)" : "rgb(0, 0, 0)");
    }

    await adjustScreenView(page, { numberOfZoomOut: 3 });

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
    await adjustScreenView(page);

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

    await expect(page.getByTestId("http-tab")).toBeDisabled({
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
    const newFlowDiv = await page
      .getByTestId("flow-name-div")
      .filter({ hasText: "New Flow" })
      .first();
    await newFlowDiv.click();

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
  "user must be able to add and delete MCP server from sidebar",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-nav-mcp").click();

    const sidebarButton = page.getByTestId("sidebar-add-mcp-server-button");
    const fallbackButton = page.getByTestId("add-mcp-server-button-sidebar");

    if (await sidebarButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await sidebarButton.click();
    } else {
      await fallbackButton.click();
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

    await page.waitForTimeout(1000);

    await page.getByTestId(`add-component-button-${testName}`).click();

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
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("canvas_controls_dropdown").click();

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

    await page.getByTestId(`mcp${testName}`).click({ button: "right" });

    await page.getByTestId("draggable-component-menu-delete").click();

    await page.waitForSelector(
      '[data-testid="btn_delete_delete_confirmation_modal"]',
      {
        timeout: 3000,
      },
    );

    await page
      .getByTestId("btn_delete_delete_confirmation_modal")
      .click({ timeout: 3000 });

    await expect(
      page.locator('[data-testid="display-name"]', { hasText: testName }),
    ).not.toBeVisible({ timeout: 10000 });

    await page.waitForSelector('[data-testid="save-mcp-server-button"]', {
      timeout: 10000,
    });

    await page.getByTestId("save-mcp-server-button").click({ timeout: 10000 });

    await page.waitForTimeout(1000);

    await expect(page.getByTestId("save-mcp-server-button")).toBeHidden({
      timeout: 10000,
    });

    await page.getByTestId("mcp-server-dropdown").click({ timeout: 10000 });
    await expect(page.getByText(testName)).toHaveCount(3, {
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
        targetPosition: { x: 100, y: 100 },
      });
    await adjustScreenView(page, { numberOfZoomOut: 3 });

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
  "HTTP/SSE MCP server fields should persist after saving and editing",
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
        targetPosition: { x: 100, y: 100 },
      });
    await adjustScreenView(page, { numberOfZoomOut: 3 });

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

    // Go to HTTP tab and fill all fields
    await page.getByTestId("http-tab").click();
    await page.waitForSelector('[data-testid="http-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    // Test data with random suffix
    const randomSuffix = Math.floor(Math.random() * 90000) + 10000; // 5-digit random number
    const testName = `test_http_server_${randomSuffix}`;
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
    await page.getByTestId("http-name-input").fill(testName);
    await page.getByTestId("http-url-input").fill(testUrl);

    // Add first header
    await page.getByTestId("http-headers-key-0").fill(testHeaderKey1);
    await page.getByTestId("http-headers-value-0").fill(testHeaderValue1);

    // Add second header
    await page.getByTestId("http-headers-plus-btn-0").click();
    await page.getByTestId("http-headers-key-1").fill(testHeaderKey2);
    await page.getByTestId("http-headers-value-1").fill(testHeaderValue2);

    // Add first environment variable
    await page.getByTestId("http-env-key-0").fill(testEnvKey1);
    await page.getByTestId("http-env-value-0").fill(testEnvValue1);

    // Add second environment variable
    await page.getByTestId("http-env-plus-btn-0").click();
    await page.getByTestId("http-env-key-1").fill(testEnvKey2);
    await page.getByTestId("http-env-value-1").fill(testEnvValue2);

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
    expect(await page.getByTestId("http-name-input").inputValue()).toBe(
      testName,
    );
    expect(await page.getByTestId("http-url-input").inputValue()).toBe(testUrl);
    expect(await page.getByTestId("http-headers-key-0").inputValue()).toBe(
      testHeaderKey1,
    );
    expect(await page.getByTestId("http-headers-value-0").inputValue()).toBe(
      testHeaderValue1,
    );
    expect(await page.getByTestId("http-headers-key-1").inputValue()).toBe(
      testHeaderKey2,
    );
    expect(await page.getByTestId("http-headers-value-1").inputValue()).toBe(
      testHeaderValue2,
    );
    expect(await page.getByTestId("http-env-key-0").inputValue()).toBe(
      testEnvKey1,
    );
    expect(await page.getByTestId("http-env-value-0").inputValue()).toBe(
      testEnvValue1,
    );
    expect(await page.getByTestId("http-env-key-1").inputValue()).toBe(
      testEnvKey2,
    );
    expect(await page.getByTestId("http-env-value-1").inputValue()).toBe(
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

test(
  "mcp server tools should be refreshed when editing a server",
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
        targetPosition: { x: 100, y: 100 },
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
    await page.getByTestId("canvas_controls_dropdown").click();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("canvas_controls_dropdown").click();

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

    await expect(page.getByTestId("http-tab")).toBeDisabled({
      timeout: 3000,
    });

    expect(await page.getByTestId("stdio-command-input").inputValue()).toBe(
      "uvx mcp-server-fetch",
    );

    await page.getByTestId("stdio-command-input").fill("uvx mcp-server-time");

    await page.getByTestId("add-mcp-server-button").click();

    await awaitBootstrapTest(page, { skipModal: true });

    const newFlowDiv = await page
      .getByTestId("flow-name-div")
      .filter({ hasText: "New Flow" })
      .first();
    await newFlowDiv.click();

    try {
      await page.waitForSelector('[data-testid="dropdown_str_tool"]:disabled', {
        timeout: 10000,
        state: "visible",
      });
    } catch (_) {
      console.warn("Dropdown tool is not disabled, continuing...");
    }

    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 10000,
        state: "visible",
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    const timeOptionCount = await page
      .getByTestId("get_current_time-0-option")
      .count();

    expect(timeOptionCount).toBeGreaterThan(0);

    await page.getByTestId("user_menu_button").click({ timeout: 3000 });

    await page.getByTestId("menu_settings_button").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Servers"]', {
      timeout: 30000,
    });

    await page.getByTestId("sidebar-nav-MCP Servers").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 3000,
    });
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

    await page.getByTestId("add-mcp-server-button-page").click();

    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "visible",
      timeout: 30000,
    });

    await page.getByTestId("stdio-tab").click();

    await page.waitForSelector('[data-testid="stdio-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    await page.getByTestId("stdio-name-input").fill(testName);

    await page.getByTestId("stdio-command-input").fill("uvx mcp-server-fetch");

    await page.getByTestId("add-mcp-server-button").click();

    await expect(page.getByText(testName)).toBeVisible({
      timeout: 3000,
    });

    await awaitBootstrapTest(page, { skipModal: true });

    const newFlowDiv2 = await page
      .getByTestId("flow-name-div")
      .filter({ hasText: "New Flow" })
      .first();
    await newFlowDiv2.click();

    try {
      await page.waitForSelector('[data-testid="dropdown_str_tool"]:disabled', {
        timeout: 10000,
        state: "visible",
      });
    } catch (_) {
      console.warn("Dropdown tool is not disabled, continuing...");
    }

    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 10000,
        state: "visible",
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    const fetchOptionCount2 = await page.getByTestId("fetch-0-option").count();

    expect(fetchOptionCount2).toBeGreaterThan(0);
  },
);

test(
  "Streamable HTTP MCP server with server-everything should load tools correctly",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    // Start the MCP server with proper health checking
    const server = "https://mcp.deepwiki.com/mcp";
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
        targetPosition: { x: 100, y: 100 },
      });

    await adjustScreenView(page, { numberOfZoomOut: 3 });

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

    // Switch to HTTP tab for Streamable HTTP
    await page.getByTestId("http-tab").click();

    await page.waitForSelector('[data-testid="http-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    const randomSuffix = Math.floor(Math.random() * 90000) + 10000;
    const testName = `test_streamable_http_${randomSuffix}`;

    // Fill in the server details
    await page.getByTestId("http-name-input").fill(testName);

    // Use the HTTP endpoint URL
    await page.getByTestId("http-url-input").fill(server);

    await page.getByTestId("add-mcp-server-button").click();

    // Wait for tools to load with proper timeout
    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 10000,
        state: "visible",
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    // Check for tools from server
    const toolOptions = page.locator('[data-testid*="-option"]');
    const toolCount = await toolOptions.count();

    // server-everything should have multiple tools (at least 5+)
    expect(toolCount).toBeGreaterThan(5);

    // Verify specific tools exist from server-everything
    const readWikiStructureOption = page.getByTestId(
      "read_wiki_structure-0-option",
    );
    expect(await readWikiStructureOption.count()).toBeGreaterThan(0);

    // Select the option to verify it loads properly
    await readWikiStructureOption.last().click();

    // Wait for the tool input field to appear
    await page.waitForSelector(
      '[data-testid="popover-anchor-input-repoName"]',
      {
        state: "visible",
        timeout: 10000,
      },
    );

    // Verify the input field is present
    await expect(
      page.getByTestId("popover-anchor-input-repoName"),
    ).toBeVisible();
  },
);

test(
  "SSE MCP server with deepwiki should load tools correctly",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    // Start the MCP server with proper health checking
    const server = "https://mcp.deepwiki.com/sse";

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
        targetPosition: { x: 100, y: 100 },
      });

    await adjustScreenView(page, { numberOfZoomOut: 3 });

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

    // Switch to HTTP tab for SSE
    await page.getByTestId("http-tab").click();

    await page.waitForSelector('[data-testid="http-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    const randomSuffix = Math.floor(Math.random() * 90000) + 10000;
    const testName = `test_sse_${randomSuffix}`;

    // Fill in the server details
    await page.getByTestId("http-name-input").fill(testName);

    // Use the HTTP endpoint URL
    await page.getByTestId("http-url-input").fill(server);

    await page.getByTestId("add-mcp-server-button").click();

    // Wait for tools to load with proper timeout
    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 10000,
        state: "visible",
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    // Check for tools from wiki
    const toolOptions = page.locator('[data-testid*="-option"]');
    const toolCount = await toolOptions.count();

    // server-everything should have multiple tools (at least 5+)
    expect(toolCount).toBeGreaterThan(5);

    // Verify specific tools exist from server-everything
    const readWikiStructureOption = page.getByTestId(
      "read_wiki_structure-0-option",
    );
    expect(await readWikiStructureOption.count()).toBeGreaterThan(0);

    // Select the readWikiStructure to verify it loads properly
    await readWikiStructureOption.last().click();

    // Wait for the tool input field to appear
    await page.waitForSelector(
      '[data-testid="popover-anchor-input-repoName"]',
      {
        state: "visible",
        timeout: 10000,
      },
    );

    // Verify the input field is present
    await expect(
      page.getByTestId("popover-anchor-input-repoName"),
    ).toBeVisible();
  },
);

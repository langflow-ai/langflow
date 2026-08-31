import { type ChildProcess, spawn } from "node:child_process";
import path from "node:path";
import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import {
  fillLocalMcpServerCommand,
  LOCAL_MCP_SERVER_ARGS,
} from "../../utils/fill-local-mcp-server-command";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";
import { useMcpServerListWithoutToolCounts } from "../../utils/mcp-server-list-without-tool-counts";
import { openAddMcpServerModal } from "../../utils/open-add-mcp-server-modal";

test.beforeEach(async ({ page }) => {
  await useMcpServerListWithoutToolCounts(page);
});

async function scrollMcpSidebarRowIntoView(page: Page, name: string) {
  const sidebar = page.getByRole("navigation", { name: "Components sidebar" });
  const mcpNavigationButton = page.getByTestId("sidebar-nav-mcp");
  const isExpanded = (await sidebar.getAttribute("data-state")) === "expanded";
  const isMcpActive =
    (await mcpNavigationButton.getAttribute("data-active")) === "true";

  if (!isExpanded) {
    await page.locator('[data-sidebar-collapsed-nav-item="mcp"]').click();
  } else if (!isMcpActive) {
    await mcpNavigationButton.click();
  }
  await expect(sidebar).toHaveAttribute("data-state", "expanded");
  await expect(mcpNavigationButton).toHaveAttribute("data-active", "true");

  const row = page.getByTestId(`mcp_${name.toLowerCase()}_draggable`);
  await expect(row).toBeAttached({ timeout: 30_000 });
  await row.evaluate((element) => {
    const scrollContainer = element.closest<HTMLElement>(
      '[data-sidebar="content"]',
    );
    if (!scrollContainer) {
      throw new Error("MCP sidebar scroll container was not found");
    }

    element.scrollIntoView({
      block: "center",
      inline: "nearest",
      behavior: "instant",
    });
  });
  await expect(row).toBeInViewport({ timeout: 30_000 });
  return row;
}

async function addMcpNodeFromSidebar(page: Page, name: string): Promise<void> {
  const toolDropdowns = page.getByTestId("dropdown_str_tool");
  const previousNodeCount = await toolDropdowns.count();
  const addButton = page.getByTestId(`add-component-button-${name}`);

  await expect(page.getByTestId("canvas-add-note-button")).toBeEnabled({
    timeout: 30_000,
  });
  await scrollMcpSidebarRowIntoView(page, name);
  await expect(addButton).toBeVisible({ timeout: 30_000 });
  await addButton.click();
  await expect(toolDropdowns).toHaveCount(previousNodeCount + 1, {
    timeout: 30_000,
  });
  await expect(
    page.getByRole("application", { name: "MCP Tools node" }).last(),
  ).toBeVisible({
    timeout: 30_000,
  });
}

async function fitMcpCanvas(page: Page, zoomOutCount = 0): Promise<void> {
  await expect(page.locator("#react-flow-id")).toBeVisible({
    timeout: 30_000,
  });
  await page.keyboard.press("ControlOrMeta+Digit1");
  for (let index = 0; index < zoomOutCount; index += 1) {
    await page.keyboard.press("ControlOrMeta+Minus");
  }
}

async function saveMcpServer(
  page: Parameters<typeof fillLocalMcpServerCommand>[0],
  name: string,
  method: "POST" | "PATCH" = "POST",
): Promise<void> {
  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === method &&
      new URL(response.url()).pathname.endsWith(
        `/api/v2/mcp/servers/${encodeURIComponent(name)}`,
      ),
    { timeout: 30_000 },
  );
  await page.getByTestId("add-mcp-server-button").click();
  const response = await saved;
  expect(
    response.ok(),
    `${method} MCP server ${name} returned ${response.status()} ${response.statusText()}`,
  ).toBeTruthy();
  await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
    state: "hidden",
    timeout: 30_000,
  });
}

async function startStreamableHttpFixture(port: number): Promise<ChildProcess> {
  const fixture = path.resolve(
    __dirname,
    "../../fixtures/mcp-loopback-server.py",
  );
  const child = spawn(
    "uv",
    [
      "run",
      "python",
      fixture,
      "--transport",
      "streamable-http",
      "--port",
      String(port),
      "--tool-set",
      "all",
    ],
    { stdio: "pipe" },
  );
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`Local MCP HTTP fixture exited with ${child.exitCode}`);
    }
    try {
      const response = await fetch(`http://127.0.0.1:${port}/mcp`);
      if (response.status < 500) return child;
    } catch {
      // The checked-in fixture may still be binding its loopback socket.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  child.kill("SIGTERM");
  throw new Error("Local MCP HTTP fixture did not become ready");
}

async function stopFixture(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  await new Promise<void>((resolve) => {
    child.once("exit", () => resolve());
    setTimeout(resolve, 2_000);
  });
}

test(
  "user must be able to change mode of MCP tools without any issues",
  {
    tag: ["@release", "@workspace", "@components"],
  },
  async ({ page }) => {
    await openBlankFlow(page);
    await page.getByTestId("sidebar-nav-mcp").click();
    await addMcpNodeFromSidebar(page, "lf-starter_project");
    await fitMcpCanvas(page, 3);
    await openAddMcpServerModal(page);

    await page.getByTestId("stdio-tab").click();

    await page.waitForSelector('[data-testid="stdio-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    const randomSuffix = Math.floor(Math.random() * 90000) + 10000; // 5-digit random number
    const testName = `test_server_${randomSuffix}`;
    await page.getByTestId("stdio-name-input").fill(testName);

    await fillLocalMcpServerCommand(page);

    await saveMcpServer(page, testName);

    // See if the color matches
    const isDark = await page.evaluate(() => {
      return document.body.classList.contains("dark");
    });
    for (const icon of await page
      .getByRole("application", { name: "MCP Tools node" })
      .last()
      .getByTestId("icon-Mcp")
      .locator("path")
      .all()) {
      const color = await icon.evaluate(
        (element) => window.getComputedStyle(element).fill,
      );
      expect(color).toBe(isDark ? "rgb(255, 255, 255)" : "rgb(0, 0, 0)");
    }

    // Wait for the modal overlay to fully close
    await page
      .locator(".fixed.inset-0.z-50")
      .waitFor({ state: "hidden", timeout: 10000 })
      .catch(() => {});

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
      timeout: 30000,
    });

    await page.getByTestId("fetch-0-option").click();

    await fitMcpCanvas(page);

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

    await page.waitForTimeout(500);

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Servers"]', {
      timeout: 30000,
    });

    await page.getByTestId("sidebar-nav-MCP Servers").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 3000,
    });

    await expect(page.getByText(testName, { exact: true })).toBeVisible({
      timeout: 3000,
    });

    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 3000 });

    await page
      .getByText("Edit", { exact: true })
      .first()
      .click({ timeout: 3000 });

    await page.waitForTimeout(500);

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
      "python",
    );
    for (const [index, arg] of LOCAL_MCP_SERVER_ARGS.entries()) {
      expect(await page.getByTestId(`stdio-args_${index}`).inputValue()).toBe(
        arg,
      );
    }

    await page.waitForTimeout(500);

    await saveMcpServer(page, testName, "PATCH");

    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 30000 });

    await page.waitForTimeout(500);

    await page
      .getByText(TEXTS.delete, { exact: true })
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

    await expect(page.getByText(testName, { exact: true })).not.toBeVisible({
      timeout: 10000,
    });
  },
);

test(
  "user must be able to add and delete MCP server from sidebar",
  {
    tag: ["@release", "@workspace", "@components"],
  },
  async ({ page }) => {
    await openBlankFlow(page);
    await page.getByTestId("sidebar-nav-mcp").click();
    await openAddMcpServerModal(page, { source: "sidebar" });

    await page.getByTestId("stdio-tab").click();

    await page.waitForSelector('[data-testid="stdio-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    const randomSuffix = Math.floor(Math.random() * 90000) + 10000; // 5-digit random number
    const testName = `test_server_${randomSuffix}`;
    await page.getByTestId("stdio-name-input").fill(testName);

    await fillLocalMcpServerCommand(page);

    await saveMcpServer(page, testName);
    await page.reload();
    await waitForFlowEditorReady(page);
    await page.getByTestId("sidebar-nav-mcp").click();
    await addMcpNodeFromSidebar(page, testName);

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
      timeout: 30000,
    });

    const fetchOptionCount = await page.getByTestId("fetch-0-option").count();

    expect(fetchOptionCount).toBeGreaterThan(0);

    await page.getByTestId("fetch-0-option").click();

    await fitMcpCanvas(page);

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

    const serverRow = await scrollMcpSidebarRowIntoView(page, testName);
    await serverRow.click({ button: "right" });

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

    await expect(page.getByTestId("save-mcp-server-button")).toBeHidden({
      timeout: 30000,
    });

    await page.getByTestId("mcp-server-dropdown").click({ timeout: 10000 });
    await expect(page.getByText(testName)).toHaveCount(3, {
      timeout: 10000,
    });
  },
);

test(
  "STDIO MCP server fields should persist after saving and editing",
  {
    tag: ["@release", "@workspace", "@components"],
  },
  async ({ page }) => {
    await openBlankFlow(page);
    await page.getByTestId("sidebar-nav-mcp").click();
    await addMcpNodeFromSidebar(page, "lf-starter_project");
    await fitMcpCanvas(page, 3);
    await openAddMcpServerModal(page);

    // Go to STDIO tab and fill all fields
    await page.getByTestId("stdio-tab").click();
    await page.waitForSelector('[data-testid="stdio-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    // Test data with random suffix
    const randomSuffix = Math.floor(Math.random() * 90000) + 10000; // 5-digit random number
    const testName = `test_stdio_server_${randomSuffix}`;
    const testCommand = "python";
    const testArg1 = "tests/fixtures/mcp-loopback-server.py";
    const testArg2 = "--transport";
    const testArg3 = "stdio";
    const testArg4 = "--tool-set=fetch";
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

    // Add fourth argument
    await page.getByTestId("input-list-plus-btn_-0").click();
    await page.getByTestId("stdio-args_3").fill(testArg4);

    // Add first environment variable
    await page.getByTestId("stdio-env-key-0").fill(testEnvKey1);
    await page.getByTestId("stdio-env-value-0").fill(testEnvValue1);

    // Add second environment variable
    await page.getByTestId("stdio-env-plus-btn-0").click();
    await page.getByTestId("stdio-env-key-1").fill(testEnvKey2);
    await page.getByTestId("stdio-env-value-1").fill(testEnvValue2);

    // Save the server
    await saveMcpServer(page, testName);

    // Go to settings to edit the server
    await page.getByTestId("user_menu_button").click({ timeout: 30000 });
    await page.getByTestId("menu_settings_button").click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Servers"]', {
      timeout: 30000,
    });
    await page.getByTestId("sidebar-nav-MCP Servers").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 3000,
    });

    // Find and edit the server
    await expect(page.getByText(testName, { exact: true })).toBeVisible({
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
    expect(await page.getByTestId("stdio-args_3").inputValue()).toBe(testArg4);
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
      .getByText(TEXTS.delete, { exact: true })
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
  {
    tag: ["@release", "@workspace", "@components"],
  },
  async ({ page }) => {
    await openBlankFlow(page);
    await page.getByTestId("sidebar-nav-mcp").click();
    await addMcpNodeFromSidebar(page, "lf-starter_project");
    await fitMcpCanvas(page, 3);
    await openAddMcpServerModal(page);

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
    await page
      .getByTestId("popover-anchor-http-headers-value-0")
      .first()
      .fill(testHeaderValue1);

    // Add second header
    await page.getByTestId("http-headers-plus-btn-0").click();
    await page.getByTestId("http-headers-key-1").fill(testHeaderKey2);
    // Use nth(1) to get the second value field
    await page
      .getByTestId("popover-anchor-http-headers-value-1")
      .first()
      .fill(testHeaderValue2);

    // Add first environment variable
    await page.getByTestId("http-env-key-0").fill(testEnvKey1);
    await page.getByTestId("http-env-value-0").fill(testEnvValue1);

    // Add second environment variable
    await page.getByTestId("http-env-plus-btn-0").click();
    await page.getByTestId("http-env-key-1").fill(testEnvKey2);
    await page.getByTestId("http-env-value-1").fill(testEnvValue2);

    // Save the server
    await saveMcpServer(page, testName);

    // Wait for save to complete and modal to close
    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "hidden",
      timeout: 30000,
    });

    // Go to settings to edit the server
    await page.getByTestId("user_menu_button").click({ timeout: 30000 });
    await page.getByTestId("menu_settings_button").click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Servers"]', {
      timeout: 30000,
    });
    await page.getByTestId("sidebar-nav-MCP Servers").click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 30000,
    });

    // Find and edit the server
    await expect(page.getByText(testName, { exact: true })).toBeVisible({
      timeout: 10000,
    });

    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 10000 });

    await page
      .getByText("Edit", { exact: true })
      .first()
      .click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "visible",
      timeout: 30000,
    });

    // Wait for form fields to be populated
    await page.waitForSelector('[data-testid="http-name-input"]', {
      state: "visible",
      timeout: 10000,
    });
    await page.waitForSelector(
      '[data-testid="popover-anchor-http-headers-value-0"]',
      {
        state: "visible",
        timeout: 10000,
      },
    );

    // Verify all fields persisted correctly
    expect(await page.getByTestId("http-name-input").inputValue()).toBe(
      testName,
    );
    expect(await page.getByTestId("http-url-input").inputValue()).toBe(testUrl);
    expect(await page.getByTestId("http-headers-key-0").inputValue()).toBe(
      testHeaderKey1,
    );
    // Header values use InputComponent with global variables
    expect(
      await page
        .getByTestId("popover-anchor-http-headers-value-0")
        .first()
        .inputValue(),
    ).toBe(testHeaderValue1);
    expect(await page.getByTestId("http-headers-key-1").inputValue()).toBe(
      testHeaderKey2,
    );
    expect(
      await page
        .getByTestId("popover-anchor-http-headers-value-1")
        .first()
        .inputValue(),
    ).toBe(testHeaderValue2);
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
      .click({ timeout: 10000 });

    await page
      .getByText(TEXTS.delete, { exact: true })
      .first()
      .click({ timeout: 10000 });

    await page.waitForSelector(
      '[data-testid="btn_delete_delete_confirmation_modal"]',
      {
        timeout: 10000,
      },
    );

    await page
      .getByTestId("btn_delete_delete_confirmation_modal")
      .click({ timeout: 10000 });
  },
);

test(
  "mcp server tools should be refreshed when editing a server",
  {
    tag: ["@release", "@workspace", "@components"],
  },
  async ({ page }) => {
    const blankFlowId = await openBlankFlow(page);
    await page.getByTestId("sidebar-nav-mcp").click();
    await addMcpNodeFromSidebar(page, "lf-starter_project");
    await fitMcpCanvas(page, 3);
    await openAddMcpServerModal(page);

    await page.getByTestId("stdio-tab").click();

    await page.waitForSelector('[data-testid="stdio-name-input"]', {
      state: "visible",
      timeout: 30000,
    });

    const randomSuffix = Math.floor(Math.random() * 90000) + 10000; // 5-digit random number
    const testName = `test_server_${randomSuffix}`;
    await page.getByTestId("stdio-name-input").fill(testName);

    await fillLocalMcpServerCommand(page);

    await saveMcpServer(page, testName);

    // Wait for save to complete and modal to close
    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "hidden",
      timeout: 30000,
    });

    // Wait for the modal overlay to fully close
    await page
      .locator(".fixed.inset-0.z-50")
      .waitFor({ state: "hidden", timeout: 10000 })
      .catch(() => {});

    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 60000,
        state: "visible",
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    await page.waitForSelector('[data-testid="fetch-0-option"]', {
      state: "visible",
      timeout: 30000,
    });

    await page.getByTestId("fetch-0-option").click();

    await fitMcpCanvas(page);

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

    await page.getByTestId("user_menu_button").click({ timeout: 10000 });

    await page.getByTestId("menu_settings_button").click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Servers"]', {
      timeout: 30000,
    });

    await page.getByTestId("sidebar-nav-MCP Servers").click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 30000,
    });

    await expect(page.getByText(testName, { exact: true })).toBeVisible({
      timeout: 10000,
    });

    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 10000 });

    await page
      .getByText("Edit", { exact: true })
      .first()
      .click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "visible",
      timeout: 30000,
    });

    await expect(page.getByTestId("json-tab")).toBeDisabled({
      timeout: 10000,
    });

    await expect(page.getByTestId("stdio-tab")).not.toBeDisabled({
      timeout: 10000,
    });

    await expect(page.getByTestId("http-tab")).toBeDisabled({
      timeout: 10000,
    });

    // Wait for command input to be populated
    await page.waitForSelector('[data-testid="stdio-command-input"]', {
      state: "visible",
      timeout: 10000,
    });

    expect(await page.getByTestId("stdio-command-input").inputValue()).toBe(
      "python",
    );
    for (const [index, arg] of LOCAL_MCP_SERVER_ARGS.entries()) {
      expect(await page.getByTestId(`stdio-args_${index}`).inputValue()).toBe(
        arg,
      );
    }

    // Swap the deterministic fixture's tool set without changing its transport.
    await page
      .getByTestId(`stdio-args_${LOCAL_MCP_SERVER_ARGS.length - 1}`)
      .fill("time");

    await saveMcpServer(page, testName, "PATCH");

    // Wait for save to complete and modal to close
    await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
      state: "hidden",
      timeout: 30000,
    });

    await page.goto(`/flow/${blankFlowId}`);
    await waitForFlowEditorReady(page);

    // Wait for the MCP Tools component to be visible on canvas
    await page.waitForSelector('text="MCP Tools"', {
      state: "visible",
      timeout: 30000,
    });
    await page.getByText("MCP Tools", { exact: true }).last().click();
    await fitMcpCanvas(page);
    // Re-select the server after returning to flow (server reference may be lost after editing)
    await page.waitForSelector('[data-testid="mcp-server-dropdown"]', {
      timeout: 30000,
      state: "visible",
    });
    await page.getByTestId("mcp-server-dropdown").click();
    await page.getByTestId(`list_item_${testName}`).click({ timeout: 10000 });

    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 60000,
        state: "visible",
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    await page.waitForSelector('[data-testid="get_current_time-0-option"]', {
      state: "visible",
      timeout: 30000,
    });

    const timeOptionCount = await page
      .getByTestId("get_current_time-0-option")
      .count();

    expect(timeOptionCount).toBeGreaterThan(0);

    await page.getByTestId("user_menu_button").click({ timeout: 10000 });

    await page.getByTestId("menu_settings_button").click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Servers"]', {
      timeout: 30000,
    });

    await page.getByTestId("sidebar-nav-MCP Servers").click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 30000,
    });
    await page
      .getByTestId(`mcp-server-menu-button-${testName}`)
      .click({ timeout: 10000 });

    await page
      .getByText(TEXTS.delete, { exact: true })
      .first()
      .click({ timeout: 10000 });

    await page.waitForSelector(
      '[data-testid="btn_delete_delete_confirmation_modal"]',
      {
        timeout: 10000,
      },
    );

    await page
      .getByTestId("btn_delete_delete_confirmation_modal")
      .click({ timeout: 10000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 10000,
    });

    await expect(page.getByText(testName, { exact: true })).not.toBeVisible({
      timeout: 10000,
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

    await fillLocalMcpServerCommand(page);

    await saveMcpServer(page, testName);

    await expect(page.getByText(testName, { exact: true })).toBeVisible({
      timeout: 10000,
    });

    await page.goto(`/flow/${blankFlowId}`);
    await waitForFlowEditorReady(page);

    // Wait for the MCP Tools component to be visible on canvas
    await page.waitForSelector('text="MCP Tools"', {
      state: "visible",
      timeout: 30000,
    });
    await page.getByText("MCP Tools", { exact: true }).last().click();

    // Re-select the server after returning to flow (server reference may be lost after editing)
    await page.waitForSelector('[data-testid="mcp-server-dropdown"]', {
      timeout: 30000,
      state: "visible",
    });
    await page.getByTestId("mcp-server-dropdown").click();
    await page.getByTestId(`list_item_${testName}`).click({ timeout: 10000 });

    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 60000,
        state: "visible",
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    await page.waitForSelector('[data-testid="fetch-0-option"]', {
      state: "visible",
      timeout: 30000,
    });

    const fetchOptionCount2 = await page.getByTestId("fetch-0-option").count();

    expect(fetchOptionCount2).toBeGreaterThan(0);
  },
);

test(
  "Streamable HTTP MCP server with server-everything should load tools correctly",
  {
    tag: ["@release", "@workspace", "@components"],
  },
  async ({ page }, testInfo) => {
    const port = 18_790 + testInfo.workerIndex;
    const fixture = await startStreamableHttpFixture(port);
    const server = `http://127.0.0.1:${port}/mcp`;
    try {
      await openBlankFlow(page);
      await page.getByTestId("sidebar-nav-mcp").click();
      await addMcpNodeFromSidebar(page, "lf-starter_project");
      await fitMcpCanvas(page, 3);
      await openAddMcpServerModal(page);

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

      await saveMcpServer(page, testName);

      // Wait for the modal overlay to fully close before interacting
      await page
        .locator(".fixed.inset-0.z-50")
        .waitFor({ state: "hidden", timeout: 10000 })
        .catch(() => {});

      // Wait for tools to load with proper timeout (external server can be slow in CI)
      await page.waitForSelector(
        '[data-testid="dropdown_str_tool"]:not([disabled])',
        {
          timeout: 60000,
          state: "visible",
        },
      );

      await page.getByTestId("dropdown_str_tool").click();

      // Verify the complete deterministic tool set before selecting a tool.
      const toolOptions = page.locator('[data-testid$="-option"]:visible');
      await expect(toolOptions).toHaveCount(3, { timeout: 30000 });
      const echoOption = page.locator(
        '[data-testid^="echo-"][data-testid$="-option"]',
      );
      const fetchOption = page.locator(
        '[data-testid^="fetch-"][data-testid$="-option"]',
      );
      const timeOption = page.locator(
        '[data-testid^="get_current_time-"][data-testid$="-option"]',
      );
      await expect(echoOption).toBeVisible();
      await expect(fetchOption).toBeVisible();
      await expect(timeOption).toBeVisible();

      const componentUpdated = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname ===
            "/api/v1/custom_component/update",
        { timeout: 30_000 },
      );
      await fetchOption.click();
      const updateResponse = await componentUpdated;
      expect(
        updateResponse.ok(),
        `Selecting the loopback MCP tool returned ${updateResponse.status()} ${updateResponse.statusText()}`,
      ).toBeTruthy();
      await expect(page.getByTestId("int_int_max_length")).toBeVisible();
      await expect(
        page.getByTestId("anchor-popover-anchor-input-url"),
      ).toBeVisible();
    } finally {
      await stopFixture(fixture);
    }
  },
);

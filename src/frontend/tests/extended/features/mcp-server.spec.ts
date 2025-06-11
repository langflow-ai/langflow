import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user must be able to change mode of MCP connection without any issues",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("mcp connection");

    await page.waitForSelector('[data-testid="dataMCP Connection"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("dataMCP Connection")
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

    await page.getByTestId("stdio-name-input").fill("test server");

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

    let fetchOptionCount = await page.getByTestId("fetch-0-option").count();

    expect(fetchOptionCount).toBeGreaterThan(0);

    await page.getByTestId("fetch-0-option").click();

    await page.waitForTimeout(2000);

    await page.getByTestId("fit_view").click();

    await page.waitForSelector('[data-testid="int_int_max_length"]', {
      state: "visible",
      timeout: 30000,
    });

    let maxLengthOptionCount = await page
      .getByTestId("int_int_max_length")
      .count();

    expect(maxLengthOptionCount).toBeGreaterThan(0);

    let urlOptionCount = await page
      .getByTestId("anchor-popover-anchor-input-url")
      .count();

    expect(urlOptionCount).toBeGreaterThan(0);

    await page.getByTestId("user_menu_button").click({ timeout: 3000 });

    await page.getByTestId("menu_settings_button").click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="sidebar-nav-MCP Connections"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("sidebar-nav-MCP Connections")
      .click({ timeout: 3000 });

    await page.waitForSelector('[data-testid="add-mcp-server-button-page"]', {
      timeout: 3000,
    });

    await expect(page.getByText("test_server")).toBeVisible({
      timeout: 3000,
    });

    await page
      .getByTestId(`mcp-server-menu-button-test_server`)
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
      .getByTestId(`mcp-server-menu-button-test_server`)
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

    await expect(page.getByText("test_server")).not.toBeVisible({
      timeout: 3000,
    });
  },
);

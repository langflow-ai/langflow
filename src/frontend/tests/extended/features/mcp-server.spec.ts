import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user must be able to change mode of MCP server without any issues",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("mcp server");

    await page.waitForSelector('[data-testid="toolsMCP Server"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("toolsMCP Server")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-mcp-server").click();
      });

    await page.getByTestId("fit_view").click();

    await zoomOut(page, 3);

    await page.getByTestId("dropdown_str_tool").isDisabled();

    await page.getByTestId("refresh-button-command").click();

    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 30000,
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    let fetchOptionCount = await page.getByTestId("fetch-0-option").count();

    expect(fetchOptionCount).toBeGreaterThan(0);

    await page.getByTestId("fetch-0-option").click();

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

    await page.getByTestId("tab_1_sse").click();

    await page.waitForSelector('[data-testid="textarea_str_sse_url"]', {
      state: "visible",
      timeout: 30000,
    });

    let sseURLCount = await page.getByTestId("textarea_str_sse_url").count();

    expect(sseURLCount).toBeGreaterThan(0);

    await page.waitForSelector('[data-testid="dropdown_str_tool"]:disabled', {
      timeout: 30000,
    });

    await page.getByTestId("tab_0_stdio").click();

    await page.getByTestId("refresh-button-command").click();

    await page.waitForSelector(
      '[data-testid="dropdown_str_tool"]:not([disabled])',
      {
        timeout: 30000,
      },
    );

    await page.getByTestId("dropdown_str_tool").click();

    fetchOptionCount = await page.getByTestId("fetch-0-option").count();

    await page.getByTestId("fetch-0-option").click();

    expect(fetchOptionCount).toBeGreaterThan(0);

    await page.waitForSelector('[data-testid="int_int_max_length"]', {
      state: "visible",
      timeout: 30000,
    });

    maxLengthOptionCount = await page.getByTestId("int_int_max_length").count();

    expect(maxLengthOptionCount).toBeGreaterThan(0);

    urlOptionCount = await page
      .getByTestId("anchor-popover-anchor-input-url")
      .count();

    expect(urlOptionCount).toBeGreaterThan(0);

    await page.getByTestId("tab_1_sse").click();

    await page.waitForSelector('[data-testid="textarea_str_sse_url"]', {
      state: "visible",
      timeout: 30000,
    });

    sseURLCount = await page.getByTestId("textarea_str_sse_url").count();

    expect(sseURLCount).toBeGreaterThan(0);

    await page.waitForSelector('[data-testid="dropdown_str_tool"]:disabled', {
      timeout: 30000,
    });
  },
);

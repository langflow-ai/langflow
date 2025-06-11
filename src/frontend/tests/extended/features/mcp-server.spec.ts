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

    await page.getByTestId("dropdown_str_tool").isDisabled();

    let attempts = 0;
    const maxAttempts = 3;
    let dropdownEnabled = false;

    while (attempts < maxAttempts && !dropdownEnabled) {
      await page.getByTestId("refresh-button-command").click();
      await page.waitForTimeout(3000);

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

    attempts = 0;
    dropdownEnabled = false;
    await page.waitForTimeout(1000);

    while (attempts < maxAttempts && !dropdownEnabled) {
      await page.waitForTimeout(3000);

      try {
        await page.waitForSelector(
          '[data-testid="dropdown_str_tool"]:not([disabled])',
          {
            timeout: 30000,
            state: "visible",
          },
        );
        dropdownEnabled = true;
      } catch (error) {
        attempts++;
        console.log(`Retry attempt ${attempts} for second refresh button`);
        await page.getByTestId("refresh-button-sse_url").click();
      }
    }

    if (!dropdownEnabled) {
      throw new Error(
        "Dropdown did not become enabled after multiple refresh attempts",
      );
    }

    await page.getByTestId("tab_0_stdio").click();

    await page.waitForTimeout(2000);

    await page.getByTestId("fit_view").click();

    attempts = 0;
    dropdownEnabled = false;

    while (attempts < maxAttempts && !dropdownEnabled) {
      await page.getByTestId("refresh-button-command").click();
      await page.waitForTimeout(3000);

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
        console.log(`Retry attempt ${attempts} for second refresh button`);
      }
    }

    if (!dropdownEnabled) {
      throw new Error(
        "Dropdown did not become enabled after multiple refresh attempts",
      );
    }

    await page.getByTestId("dropdown_str_tool").click();

    fetchOptionCount = await page.getByTestId("fetch-0-option").count();

    await page.getByTestId("fetch-0-option").click();

    await page.waitForTimeout(2000);

    await page.getByTestId("fit_view").click();

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

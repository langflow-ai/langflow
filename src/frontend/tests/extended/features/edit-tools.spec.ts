import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
test(
  "user should be able to edit tools",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

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

    await page.waitForTimeout(500);

    await page.getByTestId("tool-mode-button").click();

    await page.locator('[data-testid="icon-Hammer"]').nth(1).waitFor({
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("icon-Hammer").nth(1).click();

    await page.waitForSelector("text=edit tools", { timeout: 30000 });

    const rowsCount = await page.getByRole("gridcell").count();

    expect(rowsCount).toBeGreaterThan(3);

    expect(await page.getByRole("switch").nth(0).isChecked()).toBe(true);

    await page.getByRole("switch").nth(0).click();

    expect(await page.getByRole("switch").nth(0).isChecked()).toBe(false);

    await page.getByText("Save").last().click();

    await page.waitForSelector(
      '[data-testid="generic-node-title-arrangement"]',
      {
        timeout: 3000,
      },
    );

    await page.waitForTimeout(500);

    await page.getByTestId("icon-Hammer").nth(1).click();

    await page.waitForSelector("text=edit tools", { timeout: 30000 });

    await page.waitForTimeout(500);

    expect(await page.getByRole("switch").nth(0).isChecked()).toBe(false);
  },
);

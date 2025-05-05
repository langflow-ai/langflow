import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
test(
  "user should be able to edit flow name by clicking on the header or on the main page",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const randomName = Math.random().toString(36).substring(2, 15);
    const randomName2 = Math.random().toString(36).substring(2, 15);
    const randomName3 = Math.random().toString(36).substring(2, 15);
    const randomName4 = Math.random().toString(36).substring(2, 15);

    await awaitBootstrapTest(page);

    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.getByTestId("input-flow-name").click();

    await page.getByTestId("input-flow-name").fill(randomName);

    await page.keyboard.press("Enter");

    await page.waitForTimeout(1000);

    let flowName = await page.getByTestId("input-flow-name").inputValue();

    expect(flowName).toBe(randomName);

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 5000,
    });

    await page.waitForSelector(`text=${randomName}`, {
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText(randomName).count()).toBe(1);

    await page.getByText(randomName).click();

    await page.getByTestId("input-flow-name").click();

    await page.getByTestId("input-flow-name").fill(randomName2);

    await page.keyboard.press("Enter");

    await page.waitForTimeout(1000);

    flowName = await page.getByTestId("input-flow-name").inputValue();

    expect(flowName).toBe(randomName2);

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 5000,
    });

    await page.waitForSelector(`text=${randomName2}`, {
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText(randomName2).count()).toBe(1);

    await page.getByTestId("home-dropdown-menu").first().click();

    await page.getByTestId("btn-edit-flow").click();

    await page.getByTestId("input-flow-name").fill(randomName3);

    await page.getByTestId("save-flow-settings").click();

    await page.waitForSelector(`text=${randomName3}`, {
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText(randomName3).count()).toBe(1);

    await page.getByText(randomName3).click();

    await page.getByTestId("input-flow-name").click();

    await page.getByTestId("input-flow-name").fill(randomName4);

    await page.keyboard.press("Enter");

    await page.waitForTimeout(1000);

    flowName = await page.getByTestId("input-flow-name").inputValue();

    expect(flowName).toBe(randomName4);

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 5000,
    });

    await page.waitForSelector(`text=${randomName4}`, {
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText(randomName4).count()).toBe(1);
  },
);

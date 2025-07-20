import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { renameFlow } from "../../utils/rename-flow";

test(
  "user should be able to edit flow name by clicking on the header or on the main page",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    const randomName = Math.random().toString(36).substring(2, 15);
    const randomName2 = Math.random().toString(36).substring(2, 15);
    const randomName3 = Math.random().toString(36).substring(2, 15);
    const randomName4 = Math.random().toString(36).substring(2, 15);

    await awaitBootstrapTest(page);

    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await renameFlow(page, { flowName: randomName });

    const { flowName } = await renameFlow(page);

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

    await renameFlow(page, { flowName: randomName2 });

    const { flowName: flowName2 } = await renameFlow(page);

    expect(flowName2).toBe(randomName2);

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 5000,
    });

    await page.waitForSelector(`text=${randomName2}`, {
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText(randomName2).count()).toBe(1);

    await page.getByText(randomName2).click();

    await renameFlow(page, { flowName: randomName3 });

    const { flowName: flowName3 } = await renameFlow(page);

    expect(flowName3).toBe(randomName3);

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 5000,
    });

    await page.waitForSelector(`text=${randomName3}`, {
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText(randomName3).count()).toBe(1);

    await page.getByText(randomName3).click();

    await renameFlow(page, { flowName: randomName4 });

    const { flowName: flowName4 } = await renameFlow(page);

    expect(flowName4).toBe(randomName4);

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

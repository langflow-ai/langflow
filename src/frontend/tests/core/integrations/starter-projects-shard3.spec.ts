import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to use third quarter of starter projects without any outdated components on the flow",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();

    const numberOfTemplates = await page
      .getByTestId("text_card_container")
      .count();

    const secondQuarterEnd = Math.ceil((numberOfTemplates * 2) / 4);
    const thirdQuarterEnd = Math.ceil((numberOfTemplates * 3) / 4);
    let numberOfOutdatedComponents = 0;

    for (let i = secondQuarterEnd; i < thirdQuarterEnd; i++) {
      const exampleName = await page
        .getByTestId("text_card_container")
        .nth(i)
        .getAttribute("role");

      await page.getByTestId("text_card_container").nth(i).click();

      // Log which component is being tested
      console.log(`Testing starter project: ${exampleName}`);

      await page.waitForTimeout(500);

      await page.waitForSelector('[data-testid="div-generic-node"]', {
        timeout: 5000 * 3,
      });

      if ((await page.getByTestId("update-all-button").count()) > 0) {
        console.error(`
          ---------------------------------------------------------------------------------------
          There's an outdated component on the basic template: ${exampleName}
          ---------------------------------------------------------------------------------------
          `);
        numberOfOutdatedComponents++;
      }

      await Promise.all([
        page.waitForURL((url) => url.pathname === "/", { timeout: 30000 }),
        page.getByTestId("icon-ChevronLeft").click(),
      ]);

      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 30000,
      });

      await page.waitForTimeout(500);

      await page.waitForSelector('[data-testid="new-project-btn"]', {
        timeout: 5000,
      });

      await page.getByTestId("new-project-btn").first().click();

      await page.waitForSelector(
        '[data-testid="side_nav_options_all-templates"]',
        {
          timeout: 5000,
        },
      );

      await page.getByTestId("side_nav_options_all-templates").click();
    }

    expect(numberOfOutdatedComponents).toBe(0);
  },
);

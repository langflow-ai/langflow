import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to use first quarter of starter projects without any outdated components on the flow",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    const templatesData = [];
    let numberOfOutdatedComponents = 0;

    // First, collect all template data
    await page.getByTestId("side_nav_options_all-templates").click();

    const numberOfTemplates = await page
      .getByTestId("text_card_container")
      .count();

    const firstQuarterEnd = Math.ceil(numberOfTemplates / 4);

    console.log(
      `Total templates: ${numberOfTemplates}, Testing from 0 to ${firstQuarterEnd - 1} (first quarter)`,
    );

    // Collect template names first
    for (let i = 0; i < firstQuarterEnd; i++) {
      const exampleName = await page
        .getByTestId("text_card_container")
        .nth(i)
        .getAttribute("role");

      templatesData.push({ index: i, name: exampleName });
    }

    console.log(
      "Templates to test:",
      templatesData.map((t) => `${t.index}: ${t.name}`).join(", "),
    );

    // Now test each template individually using direct navigation
    for (const template of templatesData) {
      console.log(`Testing template ${template.index}: ${template.name}`);

      // Navigate directly to templates page
      await page.goto("/");
      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 30000,
      });
      await page.getByTestId("new-project-btn").first().click();
      await page.getByTestId("side_nav_options_all-templates").click();

      // Wait for templates to load
      await page.waitForSelector('[data-testid="text_card_container"]', {
        timeout: 10000,
      });

      // Click on the specific template
      await page.getByTestId("text_card_container").nth(template.index).click();

      await page.waitForTimeout(1000);

      await page.waitForSelector('[data-testid="div-generic-node"]', {
        timeout: 15000,
      });

      if ((await page.getByTestId("update-all-button").count()) > 0) {
        console.error(`
          ---------------------------------------------------------------------------------------
          There's an outdated component on the basic template: ${template.name}
          ---------------------------------------------------------------------------------------
          `);
        numberOfOutdatedComponents++;
      }
    }

    expect(numberOfOutdatedComponents).toBe(0);
  },
);

import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to use third quarter of starter projects without any outdated components on the flow",
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

    const secondQuarterEnd = Math.ceil((numberOfTemplates * 2) / 4);
    const thirdQuarterEnd = Math.ceil((numberOfTemplates * 3) / 4);

    console.log(
      `Total templates: ${numberOfTemplates}, Testing from ${secondQuarterEnd} to ${thirdQuarterEnd - 1} (third quarter)`,
    );

    // Collect template names first
    for (let i = secondQuarterEnd; i < thirdQuarterEnd; i++) {
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

      // Navigate directly to templates page with proper waiting
      await page.goto("/", { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle");

      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 30000,
      });

      // Use Promise.all to handle concurrent navigation and waiting
      await Promise.all([
        page.waitForLoadState("domcontentloaded"),
        page.getByTestId("new-project-btn").first().click(),
      ]);

      await Promise.all([
        page.waitForLoadState("domcontentloaded"),
        page.getByTestId("side_nav_options_all-templates").click(),
      ]);

      // Wait for templates to load with better reliability
      await page.waitForSelector('[data-testid="text_card_container"]', {
        timeout: 15000,
        state: "visible",
      });
      await page.waitForLoadState("networkidle");

      // Click on the specific template with proper navigation handling
      await Promise.all([
        page.waitForLoadState("domcontentloaded"),
        page.getByTestId("text_card_container").nth(template.index).click(),
      ]);

      // Wait for canvas to load properly
      await page.waitForSelector('[data-testid="div-generic-node"]', {
        timeout: 20000,
        state: "visible",
      });
      await page.waitForLoadState("domcontentloaded");

      if ((await page.getByTestId("update-all-button").count()) > 0) {
        console.error(`
          ---------------------------------------------------------------------------------------
          There's an outdated component on the basic template: ${template.name}
          ---------------------------------------------------------------------------------------
          `);
        numberOfOutdatedComponents++;
      }

      // Add a small delay between template tests to prevent race conditions
      await page.waitForTimeout(500);
    }

    expect(numberOfOutdatedComponents).toBe(0);
  },
);

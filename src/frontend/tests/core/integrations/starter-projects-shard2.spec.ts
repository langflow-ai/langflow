import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// Helper function to ensure element stability before interaction
async function waitForElementStability(
  page: any,
  selector: string,
  timeout = 5000,
) {
  await page.waitForSelector(selector, { state: "visible", timeout });
  // Additional wait to ensure element is stable and not moving
  await page.waitForTimeout(200);
  // Use first() to avoid strict mode violation when multiple elements exist
  await expect(page.locator(selector).first()).toBeVisible();
}

// Helper function to safely navigate with proper waiting
async function safeNavigateAndClick(
  page: any,
  testId: string,
  waitForSelector?: string,
) {
  const element = page.getByTestId(testId);
  await expect(element).toBeVisible({ timeout: 15000 });
  await element.click();

  if (waitForSelector) {
    await page.waitForLoadState("domcontentloaded");
    await waitForElementStability(page, waitForSelector);
  }
}

test(
  "user should be able to use first quarter of starter projects without any outdated components on the flow",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    const templatesData = [];
    let numberOfOutdatedComponents = 0;

    // First, collect all template data with proper waiting
    await safeNavigateAndClick(
      page,
      "side_nav_options_all-templates",
      '[data-testid="text_card_container"]',
    );

    // Wait for templates to fully load and stabilize
    await page.waitForLoadState("networkidle", { timeout: 30000 });
    await waitForElementStability(
      page,
      '[data-testid="text_card_container"]',
      20000,
    );

    // Ensure template count is stable by checking multiple times
    let numberOfTemplates = await page
      .getByTestId("text_card_container")
      .count();
    await page.waitForTimeout(1000); // Allow any dynamic loading to complete
    const verifyCount = await page.getByTestId("text_card_container").count();

    // If counts don't match, wait a bit more and try again
    if (numberOfTemplates !== verifyCount) {
      await page.waitForTimeout(2000);
      numberOfTemplates = await page.getByTestId("text_card_container").count();
    }

    const firstQuarterEnd = Math.ceil(numberOfTemplates / 4);

    console.log(
      `Total templates: ${numberOfTemplates}, Testing from 0 to ${firstQuarterEnd - 1} (first quarter)`,
    );

    // Collect template names first with stability checks
    for (let i = 0; i < firstQuarterEnd; i++) {
      // Ensure the specific template card is visible and stable
      const templateCard = page.getByTestId("text_card_container").nth(i);
      await expect(templateCard).toBeVisible({ timeout: 10000 });

      const exampleName = await templateCard.getAttribute("role");
      templatesData.push({ index: i, name: exampleName });
    }

    console.log(
      "Templates to test:",
      templatesData.map((t) => `${t.index}: ${t.name}`).join(", "),
    );

    // Now test each template individually using direct navigation
    for (const template of templatesData) {
      console.log(`Testing template ${template.index}: ${template.name}`);

      // Navigate directly to templates page with improved stability
      await page.goto("/", { waitUntil: "networkidle", timeout: 30000 });

      // Wait for main page to be fully loaded and stable
      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 30000,
      });
      await page.waitForLoadState("networkidle");

      // Sequential navigation with proper waiting (no Promise.all)
      await safeNavigateAndClick(page, "new-project-btn");
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(500); // Brief pause between navigation steps

      await safeNavigateAndClick(
        page,
        "side_nav_options_all-templates",
        '[data-testid="text_card_container"]',
      );
      await page.waitForLoadState("networkidle");

      // Ensure templates are fully loaded and stable before clicking
      await waitForElementStability(
        page,
        '[data-testid="text_card_container"]',
        20000,
      );

      // Wait for the specific template to be visible and stable
      const targetTemplate = page
        .getByTestId("text_card_container")
        .nth(template.index);
      await expect(targetTemplate).toBeVisible({ timeout: 15000 });
      await page.waitForTimeout(300); // Ensure element is stable

      await targetTemplate.click();

      // Wait for canvas to load properly with enhanced stability checks
      await page.waitForLoadState("domcontentloaded");
      await page.waitForLoadState("networkidle", { timeout: 30000 });

      // Wait for canvas elements to be visible and stable
      await waitForElementStability(
        page,
        '[data-testid="div-generic-node"]',
        25000,
      );

      // Additional wait to ensure all canvas components are fully rendered
      await page.waitForTimeout(1500);

      // Use auto-retrying assertion for checking outdated components
      const updateButtonCount = await page
        .getByTestId("update-all-button")
        .count();
      if (updateButtonCount > 0) {
        console.error(`
          ---------------------------------------------------------------------------------------
          There's an outdated component on the basic template: ${template.name}
          ---------------------------------------------------------------------------------------
          `);
        numberOfOutdatedComponents++;
      }

      // Longer delay between template tests to prevent race conditions
      await page.waitForTimeout(1000);
    }

    expect(numberOfOutdatedComponents).toBe(0);
  },
);

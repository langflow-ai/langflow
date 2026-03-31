import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to use second quarter of starter projects without any outdated components on the flow",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    const templatesData = [];
    let numberOfOutdatedComponents = 0;

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.waitForLoadState("networkidle", { timeout: 30000 });
    await expect(page.getByTestId("text_card_container").first()).toBeVisible({
      timeout: 20000,
    });

    const numberOfTemplates = await page
      .getByTestId("text_card_container")
      .count();

    const firstQuarterEnd = Math.ceil(numberOfTemplates / 4);
    const secondQuarterEnd = Math.ceil((numberOfTemplates * 2) / 4);

    console.log(
      `Total templates: ${numberOfTemplates}, Testing from ${firstQuarterEnd} to ${secondQuarterEnd - 1} (second quarter)`,
    );

    for (let i = firstQuarterEnd; i < secondQuarterEnd; i++) {
      const templateCard = page.getByTestId("text_card_container").nth(i);
      await expect(templateCard).toBeVisible({ timeout: 10000 });
      const exampleName = await templateCard.getAttribute("role");
      templatesData.push({ index: i, name: exampleName });
    }

    console.log(
      "Templates to test:",
      templatesData.map((t) => `${t.index}: ${t.name}`).join(", "),
    );

    for (const template of templatesData) {
      console.log(`Testing template ${template.index}: ${template.name}`);

      await page.goto("/", { waitUntil: "networkidle", timeout: 30000 });
      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 30000,
      });

      await page.getByTestId("new-project-btn").click();
      await page.waitForLoadState("domcontentloaded");

      await page.getByTestId("side_nav_options_all-templates").click();
      await page.waitForLoadState("networkidle", { timeout: 30000 });
      await expect(page.getByTestId("text_card_container").first()).toBeVisible(
        { timeout: 20000 },
      );

      const targetTemplate = page
        .getByTestId("text_card_container")
        .nth(template.index);
      await expect(targetTemplate).toBeVisible({ timeout: 15000 });
      await targetTemplate.click();

      await page.waitForLoadState("networkidle", { timeout: 30000 });
      await expect(
        page.locator('[data-testid="div-generic-node"]').first(),
      ).toBeVisible({ timeout: 25000 });

      const updateButtonCount = await page
        .getByTestId("update-all-button")
        .count();
      if (updateButtonCount > 0) {
        console.error(`Outdated component on template: ${template.name}`);
        numberOfOutdatedComponents++;
      }
    }

    expect(numberOfOutdatedComponents).toBe(0);
  },
);

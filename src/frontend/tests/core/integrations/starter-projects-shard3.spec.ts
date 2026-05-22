import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";

test(
  "user should be able to use second quarter of starter projects without any outdated components on the flow",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    test.skip(
      process.platform === "win32",
      "Flaky on Windows CI runners due to template-load workload; outdated-component check is OS-agnostic and covered by Linux/macOS runs",
    );

    await awaitBootstrapTest(page);

    const templatesData = [];
    let numberOfOutdatedComponents = 0;

    await page.getByTestId("side_nav_options_all-templates").click();
    // Avoid waitForLoadState("networkidle"): persistent connections
    // (MCP refresh, websockets) keep network busy and force the full 30s
    // timeout on every iteration. The toBeVisible() below already
    // auto-waits for actual readiness.
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

    for (let idx = 0; idx < templatesData.length; idx++) {
      const template = templatesData[idx];
      console.log(`Testing template ${template.index}: ${template.name}`);

      // First iteration: the templates modal is already open from the
      // data-collection step above, so skip the homepage round-trip.
      // Subsequent iterations: navigate back from the previous flow via
      // chevron-left instead of page.goto("/"). page.goto forces a full SPA
      // bundle re-execution which was the dominant per-iteration cost on
      // Linux CI and pushed shard 38 past its 12-minute attempt budget.
      if (idx > 0) {
        await page.getByTestId("icon-ChevronLeft").first().click();
        await expect(page.getByTestId("mainpage_title")).toBeVisible({
          timeout: 30000,
        });
        await openTemplatesModal(page);
        await page.waitForLoadState("domcontentloaded");
        await page.getByTestId("side_nav_options_all-templates").click();
        await expect(
          page.getByTestId("text_card_container").first(),
        ).toBeVisible({ timeout: 20000 });
      }

      const targetTemplate = page
        .getByTestId("text_card_container")
        .nth(template.index);
      await expect(targetTemplate).toBeVisible({ timeout: 15000 });
      await targetTemplate.click();

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

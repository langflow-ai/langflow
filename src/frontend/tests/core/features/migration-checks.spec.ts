import { CHECKS } from "../../../src/pages/SettingsPage/pages/MigrationPage/catalog";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "a superuser can check this instance before moving it to a new instance",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    // Opened by its address, the page renders before the server's feature flags arrive, so hold them back.
    let sendConfig = () => {};
    const held = new Promise<void>((resolve) => {
      sendConfig = resolve;
    });
    await page.route(
      "**/api/v1/config",
      async (route) => {
        await held;
        await route.continue();
      },
      { times: 1 },
    );
    await page.goto("/settings/migration");
    // The reload boots the whole app again before Settings renders, so it gets the bootstrap's wait.
    await expect(page.getByTestId("sidebar-nav-Global Variables")).toBeVisible({
      timeout: 30000,
    });
    expect(new URL(page.url()).pathname).toBe("/settings/migration");
    sendConfig();

    // A check that already passed on this instance, on a retry or a second local run, shows collapsed.
    const step = page.getByTestId("migration-step-check_source");
    await expect(step).toBeVisible();
    const reopen = step.getByRole("button", { name: "Check this instance" });
    if (await reopen.isVisible()) await reopen.click();

    // The placeholder shows this instance's version, and the same version passes.
    const version = page.getByTestId("migration-target-version");
    await version.fill((await version.getAttribute("placeholder")) ?? "");
    await page.getByTestId("migration-run-checks").click();

    // The page runs the real migration-preflight command against this instance.
    await expect(page.getByTestId("migration-checks-summary")).toBeVisible({
      timeout: 120000,
    });
    const passed = page.getByTestId("migration-group-passed");
    await expect(passed).toBeVisible();
    await expect(passed.getByTestId("migration-check-version")).toContainText(
      "New instance's version",
    );
    await expect(
      passed.getByTestId("migration-check-source: schema"),
    ).toContainText("Database version");
    // The progress line's total is the page's own list, so it has to match the checks the server sends.
    await expect(page.locator('[data-testid^="migration-check-"]')).toHaveCount(
      Object.keys(CHECKS).length,
    );

    // Pausing always waits for the steps before it, so it offers nothing to click.
    await expect(
      page.getByTestId("migration-step-pause").getByRole("button"),
    ).toHaveCount(0);

    // The record for support is what the page knows, saved as a file.
    const download = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "Download the migration record" })
      .click();
    expect((await download).suggestedFilename()).toMatch(
      /^langflow-migration-\d{8}\.json$/,
    );

    // On a phone the link wraps, so its end stays inside the page's column.
    await page.setViewportSize({ width: 390, height: 844 });
    const rightEdge = async (locator: ReturnType<typeof page.locator>) => {
      const box = await locator.boundingBox();
      return box ? box.x + box.width : Number.NaN;
    };
    expect(
      await rightEdge(
        page.getByRole("button", { name: "Download the migration record" }),
      ),
    ).toBeLessThanOrEqual((await rightEdge(step)) + 1);
  },
);

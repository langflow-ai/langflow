import { readFile } from "node:fs/promises";
import path from "node:path";
import type {
  RepairOutcome,
  RepairResult,
} from "../../src/controllers/API/queries/upgrade-reports";
import {
  history,
  preview,
  report,
} from "../../src/pages/SettingsPage/pages/UpgradeReportsPage/__tests__/fixture";
import { expect, test } from "../fixtures";
import { TIMEOUTS } from "../utils/constants/timeouts";

const routePath = "/settings/upgrade-reports";

test(
  "imports, reloads, and exports a persisted report",
  { tag: ["@release", "@database"] },
  async ({ page }) => {
    await page.goto(routePath);
    await expect(
      page.getByRole("heading", { name: "Upgrade reports", exact: true }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await page
      .getByLabel("Checker report file")
      .setInputFiles(
        path.resolve(
          __dirname,
          "../../../backend/tests/unit/api/v1/fixtures/upgrade-report-v1.json",
        ),
      );
    await page
      .getByRole("button", { name: "Import report", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "MCP flow", exact: true }),
    ).toBeVisible();
    await expect(page).toHaveURL(/report=/);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Upgrade reports", exact: true }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await expect(
      page.getByRole("heading", { name: "MCP flow", exact: true }),
    ).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export original report" }).click();
    const saved = await download;
    expect(saved.suggestedFilename()).toMatch(/^upgrade-report-.*\.json$/);
    expect(await readFile((await saved.path())!)).toEqual(
      await readFile(
        path.resolve(
          __dirname,
          "../../../backend/tests/unit/api/v1/fixtures/upgrade-report-v1.json",
        ),
      ),
    );
    await page.runA11yScan("upgrade-reports-persisted");
  },
);

test(
  "checks selection, repair confirmation, unknown history, and keyboard access",
  { tag: ["@release", "@database"] },
  async ({ page }) => {
    let recorded: RepairOutcome[] = [];
    const updated: RepairResult = {
      ...preview.results[0],
      status: "updated",
      recovery_version_id: "recovery-1",
    };
    await page.route("**/api/v1/upgrade-reports**", async (route) => {
      const pathname = new URL(route.request().url()).pathname;
      await route.fulfill({
        json: pathname.endsWith("/repairs")
          ? { items: recorded, total: recorded.length }
          : pathname.endsWith(report.id)
            ? report
            : history,
      });
    });
    await page.route("**/api/v1/maintenance/status", (route) =>
      route.fulfill({
        json: {
          maintenance: true,
          migration: false,
          paused: true,
          running_jobs: 0,
        },
      }),
    );
    await page.route("**/api/v1/upgrade-repairs/preview", (route) =>
      route.fulfill({ json: preview }),
    );
    await page.route("**/api/v1/upgrade-repairs/apply", (route) => {
      recorded = [
        {
          id: "outcome-1",
          created_at: "2026-11-04T20:00:00Z",
          created_by: null,
          target_sha256: preview.target_sha256,
          result: updated,
        },
      ];
      return route.fulfill({ json: { ...preview, results: [updated] } });
    });
    await page.goto(routePath);
    await expect(
      page.getByRole("heading", { name: "Upgrade reports", exact: true }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await expect(
      page.getByRole("heading", { name: "Customer support" }),
    ).toBeVisible();
    await page.runA11yScan("upgrade-reports-populated");
    const selection = page.getByRole("checkbox", {
      name: "Select Customer support for preview",
    });
    await selection.focus();
    await page.keyboard.press("Space");
    await expect(selection).toBeChecked();
    await page.keyboard.press("Tab");
    await expect(selection).not.toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(selection).toBeFocused();
    await page
      .getByText("Usage, deployments, and findings", { exact: true })
      .click();
    await expect(
      page.getByText(/does not prove that the flow never ran/),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Preview selected updates" })
      .click();
    const apply = page.getByRole("button", { name: "Apply 1 reviewed update" });
    await expect(apply).toBeDisabled();
    await page.runA11yScan("upgrade-reports-preview");
    await page.screenshot({
      path: test.info().outputPath("upgrade-report-preview.png"),
      fullPage: true,
    });
    await page
      .getByRole("checkbox", { name: /I reviewed this 1 update/ })
      .check();
    await expect(apply).toBeEnabled();
    await apply.click();
    await expect(
      page.getByRole("list", { name: "Update results" }).getByRole("link", {
        name: "Review protected recovery version for Customer support",
      }),
    ).toHaveAttribute(
      "href",
      `/flow/${updated.flow_id}?version=${updated.recovery_version_id}`,
    );
    await page.runA11yScan("upgrade-reports-results");
    await page.getByText("Saved update outcomes", { exact: true }).click();
    await expect(page.getByText("Showing 1 of 1 saved outcomes")).toBeVisible();
    await page.runA11yScan("upgrade-reports-outcomes");
    await page.setViewportSize({ width: 320, height: 740 });
    await page.runA11yScan("upgrade-reports-mobile");
  },
);

test(
  "checks empty history and file size validation",
  { tag: ["@release", "@database"] },
  async ({ page }) => {
    await page.route("**/api/v1/upgrade-reports**", (route) =>
      route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 20 } }),
    );
    await page.goto(routePath);
    await expect(
      page.getByRole("heading", { name: "Upgrade reports", exact: true }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
    await expect(
      page.getByText("No upgrade reports have been imported."),
    ).toBeVisible();
    await page.runA11yScan("upgrade-reports-empty");
    await page.getByLabel("Checker report file").setInputFiles({
      name: "large.json",
      mimeType: "application/json",
      buffer: Buffer.alloc(20 * 1024 * 1024 + 1, " "),
    });
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "The report could not be imported." }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Import report", exact: true }),
    ).toBeDisabled();
    await page.runA11yScan("upgrade-reports-import-error");
  },
);

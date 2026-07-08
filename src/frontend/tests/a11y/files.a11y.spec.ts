import type { Route } from "@playwright/test";
import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";

type FileRow = {
  id: string;
  user_id: string;
  provider: string | null;
  name: string;
  path: string;
  type: string;
  size: number;
  created_at: string;
  updated_at: string;
  // Client-side upload state injected into the grid rowData: a number 0..1 while
  // uploading, -1 when the upload failed.
  progress?: number;
};

const populatedFiles: FileRow[] = [
  {
    id: "a11y-file-1",
    user_id: "a11y-user",
    provider: null,
    name: "quarterly-report",
    path: "quarterly-report.pdf",
    type: "pdf",
    size: 428032,
    created_at: "2026-06-01T10:00:00",
    updated_at: "2026-06-15T13:30:00",
  },
  {
    id: "a11y-file-2",
    user_id: "a11y-user",
    provider: null,
    name: "customer-import",
    path: "customer-import.csv",
    type: "csv",
    size: 8192,
    created_at: "2026-06-02T10:00:00",
    updated_at: "2026-06-16T13:30:00",
  },
];

async function disableAnimations(page: LangflowPage) {
  await page.addStyleTag({
    content: `
      *,
      *::before,
      *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        scroll-behavior: auto !important;
      }
    `,
  });
}

async function mockFiles(page: LangflowPage, files: FileRow[]) {
  await page.route("**/api/v2/files", async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: files });
      return;
    }
    await route.continue();
  });
}

async function openFilesRoute(page: LangflowPage, files = populatedFiles) {
  await mockFiles(page, files);
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/assets/files");
  await disableAnimations(page);
  await expect(page).toHaveURL(/\/assets\/files\/?$/, {
    timeout: TIMEOUTS.standard,
  });
  await page
    .waitForLoadState("networkidle", { timeout: TIMEOUTS.medium })
    .catch(() => {});
}

async function openActionsMenu(page: LangflowPage) {
  await page
    .getByRole("button", { name: /File actions/ })
    .first()
    .click();
  await expect(page.getByRole("menu")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
}

test.describe("files route accessibility", () => {
  test(
    "scans populated files table",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page);
      await expect(page.getByText("quarterly-report")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect(page.getByTestId("search-store-input")).toBeVisible();

      await page.runA11yScan("assets-files-data-rich");
    },
  );

  test(
    "scans empty files state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page, []);
      await expect(page.getByText("No files")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("assets-files-empty");
    },
  );

  test(
    "scans populated files table on mobile width",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openFilesRoute(page);
      await expect(page.getByText("quarterly-report")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("assets-files-mobile-data-rich");
    },
  );

  test(
    "scans upload-in-progress state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page, [{ ...populatedFiles[0], progress: 0.5 }]);
      await expect(page.getByText("50%")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("assets-files-uploading");
    },
  );

  test(
    "scans upload-failed (error) state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page, [{ ...populatedFiles[0], progress: -1 }]);
      await expect(page.getByText(/Upload failed/i)).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      // The retry affordance must be a real, keyboard-operable control.
      await expect(
        page.getByRole("button", { name: /try again/i }),
      ).toBeVisible();

      await page.runA11yScan("assets-files-error");
    },
  );

  test(
    "scans selected files table state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page);
      const firstRow = page
        .locator(".ag-center-cols-container .ag-row")
        .first();
      await firstRow.hover();
      await firstRow
        .locator("input.ag-checkbox-input")
        .first()
        .click({ force: true });
      await expect(firstRow).toHaveAttribute("aria-selected", "true");
      await expect(page.getByTestId("bulk-delete-btn")).toBeVisible();

      await page.runA11yScan("assets-files-row-selected");
    },
  );

  test(
    "bulk delete control is a single tab stop (no nested trigger button)",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page);
      const firstRow = page
        .locator(".ag-center-cols-container .ag-row")
        .first();
      await firstRow.hover();
      await firstRow
        .locator("input.ag-checkbox-input")
        .first()
        .click({ force: true });

      const deleteBtn = page.getByTestId("bulk-delete-btn");
      await expect(deleteBtn).toBeVisible();
      // Regression: the dialog trigger must merge onto the button (asChild), not
      // wrap it in a second <button>, which would create two consecutive tab
      // stops (WCAG 2.4.3 focus order).
      const wrappedInButton = await deleteBtn.evaluate(
        (el) => el.parentElement?.closest("button") !== null,
      );
      expect(wrappedInButton).toBe(false);
    },
  );

  // The open row-actions dropdown surfaces a KNOWN, app-wide limitation: Radix
  // portals menu content to <body>, tripping IBM `aria_content_in_landmark`
  // (menus, unlike aria-modal dialogs, are not landmark-exempt), and <main> is
  // overflow-hidden so the menu cannot simply portal into it. The violation is
  // tracked via an IBM baseline (tests/a11y/baselines/
  // chromium__assets-files-actions-menu.json) so this scan passes while the debt
  // is recorded. Delete that baseline file to resurface the violation.
  test(
    "scans open row actions menu",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page);
      await openActionsMenu(page);
      await expect(page.getByTestId("btn-rename-file")).toBeVisible();
      await expect(page.getByTestId("btn-delete-file")).toBeVisible();

      await page.runA11yScan("assets-files-actions-menu");
    },
  );

  test(
    "scans delete confirmation modal",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page);
      await openActionsMenu(page);
      await page.getByTestId("btn-delete-file").click();
      await expect(page.getByRole("dialog")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("assets-files-delete-modal");
    },
  );

  test(
    "scans inline rename editing state",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page);
      await openActionsMenu(page);
      await page.getByTestId("btn-rename-file").click();
      await expect(page.locator(".ag-cell-inline-editing")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      await page.runA11yScan("assets-files-rename-editing");
    },
  );

  test(
    "rename moves focus into the cell editor input",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page);
      await openActionsMenu(page);
      // Activate rename from the menu (Radix restores focus to the trigger on
      // close; focus must still end up in the editor input — WCAG 2.4.3).
      await page.getByTestId("btn-rename-file").click();
      await expect(page.locator(".ag-cell-inline-editing")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });
      await expect
        .poll(async () =>
          page.evaluate(() => {
            const el = document.activeElement as HTMLElement | null;
            return (
              el?.tagName === "INPUT" && !!el.closest(".ag-cell-inline-editing")
            );
          }),
        )
        .toBe(true);
    },
  );

  test(
    "opens row actions menu with the keyboard and restores focus on close",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page);
      await disableAnimations(page);

      // Give AG Grid cell focus on a non-editable cell, then arrow across to the
      // actions cell (name -> path -> size -> updated_at -> actions).
      const firstRow = page
        .locator(".ag-center-cols-container .ag-row")
        .first();
      await firstRow.locator('[role="gridcell"][col-id="path"]').click();
      await page.keyboard.press("ArrowRight");
      await page.keyboard.press("ArrowRight");
      await page.keyboard.press("ArrowRight");
      await expect
        .poll(async () =>
          page.evaluate(() => document.activeElement?.getAttribute("col-id")),
        )
        .toBe("actions");

      // Enter on the actions cell opens the dropdown (WCAG 2.1.1).
      await page.keyboard.press("Enter");
      await expect(page.getByRole("menu")).toBeVisible({
        timeout: TIMEOUTS.standard,
      });

      // Escape closes and returns focus to the (real button) trigger.
      await page.keyboard.press("Escape");
      await expect(page.getByRole("menu")).toBeHidden({
        timeout: TIMEOUTS.standard,
      });
      const focusedName = await page.evaluate(
        () => document.activeElement?.getAttribute("aria-label") ?? "",
      );
      expect(focusedName).toMatch(/File actions/);
    },
  );

  test(
    "shows a visible focus ring on grid cells for keyboard but not mouse",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openFilesRoute(page);

      // WCAG 2.4.7: keyboard navigation must show a visible focus ring. The
      // borderless table hides AG Grid's default cell outline, so this guards the
      // :focus-visible restore.
      await page.getByTestId("search-store-input").focus();
      for (let i = 0; i < 12; i++) {
        const onCell = await page.evaluate(() =>
          document.activeElement?.classList.contains("ag-cell"),
        );
        if (onCell) break;
        await page.keyboard.press("Tab");
      }
      const keyboardFocus = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el?.classList.contains("ag-cell")) return null;
        const cs = getComputedStyle(el);
        return {
          style: cs.outlineStyle,
          hasWidth: parseFloat(cs.outlineWidth) > 0,
        };
      });
      expect(keyboardFocus).toEqual({ style: "solid", hasWidth: true });

      // A mouse click resolves to :focus (not :focus-visible), so no ring shows.
      await page
        .locator(
          '.ag-center-cols-container .ag-row [role="gridcell"][col-id="size"]',
        )
        .first()
        .click();
      const mouseOutlineStyle = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        return el ? getComputedStyle(el).outlineStyle : null;
      });
      expect(mouseOutlineStyle).toBe("none");
    },
  );
});

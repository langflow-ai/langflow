import type { Route, TestInfo } from "@playwright/test";
import { expect, type LangflowPage, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TIMEOUTS } from "../../utils/constants/timeouts";

/**
 * WCAG 2.4.7 Focus Visible regression tests.
 *
 * Each test moves focus to an interactive element and confirms it has a
 * *perceivable* focus indicator: an outline with a non-transparent colour, a
 * box-shadow whose strongest layer is not near-transparent (Tailwind ring
 * classes render as box-shadow behind transparent placeholder layers), or
 * AG-Grid's own `::after` header-cell border.
 */

type FocusIndicator = {
  tag: string;
  testId: string;
  className: string;
  focusVisible: boolean;
  outlineWidth: string;
  outlineStyle: string;
  outlineColor: string;
  boxShadow: string;
  afterBorderWidth: string;
  afterBorderStyle: string;
};

async function getFocusIndicator(
  page: LangflowPage,
): Promise<FocusIndicator | null> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return null;
    const style = window.getComputedStyle(el);
    const after = window.getComputedStyle(el, "::after");
    return {
      tag: el.tagName.toLowerCase(),
      testId: el.getAttribute("data-testid") ?? "",
      className: el.className?.toString() ?? "",
      focusVisible: el.matches(":focus-visible"),
      outlineWidth: style.outlineWidth,
      outlineStyle: style.outlineStyle,
      outlineColor: style.outlineColor,
      boxShadow: style.boxShadow,
      afterBorderWidth: after.borderTopWidth,
      afterBorderStyle: after.borderTopStyle,
    };
  });
}

/**
 * Strongest alpha among the colours in a computed colour / box-shadow string.
 * `rgb()` counts as opaque; a value with no rgb()/rgba() colour (e.g. `none`,
 * or a modern colour syntax) is treated as opaque unless it is `none`/empty.
 */
function maxColorAlpha(value: string): number {
  if (!value || value === "none") return 0;
  const alphas = [...value.matchAll(/rgba?\(([^)]+)\)/g)].map(([, inner]) => {
    const parts = inner.split(",").map((part) => Number.parseFloat(part));
    return parts.length === 4 ? parts[3] : 1;
  });
  return alphas.length ? Math.max(...alphas) : 1;
}

function hasPerceivableFocusIndicator(indicator: FocusIndicator) {
  const hasOutline =
    indicator.outlineStyle !== "none" &&
    Number.parseFloat(indicator.outlineWidth) > 0 &&
    maxColorAlpha(indicator.outlineColor) > 0;
  // A 5%-alpha shadow (the old .ag-cell-focus style) is not a visible indicator.
  const hasRing = maxColorAlpha(indicator.boxShadow) >= 0.5;
  const hasAfterBorder =
    indicator.afterBorderStyle !== "none" &&
    Number.parseFloat(indicator.afterBorderWidth) > 0;
  return hasOutline || hasRing || hasAfterBorder;
}

function formatIndicator(indicator: FocusIndicator) {
  const id = indicator.testId ? ` data-testid="${indicator.testId}"` : "";
  return `<${indicator.tag}${id} class="${indicator.className}"> focus-visible=${indicator.focusVisible} outline=${indicator.outlineWidth} ${indicator.outlineStyle} ${indicator.outlineColor} box-shadow=${indicator.boxShadow} ::after-border=${indicator.afterBorderWidth} ${indicator.afterBorderStyle}`;
}

/** Asserts the active element has a perceivable indicator; attaches a screenshot for visual review. */
async function expectFocusIndicator(
  page: LangflowPage,
  label: string,
  testInfo: TestInfo,
) {
  const indicator = await getFocusIndicator(page);
  await testInfo.attach(label, {
    body: await page.screenshot(),
    contentType: "image/png",
  });
  if (!indicator) throw new Error(`${label}: nothing is focused`);
  expect(
    hasPerceivableFocusIndicator(indicator),
    `${label}: no perceivable focus indicator — ${formatIndicator(indicator)}`,
  ).toBe(true);
}

test(
  "login page — every interactive element shows a visible focus indicator when tabbed to",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    // Tab through up to 20 focusable elements
    const violations: string[] = [];
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press("Tab");
      const indicator = await getFocusIndicator(page);
      if (!indicator) continue;

      // Skip elements that are intentionally not interactive (body, html)
      if (["body", "html"].includes(indicator.tag)) continue;

      if (!hasPerceivableFocusIndicator(indicator)) {
        violations.push(formatIndicator(indicator));
      }
    }

    expect(
      violations,
      `Focus visible violations found:\n${violations.join("\n")}`,
    ).toHaveLength(0);
  },
);

test(
  "canvas controls — add note, zoom, and fit view buttons show focus ring when tabbed to",
  { tag: ["@release", "@workspace"] },
  async ({ page }, testInfo) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const controlTestIds = [
      "canvas-add-note-button",
      "zoom_in",
      "zoom_out",
      "fit_view",
    ];

    for (const testId of controlTestIds) {
      const button = page.getByTestId(testId);
      if (!(await button.isVisible())) continue;

      await button.focus();
      await expectFocusIndicator(page, `canvas-control-${testId}`, testInfo);
    }
  },
);

test(
  "dropdown trigger shows focus ring on keyboard focus",
  { tag: ["@release", "@workspace"] },
  async ({ page }, testInfo) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Find any visible button-role element and tab to it
    const triggers = page.locator('[role="combobox"]:visible').first();
    if (!(await triggers.isVisible())) return;

    await triggers.focus();
    await expectFocusIndicator(page, "dropdown-trigger", testInfo);
  },
);

// ---------------------------------------------------------------------------
// AG-Grid surfaces (LE-2233)
//
// The generic grid theme (style/classes.css) used to replace the focus outline
// on `.ag-cell-focus` with a 1px #94a3b8 border and a 5%-alpha shadow, which is
// below the 3:1 non-text contrast floor and effectively invisible on a hovered
// row. `.ag-no-border` / `.ag-knowledge-table` grids already carried a
// `:focus-visible` ring (LE-1561, covered by tests/a11y/files.a11y.spec.ts);
// the generic grid, `.ag-tool-mode`, `.no-border` and `.cell-disable-edit`
// cells did not.
//
// This test moves focus with the keyboard (click, then arrow key) so
// `:focus-visible` matches the way it does for a real keyboard user.
// ---------------------------------------------------------------------------

/**
 * Click a first-row cell (mouse focus), then arrow to the next one so focus is
 * keyboard-driven and `:focus-visible` matches. `colId` must be a column whose
 * cell click does not open a dialog.
 */
async function keyboardFocusNextCell(page: LangflowPage, colId: string) {
  const cell = page.locator(`.ag-cell[col-id="${colId}"]`).first();
  await cell.waitFor({ timeout: TIMEOUTS.standard });
  await cell.click();
  await page.keyboard.press("ArrowRight");
}

test(
  "settings API keys grid — keyboard focus on a cell and a header cell shows a perceivable indicator",
  { tag: ["@release", "@workspace"] },
  async ({ page }, testInfo) => {
    await page.route("**/api/v1/api_key/", async (route: Route) => {
      if (route.request().method() !== "GET") return route.continue();
      await route.fulfill({
        json: {
          total_count: 2,
          user_id: "a11y-user",
          api_keys: [
            {
              id: "a11y-key-1",
              name: "ci-key",
              created_at: "2026-06-01T10:00:00",
              last_used_at: null,
              total_uses: 3,
              is_active: true,
              api_key: "sk-****abcd", // pragma: allowlist secret
            },
            {
              id: "a11y-key-2",
              name: "local-key",
              created_at: "2026-06-02T10:00:00",
              last_used_at: "2026-06-10T10:00:00",
              total_uses: 0,
              is_active: true,
              api_key: "sk-****efgh", // pragma: allowlist secret
            },
          ],
        },
      });
    });
    await awaitBootstrapTest(page, { skipModal: true });
    await page.goto("/settings/api-keys");

    // "Created" — the Name/Key cells open dialogs on click.
    await keyboardFocusNextCell(page, "created_at");
    await expectFocusIndicator(page, "api-keys-cell", testInfo);

    // A mouse click resolves to :focus, not :focus-visible — the grid keeps its
    // quiet border look and must not grow the keyboard ring.
    await page.locator('.ag-cell[col-id="created_at"]').first().click();
    const mouse = await getFocusIndicator(page);
    expect(mouse?.focusVisible).toBe(false);
    expect(mouse?.outlineStyle).toBe("none");

    // Arrow up out of the rows lands on the column header.
    await page.keyboard.press("ArrowUp");
    await page.keyboard.press("ArrowUp");
    await expect(page.locator(".ag-header-cell:focus")).toHaveCount(1);
    await expectFocusIndicator(page, "api-keys-header-cell", testInfo);
  },
);

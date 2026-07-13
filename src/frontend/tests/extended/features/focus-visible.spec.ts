import { expect, test } from "../../fixtures";

/**
 * WCAG 2.4.7 Focus Visible regression tests.
 *
 * Each test tabs to an interactive element and confirms it has a visible
 * focus indicator — either a non-zero outline or a non-"none" box-shadow
 * (Tailwind ring classes render as box-shadow).
 */

async function getFocusStyle(page) {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return null;
    const style = window.getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(),
      testId: el.getAttribute("data-testid") ?? "",
      outlineWidth: style.outlineWidth,
      outlineStyle: style.outlineStyle,
      boxShadow: style.boxShadow,
    };
  });
}

function hasFocusIndicator(focusStyle: {
  outlineWidth: string;
  outlineStyle: string;
  boxShadow: string;
}) {
  const hasOutline =
    focusStyle.outlineStyle !== "none" &&
    focusStyle.outlineWidth !== "0px" &&
    focusStyle.outlineWidth !== "";
  const hasRing =
    focusStyle.boxShadow !== "none" && focusStyle.boxShadow !== "";
  return hasOutline || hasRing;
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
      const focusStyle = await getFocusStyle(page);
      if (!focusStyle) continue;

      // Skip elements that are intentionally not interactive (body, html)
      if (["body", "html"].includes(focusStyle.tag)) continue;

      if (!hasFocusIndicator(focusStyle)) {
        violations.push(
          `Element <${focusStyle.tag}> data-testid="${focusStyle.testId}" has no visible focus indicator (outline: ${focusStyle.outlineWidth} ${focusStyle.outlineStyle}, box-shadow: ${focusStyle.boxShadow})`,
        );
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
  async ({ page }) => {
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
      const focusStyle = await getFocusStyle(page);
      if (!focusStyle) continue;

      expect(
        hasFocusIndicator(focusStyle),
        `Canvas control [data-testid="${testId}"] has no visible focus indicator`,
      ).toBe(true);
    }
  },
);

test(
  "dropdown trigger shows focus ring on keyboard focus",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Find any visible button-role element and tab to it
    const triggers = page.locator('[role="combobox"]:visible').first();
    if (!(await triggers.isVisible())) return;

    await triggers.focus();
    const focusStyle = await getFocusStyle(page);

    expect(
      focusStyle && hasFocusIndicator(focusStyle),
      `Dropdown trigger has no visible focus indicator (outline: ${focusStyle?.outlineWidth}, box-shadow: ${focusStyle?.boxShadow})`,
    ).toBe(true);
  },
);

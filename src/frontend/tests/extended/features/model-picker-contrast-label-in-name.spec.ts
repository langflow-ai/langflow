import type { Locator, Page, Route } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { openFlowCard } from "../../utils/flow/open-flow-card";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";

/**
 * LE-2235 — WCAG 1.4.3 Contrast (Minimum) + 2.5.3 Label in Name.
 *
 * 1.4.3: the model-picker provider group headings and the footer action
 *        buttons must measure >= 4.5:1 against the popover background, in
 *        both themes.
 * 2.5.3: every component-sidebar drag item's accessible name must contain
 *        its visible text (display name + Beta / Legacy badge).
 *
 * Contrast is computed here from live computed styles (WCAG relative
 * luminance) rather than delegated to the IBM checker so the assertion
 * runs without RUN_A11Y and reports the actual ratio on failure.
 */

const WCAG_AA_TEXT = 4.5;

const mockProviders = [
  {
    provider: "OpenAI",
    is_enabled: true,
    is_configured: true,
    models: [
      { model_name: "gpt-4", metadata: { model_type: "llm" } },
      { model_name: "gpt-3.5-turbo", metadata: { model_type: "llm" } },
    ],
  },
  {
    provider: "Anthropic",
    is_enabled: true,
    is_configured: true,
    models: [{ model_name: "claude-3-opus", metadata: { model_type: "llm" } }],
  },
];

async function mockModelCatalog(page: Page) {
  await page.route(/\/api\/v1\/models(\?.*)?$/, async (route: Route) => {
    await route.fulfill({ json: mockProviders });
  });
  await page.route(
    /\/api\/v1\/models\/enabled_models$/,
    async (route: Route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({ json: { disabled_models: [] } });
        return;
      }
      await route.fulfill({
        json: {
          enabled_models: {
            OpenAI: { "gpt-4": true, "gpt-3.5-turbo": true },
            Anthropic: { "claude-3-opus": true },
          },
        },
      });
    },
  );
}

async function openBlankFlow(page: Page) {
  await awaitBootstrapTest(page);
  await page.getByTestId("blank-flow").click();
  await expect(page.getByTestId("modal-title")).toBeHidden({
    timeout: TIMEOUTS.standard,
  });
  const sidebarSearchInput = page.getByTestId("sidebar-search-input");
  if (!(await sidebarSearchInput.isVisible())) {
    const createdFlow = page
      .getByTestId("flow-name-div")
      .filter({ hasText: "New Flow" })
      .first();
    const visible = await createdFlow
      .waitFor({ state: "visible", timeout: TIMEOUTS.short })
      .then(() => true)
      .catch(() => false);
    if (visible) await openFlowCard(page, "New Flow");
  }
  await expect(sidebarSearchInput).toBeVisible({ timeout: TIMEOUTS.standard });
}

async function addLanguageModelNode(page: Page) {
  await page.getByTestId("sidebar-search-input").click();
  await page
    .getByTestId("sidebar-search-input")
    .fill(TEXTS.componentLanguageModel);
  await page.waitForTimeout(500);
  await page.getByTestId("add-component-button-language-model").click();
  const node = page.locator(".react-flow__node").first();
  await expect(node).toBeVisible({ timeout: TIMEOUTS.short });
  await page.getByTestId("sidebar-search-input").fill("");
  return node;
}

async function setTheme(page: Page, dark: boolean) {
  // useTheme (customization/hooks/use-custom-theme.ts) reads
  // `themePreference` on mount and toggles the `dark` class on <body>.
  await page.evaluate(
    (theme) => {
      window.localStorage.setItem("themePreference", theme);
    },
    dark ? "dark" : "light",
  );
  await page.reload();
  await expect(page.getByTestId("sidebar-search-input")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  await expect(page.locator("body")).toHaveClass(
    dark ? /dark/ : /^((?!dark).)*$/,
  );
}

/** Wait for finite CSS animations (Radix popover fade/zoom-in) to finish. */
async function settleAnimations(page: Page) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  );
}

/**
 * Walk up from the element until an ancestor paints an opaque background,
 * then return WCAG contrast between the element's text color and it.
 */
async function measureContrast(el: Locator) {
  return el.evaluate((node) => {
    const parse = (c: string) => {
      const m = c.match(/rgba?\(([^)]+)\)/);
      if (!m) return null;
      const [r, g, b, a = "1"] = m[1].split(/[\s,/]+/).map((v) => v.trim());
      return { r: +r, g: +g, b: +b, a: +a };
    };
    const lum = ({ r, g, b }: { r: number; g: number; b: number }) => {
      const f = (v: number) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    const fg = parse(getComputedStyle(node).color);
    let cur: HTMLElement | null = node as HTMLElement;
    let bg: ReturnType<typeof parse> = null;
    while (cur) {
      const c = parse(getComputedStyle(cur).backgroundColor);
      if (c && c.a === 1) {
        bg = c;
        break;
      }
      cur = cur.parentElement;
    }
    if (!fg || !bg) return null;
    const [l1, l2] = [lum(fg), lum(bg)].sort((a, b) => b - a);
    return {
      ratio: Math.round(((l1 + 0.05) / (l2 + 0.05)) * 100) / 100,
      fg: getComputedStyle(node).color,
      bg: `rgb(${bg.r}, ${bg.g}, ${bg.b})`,
    };
  });
}

test.describe("Model picker contrast (WCAG 1.4.3) — LE-2235", () => {
  for (const dark of [false, true]) {
    test(
      `provider group headings and footer buttons measure >= 4.5:1 (${dark ? "dark" : "light"} theme)`,
      { tag: ["@release", "@components", "@workspace"] },
      async ({ page }, testInfo) => {
        await mockModelCatalog(page);
        await openBlankFlow(page);
        await setTheme(page, dark);
        const node = await addLanguageModelNode(page);

        const combobox = node.getByRole("combobox", {
          name: TEXTS.componentLanguageModel,
        });
        await combobox.click();
        const listbox = page.getByRole("listbox");
        await expect(listbox).toBeVisible({ timeout: TIMEOUTS.medium });
        // The popover fades in; measure and screenshot the settled state.
        await settleAnimations(page);

        const headings = listbox.locator("[cmdk-group-heading]");
        await expect(headings.first()).toBeVisible();
        const footerButtons = page
          .getByTestId("refresh-model-list")
          .or(page.getByTestId("manage-model-providers"));
        await expect(footerButtons.first()).toBeVisible();

        await page.screenshot({
          path: testInfo.outputPath(
            `model-picker-${dark ? "dark" : "light"}.png`,
          ),
        });

        const failures: string[] = [];
        const measured: string[] = [];
        for (const [name, locator] of [
          ["group heading", headings],
          ["footer button", footerButtons],
        ] as const) {
          const count = await locator.count();
          for (let i = 0; i < count; i++) {
            const item = locator.nth(i);
            // Footer buttons carry the muted color on the inner text wrapper.
            const target =
              name === "footer button" ? item.locator("div").first() : item;
            const text = (await item.innerText()).trim();
            const result = await measureContrast(target);
            measured.push(
              `${name} "${text}": ${result?.ratio ?? "?"}:1 (${result?.fg} on ${result?.bg})`,
            );
            if (!result || result.ratio < WCAG_AA_TEXT) {
              failures.push(
                `${name} "${text}": ${result?.ratio ?? "?"}:1 (${result?.fg} on ${result?.bg})`,
              );
            }
          }
        }
        // Keep the measured ratios in the report as evidence for row 1.4.3.
        testInfo.annotations.push({
          type: `contrast-${dark ? "dark" : "light"}`,
          description: measured.join(" | "),
        });
        expect(failures, failures.join("\n")).toEqual([]);
      },
    );
  }
});

test.describe("Sidebar label in name (WCAG 2.5.3) — LE-2235", () => {
  test(
    "every sidebar drag item's accessible name contains its visible text",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }, testInfo) => {
      await openBlankFlow(page);
      // The sidebar can remount while the flow finishes loading, which
      // resets its open-category state — expand only once it is settled.
      await waitForFlowEditorReady(page);

      // Expand every category so badged (Beta / Legacy) items render.
      const triggers = page.locator('[data-testid^="disclosure-"]');
      const triggerCount = await triggers.count();
      for (let i = 0; i < triggerCount; i++) {
        const trigger = triggers.nth(i);
        if ((await trigger.getAttribute("aria-expanded")) !== "true") {
          await trigger.click();
          await expect(trigger).toHaveAttribute("aria-expanded", "true");
        }
      }

      const items = page.locator(
        '[data-testid$="_draggable"] [role="button"][aria-label]',
      );
      await expect
        .poll(() => items.count(), { timeout: TIMEOUTS.medium })
        .toBeGreaterThan(0);

      // Same normalisation IBM's label_name_visible applies: text nodes
      // joined by spaces, non-alphanumerics collapsed to spaces, lowercase,
      // and the visible text must appear in the name as whole words.
      const mismatches = await items.evaluateAll((nodes) => {
        const normalize = (s: string) =>
          s
            .replace(/[^a-zA-Z0-9]/g, " ")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
        const visibleText = (el: Element) => {
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
          const parts: string[] = [];
          for (let t = walker.nextNode(); t; t = walker.nextNode()) {
            const v = t.nodeValue?.trim();
            if (v) parts.push(v);
          }
          return parts.join(" ");
        };
        return nodes
          .map((n) => ({
            name: n.getAttribute("aria-label") ?? "",
            visible: visibleText(n),
          }))
          .filter(({ name, visible }) => {
            const hay = normalize(name);
            const needle = normalize(visible);
            return !new RegExp(`(^|\\s)${needle}(\\s|$)`).test(hay);
          });
      });

      // Evidence screenshot: the first badged item with its accessible name
      // painted into the frame (the name is not otherwise visible).
      const badged = page
        .locator('[data-testid$="_draggable"]')
        .filter({ hasText: /Beta|Legacy/ })
        .first();
      if (await badged.isVisible()) {
        await badged.scrollIntoViewIfNeeded();
        const box = await badged.boundingBox();
        await badged.evaluate((el, b) => {
          const name =
            el.querySelector('[role="button"]')?.getAttribute("aria-label") ??
            "";
          const tag = document.createElement("div");
          tag.id = "le-2235-evidence";
          tag.textContent = `aria-label: "${name}"`;
          tag.style.cssText = `position:fixed;left:${b.x}px;top:${b.y + b.height + 2}px;z-index:9999;font:12px monospace;background:#fff3cd;color:#000;border:1px solid #000;padding:2px 4px;white-space:nowrap`;
          document.body.appendChild(tag);
        }, box!);
        await page.screenshot({
          path: testInfo.outputPath("sidebar-badged-item.png"),
          clip: {
            x: box!.x - 4,
            y: box!.y - 4,
            width: 360,
            height: box!.height + 32,
          },
        });
        await page.locator("#le-2235-evidence").evaluate((el) => el.remove());
      }

      expect(
        mismatches,
        mismatches
          .map(
            (m) => `name="${m.name}" does not contain visible "${m.visible}"`,
          )
          .join("\n"),
      ).toEqual([]);
    },
  );
});

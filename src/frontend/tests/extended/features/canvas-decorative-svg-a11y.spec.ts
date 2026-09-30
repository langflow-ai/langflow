import { expect, test } from "../../fixtures";
import { openStarterProject } from "../../utils/flow/open-starter-project";

/**
 * WCAG 1.1.1 Non-text Content regression tests for the flow canvas.
 *
 * IBM Equal Access reported `svg_graphics_labelled` once per edge plus once for
 * the dot-grid background: ReactFlow renders a bare `<svg>` wrapper around each
 * edge and a bare `<svg>` for the grid, and an unnamed `<svg>` is an unnamed
 * graphic. Both are decoration, so neither should reach assistive tech.
 *
 * The wrappers and the grid are fixed differently on purpose:
 *   - the grid is wrapped in an `aria-hidden` container — nothing inside it
 *     carries meaning;
 *   - each edge wrapper only gets `role="presentation"`, because the named,
 *     tabbable `<g role="group">` that carries the edge's accessible name lives
 *     *inside* it. `aria-hidden` there would silently erase every edge name.
 *
 * That last point is what the second test guards: it resolves each edge through
 * `getByRole` + accessible name, which is computed the way assistive tech
 * computes it, so it fails the moment an `aria-hidden` ancestor is introduced.
 */

test(
  "decorative canvas SVGs are not exposed as unnamed graphics",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");

    const edgeWrappers = page.locator(".react-flow__edges > svg");
    await expect(edgeWrappers.first()).toBeAttached();

    // Presentational, never hidden — hiding would take the edge names with it.
    const wrappers = await edgeWrappers.evaluateAll((svgs) =>
      svgs.map((svg) => ({
        role: svg.getAttribute("role"),
        ariaHidden: svg.getAttribute("aria-hidden"),
      })),
    );
    expect(wrappers.length).toBeGreaterThan(0);
    for (const wrapper of wrappers) {
      expect(wrapper.role).toBe("presentation");
      expect(wrapper.ariaHidden).toBeNull();
    }

    const backgroundHidden = await page
      .getByTestId("rf__background")
      .evaluate((svg) => svg.closest('[aria-hidden="true"]') !== null);
    expect(backgroundHidden).toBe(true);
  },
);

test(
  "every edge keeps its accessible name and tab stop",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");

    const edges = page.locator(".react-flow__edge");
    await expect(edges.first()).toBeAttached();

    const names = await edges.evaluateAll((groups) =>
      groups.map((group) => group.getAttribute("aria-label")),
    );
    expect(names.length).toBeGreaterThan(0);
    expect(names).not.toContain(null);

    for (const name of names) {
      // `getByRole` uses the computed accessible name, so an `aria-hidden`
      // ancestor anywhere above the edge makes this resolve to nothing.
      const edge = page.getByRole("button", { name: name!, exact: true });
      await expect(edge).toHaveCount(1);
      await expect(edge).toHaveAttribute("tabindex", "0");

      await edge.focus();
      await expect(edge).toBeFocused();
    }
  },
);

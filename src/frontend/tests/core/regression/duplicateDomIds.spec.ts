import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

/**
 * LE-2037 / #14096: node parameter fields derive their DOM id from the field
 * name alone, so two nodes exposing the same field render duplicate ids —
 * a WCAG 4.1.1 violation that also breaks browser autofill.
 *
 * Both a string field and a numeric one are covered: they go through different
 * renderers (`StrRenderComponent` vs `IntComponent`), each with its own id
 * path, so covering only one leaves the other free to regress.
 *
 * Flows are created through the API rather than the sidebar so the scenario is
 * exact and deterministic: two nodes of the same component, therefore an
 * identical set of visible fields. Dragging is not an option for every
 * component either — `ChatInput` is a singleton in the sidebar.
 */
const CASES = [
  { type: "ChatInput", testId: "textarea_str_input_value" },
  { type: "WikipediaAPI", testId: "int_int_k" },
];

test(
  "two nodes sharing a field name must not produce duplicate DOM ids",
  { tag: ["@release", "@components", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    const allTypes = await (await page.request.get("/api/v1/all")).json();

    for (const { type, testId } of CASES) {
      let template: unknown;
      for (const category of Object.values(allTypes) as Record<
        string,
        unknown
      >[]) {
        if (category?.[type]) template = category[type];
      }
      expect(template, `${type} missing from /api/v1/all`).toBeTruthy();

      const makeNode = (suffix: string, x: number) => ({
        id: `${type}-${suffix}`,
        type: "genericNode",
        position: { x, y: 0 },
        data: { id: `${type}-${suffix}`, type, node: template },
      });

      const created = await page.request.post("/api/v1/flows/", {
        data: {
          name: `duplicate-ids-${type}-${Date.now()}`,
          description: "LE-2037 duplicate DOM id regression",
          data: {
            nodes: [makeNode("aaaaa", 0), makeNode("bbbbb", 600)],
            edges: [],
            viewport: { x: 0, y: 0, zoom: 1 },
          },
        },
      });
      expect(created.status()).toBe(201);
      const flowId = (await created.json()).id;

      await page.goto(`/flow/${flowId}`);
      await expect(page.getByTestId("div-generic-node")).toHaveCount(2, {
        timeout: 15_000,
      });

      // Scoped to form controls: that is what the reported DevTools warning
      // ("Duplicate form field id in the same form") covers, and what breaks
      // autofill. Icon SVGs repeat their own internal ids (gradients, masks,
      // filters) whenever the same icon renders twice — a separate defect that
      // must not make this regression test fail for the wrong reason.
      const duplicates = await page.evaluate(() => {
        const counts = new Map<string, number>();
        const controls = document.querySelectorAll(
          "input[id], textarea[id], select[id]",
        );
        for (const element of Array.from(controls)) {
          counts.set(element.id, (counts.get(element.id) ?? 0) + 1);
        }
        return Array.from(counts.entries())
          .filter(([, count]) => count > 1)
          .map(([id, count]) => `${id} x${count}`)
          .sort();
      });

      expect(
        duplicates,
        `duplicate form field ids for ${type}: ${duplicates.join(", ")}`,
      ).toEqual([]);

      // Scoping happens on the DOM id only — the test ids the rest of the
      // suite selects on must keep matching both nodes.
      await expect(page.getByTestId(testId)).toHaveCount(2);
    }
  },
);

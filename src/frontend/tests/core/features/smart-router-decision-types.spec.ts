import type { Locator, Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { routeTestScopedDefaultFlowNames } from "../../utils/flow/route-test-scoped-default-flow-names";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";

// The Support Ticket Routing template ships a Smart Router in Decision Model mode with
// TypeSafe selected, so these tests need no Model Providers setup, key or network.
const TEMPLATE = "Support Ticket Routing";
const ROUTE_HANDLES = ["billing", "technical support", "sales"];
const DECISION_TYPES = { Choice: 0, Boolean: 1, Score: 2 } as const;

function smartRouter(page: Page): Locator {
  return page
    .locator(".react-flow__node")
    .filter({ has: page.getByTestId("title-Smart Router") })
    .first();
}

function outputHandle(router: Locator, name: string): Locator {
  return router.getByTestId(`handle-smartrouter-shownode-${name}-right`);
}

// Smart Router output names; the edge ID format differs between saved and newly drawn edges.
const ROUTER_OUTPUT =
  /(category_\d+_result|level_\d+_result|yes_result|no_result|default_result)/;

/** The router's outgoing edges, by the output name each one leaves from. */
async function routerEdgeOutputs(page: Page): Promise<string[]> {
  const edges = await page
    .locator(".react-flow__edge")
    .evaluateAll((elements) =>
      elements.map((edge) => ({
        id: edge.getAttribute("data-id") ?? "",
        label: edge.getAttribute("aria-label") ?? "",
      })),
    );
  return edges
    .filter((edge) => edge.label.startsWith("Edge from Smart Router "))
    .map((edge) => edge.id.match(ROUTER_OUTPUT)?.[1] ?? edge.id)
    .sort();
}

async function chooseDecisionType(
  page: Page,
  type: keyof typeof DECISION_TYPES,
) {
  const router = smartRouter(page);
  await router.getByTestId("value-dropdown-dropdown_str_decision_kind").click();
  await page
    .getByTestId(`dropdown-option-${DECISION_TYPES[type]}-container`)
    .click();
  await expect(
    router.getByTestId("value-dropdown-dropdown_str_decision_kind"),
  ).toHaveText(type);
}

/**
 * The autosave that carries ``text``, armed before the edit that triggers it. Autosave is
 * debounced, so matching on content keeps an earlier, unrelated save from satisfying it.
 */
function savedWith(page: Page, text: string) {
  return page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      /\/api\/v1\/flows\/[^/]+$/.test(new URL(response.url()).pathname) &&
      response.ok() &&
      (response.request().postData() ?? "").includes(text),
    { timeout: 30000 },
  );
}

async function reloadFlow(page: Page, saved: Promise<unknown>) {
  await saved;
  await page.reload();
  await waitForFlowEditorReady(page);
  await expect(smartRouter(page)).toBeVisible();
}

test.describe("Smart Router decision types", () => {
  test.beforeEach(async ({ page }, testInfo) => {
    // Parallel workers creating the placeholder and this template would otherwise race for one "(n)" name.
    await routeTestScopedDefaultFlowNames(
      page,
      testInfo,
      "smart-router-decision",
      /^(?:New Flow|Support Ticket Routing)(?: \(\d+\))?$/,
    );
    await openStarterProject(page, TEMPLATE);
    await expect(smartRouter(page)).toBeVisible();
    await adjustScreenView(page);
  });

  test(
    "Boolean replaces the routes with Yes and No and keeps Else connected",
    { tag: ["@release", "@components"] },
    async ({ page }) => {
      const router = smartRouter(page);
      expect(await routerEdgeOutputs(page)).toEqual([
        "category_1_result",
        "category_2_result",
        "category_3_result",
        "default_result",
      ]);

      await chooseDecisionType(page, "Boolean");

      for (const name of ["yes", "no", "else"]) {
        await expect(outputHandle(router, name)).toBeVisible();
      }
      for (const name of ROUTE_HANDLES) {
        await expect(outputHandle(router, name)).toHaveCount(0);
      }
      for (const title of [
        "what yes means (optional)",
        "what no means (optional)",
        "yes message (optional)",
        "no message (optional)",
        "minimum probability",
      ]) {
        await expect(router.getByTestId(`title-${title}`)).toBeVisible();
      }
      await expect(router.getByTestId("div-table_routes")).toHaveCount(0);
      // The route outputs are gone, so their connections are removed; Else keeps its own.
      await expect
        .poll(() => routerEdgeOutputs(page))
        .toEqual(["default_result"]);
      // The template's own question is kept: only a stock question changes with the type.
      await expect(
        router.getByTestId("textarea_str_decision_question"),
      ).toHaveValue("Which team should handle this customer message?");

      // Connect Yes to a Chat Output, as a user rewiring the flow would.
      const saved = savedWith(page, "œyes_resultœ");
      await outputHandle(router, "yes").dragTo(
        page.getByTestId("handle-chatoutput-shownode-inputs-left").first(),
      );
      await expect
        .poll(() => routerEdgeOutputs(page))
        .toEqual(["default_result", "yes_result"]);

      await reloadFlow(page, saved);

      const reloaded = smartRouter(page);
      await expect(
        reloaded.getByTestId("value-dropdown-dropdown_str_decision_kind"),
      ).toHaveText("Boolean");
      await expect(outputHandle(reloaded, "yes")).toBeVisible();
      await expect
        .poll(() => routerEdgeOutputs(page))
        .toEqual(["default_result", "yes_result"]);
    },
  );

  test(
    "Score shows ordered levels without a minimum probability",
    { tag: ["@release", "@components"] },
    async ({ page }) => {
      const router = smartRouter(page);
      const saved = savedWith(page, "level_3_result");

      await chooseDecisionType(page, "Score");

      await expect(router.getByTestId("div-table_score_levels")).toBeVisible();
      await expect(router.getByTestId("div-table_routes")).toHaveCount(0);
      for (const name of ["low", "medium", "high", "else"]) {
        await expect(outputHandle(router, name)).toBeVisible();
      }
      for (const name of ROUTE_HANDLES) {
        await expect(outputHandle(router, name)).toHaveCount(0);
      }
      // Every score rounds to a level, so Score has no threshold to set.
      await expect(router.getByTestId("title-minimum probability")).toHaveCount(
        0,
      );
      await expect(
        router.getByTestId("title-what yes means (optional)"),
      ).toHaveCount(0);
      await expect
        .poll(() => routerEdgeOutputs(page))
        .toEqual(["default_result"]);

      await reloadFlow(page, saved);

      const reloaded = smartRouter(page);
      await expect(
        reloaded.getByTestId("value-dropdown-dropdown_str_decision_kind"),
      ).toHaveText("Score");
      await expect(
        reloaded.getByTestId("div-table_score_levels"),
      ).toBeVisible();
      await expect(outputHandle(reloaded, "high")).toBeVisible();

      // Back to Choice: the routes and their outputs return; their old connections do not.
      await chooseDecisionType(page, "Choice");
      for (const name of [...ROUTE_HANDLES, "else"]) {
        await expect(outputHandle(reloaded, name)).toBeVisible();
      }
      await expect(outputHandle(reloaded, "high")).toHaveCount(0);
      await expect
        .poll(() => routerEdgeOutputs(page))
        .toEqual(["default_result"]);
    },
  );

  test(
    "a Boolean decision without a provider key stops before any request",
    { tag: ["@release", "@components"] },
    async ({ page }) => {
      // With a real key configured this run would call TypeSafe and be billed.
      test.skip(
        Boolean(
          process.env.TYPESAFE_API_KEY || process.env.LANGFLOW_TYPESAFE_API_KEY,
        ),
        "A TypeSafe key is configured; this test only covers the missing-key path.",
      );
      const router = smartRouter(page);
      await chooseDecisionType(page, "Boolean");
      // The outputs refresh after the type changes; run only once the node shows the new ones.
      await expect(outputHandle(router, "yes")).toBeVisible();
      await router
        .getByTestId("textarea_str_decision_question")
        .fill("Is this about a payment?");

      const run = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname === "/api/v2/workflows",
      );
      await router.getByTestId("button_run_smart router").click();
      const body = await (await run).text();

      // The run records why it stopped, and the message says what to fix.
      expect(body).toContain('"reason":"configuration_error"');
      expect(body).toContain(
        "Add the TypeSafe API key in Model Providers, or set TYPESAFE_API_KEY.",
      );
      expect(body).toContain('"kind":"boolean"');
      await expect(
        page
          .getByText(
            "Add the TypeSafe API key in Model Providers, or set TYPESAFE_API_KEY.",
          )
          .first(),
      ).toBeVisible({ timeout: 30000 });
    },
  );
});

import type { APIClassType, APIObjectType } from "../../../src/types/api";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TIMEOUTS } from "../../utils/constants/timeouts";

/**
 * LE-2045: grouping succeeds but raises "Error while updating the Component".
 *
 * A grouped node has no `code` of its own — its fields proxy the inner
 * components — so asking the update endpoint to recompile it throws before the
 * request is even sent, and the generic error toast fires for an operation
 * that never failed.
 *
 * The refresh only fires when the model field has no options, which is why the
 * report needs a workspace with no provider configured: with a model selected
 * the field never asks for a refresh and the bug stays hidden.
 *
 * The group node is synthesized here rather than produced by dragging and
 * grouping in the UI so the failing shape is explicit and deterministic.
 * The assertion targets the notifications panel because the toast
 * auto-dismisses, while the reported message persists in the panel.
 */
test(
  "a grouped node must not raise a false update error",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    const allTypes = (await (
      await page.request.get("/api/v1/all")
    ).json()) as APIObjectType;
    let languageModel: APIClassType | undefined;
    for (const category of Object.values(allTypes)) {
      for (const def of Object.values(category)) {
        if (def?.display_name === "Language Model") languageModel = def;
      }
    }
    if (!languageModel) {
      throw new Error("Language Model not found in /api/v1/all");
    }

    const modelField = Object.entries(languageModel.template).find(
      ([, field]) => field.type === "model",
    );
    if (!modelField) {
      throw new Error("Language Model has no model field");
    }

    const innerId = "LanguageModelComponent-aaaaa";
    const groupId = "groupComponent-bbbbb";
    const proxiedName = `${modelField[0]}_${innerId}`;

    const innerNode = {
      id: innerId,
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: innerId,
        type: "LanguageModelComponent",
        node: languageModel,
      },
    };

    // The grouped template proxies the inner field and carries no `code` of its
    // own; an empty option list is what makes the field ask for a refresh.
    const groupNode = {
      id: groupId,
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: groupId,
        type: "GroupNode",
        node: {
          display_name: "Group",
          description: "",
          documentation: "",
          outputs: languageModel.outputs,
          template: {
            [proxiedName]: {
              ...modelField[1],
              options: [],
              value: "",
              proxy: { field: modelField[0], id: innerId },
            },
          },
          flow: {
            name: "Group",
            description: "",
            id: groupId,
            data: {
              nodes: [innerNode],
              edges: [],
              viewport: { x: 0, y: 0, zoom: 1 },
            },
          },
        },
      },
    };

    const created = await page.request.post("/api/v1/flows/", {
      data: {
        name: `le-2045-${Date.now()}`,
        description: "LE-2045 false grouping error",
        data: {
          nodes: [groupNode],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
      },
    });
    expect(created.status()).toBe(201);
    const flowId = (await created.json()).id;

    const flowLoadPromise = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname.endsWith(`/api/v1/flows/${flowId}`) &&
        response.request().method() === "GET" &&
        response.status() === 200,
      { timeout: TIMEOUTS.standard },
    );
    await page.goto(`/flow/${flowId}`);
    await flowLoadPromise;
    await expect(page.getByTestId("div-generic-node")).toHaveCount(1, {
      timeout: TIMEOUTS.standard,
    });
    await page.waitForTimeout(4000);

    await page.getByTestId("notification_button").click();
    const panel = page.getByTestId("notification-dropdown-content");
    await expect(panel).toBeVisible();
    await expect(
      panel.getByText("Error while updating the Component"),
    ).toHaveCount(0);
  },
);

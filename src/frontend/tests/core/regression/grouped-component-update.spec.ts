import type { APIClassType, APIObjectType } from "../../../src/types/api";
import type { GenericNodeType } from "../../../src/types/flow";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";

function componentNode(
  id: string,
  type: string,
  node: APIClassType,
): GenericNodeType {
  return {
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: { id, type, node },
  };
}

function groupedOutput(
  current: APIClassType,
  breaking: boolean,
  value: string,
) {
  const saved = structuredClone(current);
  saved.template.code.value += "\n# Historical upgrade fixture\n";
  saved.template.input_value = {
    ...saved.template.input_value,
    type: "str",
    _input_type: "MessageInput",
    value,
  };
  if (breaking) {
    saved.template.removed_input = {
      ...saved.template.input_value,
      name: "removed_input",
      value: "requires review",
    };
  }
  const child = componentNode("ChatOutput-upgrade", "ChatOutput", saved);
  const groupId = "groupComponent-upgrade";
  const exposed = "input_value_ChatOutput-upgrade";
  const group = componentNode(groupId, "GroupNode", {
    display_name: "Group",
    description: "Grouped upgrade regression",
    documentation: "",
    template: {
      [exposed]: {
        ...saved.template.input_value,
        proxy: { id: child.id, field: "input_value" },
      },
    },
    outputs: (saved.outputs ?? []).map((output) => ({
      ...output,
      name: `${child.id}_${output.name}`,
      proxy: { id: child.id, name: output.name },
    })),
    flow: {
      id: groupId,
      name: "Group",
      description: "",
      data: { nodes: [child], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
    },
  });
  group.position = { x: 500, y: 0 };
  return { group, child, exposed };
}

for (const scenario of [
  "saved-value",
  "external-edge",
  "review-dismiss",
] as const) {
  const breaking = scenario === "review-dismiss";
  const connected = scenario === "external-edge";
  const savedValue = connected ? "" : "saved group value";
  test(
    breaking
      ? "review and dismiss an outdated component inside a group"
      : `update grouped historical Chat Output and preserve ${scenario}`,
    { tag: ["@release", "@workspace", "@components"] },
    async ({ page }, testInfo) => {
      await awaitBootstrapTest(page, {
        skipModal: true,
        seedFlowIfEmpty: false,
      });
      const response = await page.request.get("/api/v1/all");
      expect(response.ok()).toBeTruthy();
      const catalog = (await response.json()) as APIObjectType;
      const definitions = Object.assign(
        {},
        ...Object.values(catalog),
      ) as Record<string, APIClassType>;
      expect(definitions.ChatInput).toBeDefined();
      expect(definitions.ChatOutput).toBeDefined();
      const { group, child, exposed } = groupedOutput(
        definitions.ChatOutput,
        breaking,
        savedValue,
      );
      const input = componentNode(
        "ChatInput-upgrade",
        "ChatInput",
        structuredClone(definitions.ChatInput),
      );
      const output = input.data.node!.outputs![0];
      const sourceHandle = {
        id: input.id,
        name: output.name,
        dataType: "ChatInput",
        output_types: output.types,
      };
      const targetHandle = {
        id: group.id,
        fieldName: exposed,
        type: "str",
        inputTypes: child.data.node!.template.input_value.input_types,
        proxy: { id: child.id, field: "input_value" },
      };
      const edge = {
        id: "group-upgrade-edge",
        source: input.id,
        target: group.id,
        sourceHandle: JSON.stringify(sourceHandle).replaceAll('"', "œ"),
        targetHandle: JSON.stringify(targetHandle).replaceAll('"', "œ"),
        data: { sourceHandle, targetHandle },
      };
      const created = await page.request.post("/api/v1/flows/", {
        data: {
          name: `grouped-upgrade-${scenario}-${Date.now()}`,
          description: "Grouped component update regression",
          data: {
            nodes: [input, group],
            edges: connected ? [edge] : [],
            viewport: { x: 0, y: 0, zoom: 1 },
          },
        },
      });
      expect(created.status()).toBe(201);
      const flowId = (await created.json()).id as string;
      await page.goto(`/flow/${flowId}`);
      await waitForFlowEditorReady(page);
      await expect(page.getByTestId("update-all-button")).toBeVisible();
      const persistedUpdate = Promise.all([
        page.waitForResponse(
          (response) =>
            response.request().method() === "PATCH" &&
            new URL(response.url()).pathname === `/api/v1/flows/${flowId}`,
        ),
        ...["/api/v1/flows/", "/api/v1/projects/"].map((pathname) =>
          page.waitForResponse(
            (response) =>
              response.request().method() === "GET" &&
              new URL(response.url()).pathname === pathname,
          ),
        ),
      ]);
      if (breaking) {
        await expect(page.getByTestId("update-all-button")).toHaveText(
          "Review All",
        );
        await page.getByTestId("update-all-button").click();
        const dialog = page.getByRole("dialog");
        await expect(
          dialog.getByText("Chat Output", { exact: true }),
        ).toBeVisible();
        await expect(
          dialog.getByText("Breaking", { exact: true }),
        ).toBeVisible();
        await page.screenshot({
          path: testInfo.outputPath("grouped-review.png"),
        });
        await page.keyboard.press("Escape");
        await page
          .getByRole("button", { name: "Dismiss", exact: true })
          .click();
      } else {
        await expect(page.getByTestId("update-all-button")).toHaveText(
          "Update All",
        );
        await page.getByTestId("update-all-button").click();
      }
      await expect(page.getByTestId("update-all-button")).toHaveCount(0);
      for (const response of await persistedUpdate) {
        expect(response.ok()).toBeTruthy();
        await response.finished();
      }
      await expect
        .poll(async () => {
          const savedResponse = await page.request.get(
            `/api/v1/flows/${flowId}`,
          );
          expect(savedResponse.ok()).toBeTruthy();
          const savedFlow = await savedResponse.json();
          const savedGroup = savedFlow.data.nodes.find(
            (node: GenericNodeType) => node.id === group.id,
          );
          const savedChild = savedGroup.data.node.flow.data.nodes[0];
          return {
            type: savedChild.data.node.template.input_value.type,
            value: savedChild.data.node.template.input_value.value,
            edited: Boolean(savedChild.data.node.edited),
            edges: savedFlow.data.edges.length,
            groupValue: savedGroup.data.node.template[exposed].value,
            targetHandle: connected
              ? JSON.parse(
                  savedFlow.data.edges[0]?.targetHandle.replaceAll("œ", '"') ??
                    "null",
                )
              : null,
          };
        })
        .toEqual({
          type: breaking ? "str" : "other",
          value: savedValue,
          edited: breaking,
          edges: connected ? 1 : 0,
          groupValue: savedValue,
          targetHandle: connected ? { ...targetHandle, type: "other" } : null,
        });
      await Promise.all([
        page.waitForResponse(
          (response) =>
            new URL(response.url()).pathname === "/api/v1/all" && response.ok(),
        ),
        page.reload(),
      ]);
      await waitForFlowEditorReady(page);
      await expect(page.getByTestId("div-generic-node")).toHaveCount(2);
      await expect(
        page.getByRole("button", { name: "Input & Output", exact: true }),
      ).toBeVisible();
      await expect(page.locator(".react-flow__edge")).toHaveCount(
        connected ? 1 : 0,
      );
      if (connected) {
        await expect(page.locator(".react-flow__edge")).toHaveAttribute(
          "data-id",
          new RegExp(`${input.id}.*${group.id}`),
        );
      }
      await expect(page.getByTestId("update-all-button")).toHaveCount(0);
      await page.screenshot({
        path: testInfo.outputPath("grouped-after-reload.png"),
      });
    },
  );
}

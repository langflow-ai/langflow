import { type ChildProcess, spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer } from "node:net";
import path from "node:path";
import type { APIClassType, APIObjectType } from "../../../src/types/api";
import type { FlowType, GenericNodeType } from "../../../src/types/flow";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

const hardFlows = path.resolve(
  __dirname,
  "../../../../lfx/tests/data/component_compat/hard_flows/v1.13.0",
);

async function unusedPort(): Promise<number> {
  const server = createServer();
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  if (!address || typeof address === "string")
    throw new Error("No loopback port was assigned");
  await new Promise<void>((resolve, reject) =>
    server.close((error) => (error ? reject(error) : resolve())),
  );
  return address.port;
}

async function stopServer(server: ChildProcess | undefined) {
  if (!server || server.exitCode !== null) return;
  await new Promise<void>((resolve) => {
    server.once("exit", () => resolve());
    server.kill("SIGTERM");
  });
}

function fixtureNode(flow: FlowType, componentType: string): GenericNodeType {
  const node = flow.data?.nodes.find(
    (candidate) => candidate.data.type === componentType,
  );
  if (!node || node.type !== "genericNode" || !node.data.node) {
    throw new Error(`Fixture has no ${componentType} node`);
  }
  return node;
}

function preservedState(flow: FlowType, nodeId: string, fieldNames: string[]) {
  const node = flow.data?.nodes.find(
    (candidate) => candidate.id === nodeId,
  ) as GenericNodeType;
  return {
    fields: Object.fromEntries(
      fieldNames.map((name) => [
        name,
        {
          value: node.data.node?.template[name]?.value,
          load_from_db: node.data.node?.template[name]?.load_from_db ?? false,
        },
      ]),
    ),
    edges: flow.data!.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      sourceHandle: JSON.parse(edge.sourceHandle!.replaceAll("œ", '"')),
      targetHandle: JSON.parse(edge.targetHandle!.replaceAll("œ", '"')),
    })),
  };
}

let mcpServer: ChildProcess | undefined;
let mcpUrl: string;
const createdResources = new Map<
  string,
  { flows: string[]; servers: string[] }
>();

test.beforeAll(async () => {
  const port = await unusedPort();
  mcpUrl = `http://127.0.0.1:${port}/mcp`;
  mcpServer = spawn(
    "uv",
    [
      "run",
      "--no-sync",
      "python",
      path.resolve(__dirname, "../../fixtures/mcp-loopback-server.py"),
      "--transport",
      "streamable-http",
      "--port",
      String(port),
      "--tool-set",
      "upgrade",
    ],
    { stdio: "ignore" },
  );
  try {
    await expect
      .poll(
        async () => {
          if (mcpServer?.exitCode !== null)
            throw new Error("MCP fixture exited before startup");
          try {
            return (await fetch(mcpUrl)).status;
          } catch {
            return 0;
          }
        },
        { timeout: 30_000 },
      )
      .toBe(406);
  } catch (error) {
    await stopServer(mcpServer);
    throw error;
  }
});

test.afterAll(async () => stopServer(mcpServer));

test.afterEach(async ({ page }, testInfo) => {
  const resources = createdResources.get(testInfo.testId);
  if (!resources) return;
  for (const name of resources.servers) {
    const response = await page.request.delete(`/api/v2/mcp/servers/${name}`);
    expect(response.ok()).toBeTruthy();
  }
  for (const id of resources.flows.reverse()) {
    const response = await page.request.delete(`/api/v1/flows/${id}`);
    expect(response.ok()).toBeTruthy();
  }
  createdResources.delete(testInfo.testId);
});

for (const componentType of ["RunFlow", "MCPTools"] as const) {
  for (const available of [true, false]) {
    test(
      `${componentType} ${available ? "keeps generated fields and connections" : "names fields when discovery is unavailable"} during ${componentType === "RunFlow" ? "single" : "bulk"} update`,
      { tag: ["@release", "@workspace", "@components"] },
      async ({ page }, testInfo) => {
        const resources = { flows: [] as string[], servers: [] as string[] };
        createdResources.set(testInfo.testId, resources);
        await awaitBootstrapTest(page, {
          skipModal: true,
          seedFlowIfEmpty: false,
        });
        const catalogResponse = await page.request.get("/api/v1/all");
        expect(catalogResponse.ok()).toBeTruthy();
        const catalog = (await catalogResponse.json()) as APIObjectType;
        const definitions = Object.assign(
          {},
          ...Object.values(catalog),
        ) as Record<string, APIClassType>;
        const filename =
          componentType === "RunFlow"
            ? "run_flow_inputs.json"
            : "mcp_tools_arguments.json";
        const flow = JSON.parse(
          readFileSync(path.join(hardFlows, filename), "utf8"),
        ) as FlowType;
        const node = fixtureNode(flow, componentType);
        const saved = node.data.node!;
        // The fixture contract is historical even when its class source is unchanged.
        // A comment makes Update available without changing component behavior.
        saved.template.code.value +=
          "\n# Historical generated-field upgrade fixture\n";
        const generatedFields =
          componentType === "RunFlow"
            ? Object.keys(saved.template).filter((name) => name.includes("~"))
            : ["name", "times"];

        if (componentType === "RunFlow") {
          let selected = {
            id: randomUUID(),
            name: "Unavailable child flow",
            updated_at: new Date().toISOString(),
          };
          if (available) {
            const nodes = [
              ["ChatInput", "ChatInput-NrNFA"],
              ["TextInput", "TextInput-v7wpH"],
              ["ChatOutput", "ChatOutput-evE3l"],
            ].map(([type, id], index) => ({
              id,
              type: "genericNode",
              position: { x: index * 400, y: 0 },
              data: { id, type, node: structuredClone(definitions[type]) },
            }));
            const childResponse = await page.request.post("/api/v1/flows/", {
              data: {
                name: `Upgrade child ${randomUUID()}`,
                data: { nodes, edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
              },
            });
            expect(childResponse.status()).toBe(201);
            selected = await childResponse.json();
            resources.flows.push(selected.id);
          }
          saved.template.flow_id_selected.value = selected.id;
          saved.template.flow_name_selected.value = selected.name;
          saved.template.flow_name_selected.selected_metadata = {
            id: selected.id,
            updated_at: selected.updated_at,
          };
          saved.template.flow_name_selected.options = [selected.name];
          saved.template.flow_name_selected.options_metadata = [
            saved.template.flow_name_selected.selected_metadata,
          ];
          saved.template["TextInput-v7wpH~input_value"].value =
            "Saved nested text";
          saved.template["ChatInput-NrNFA~sender_name"].value = "Saved caller";
          saved.template["ChatInput-NrNFA~should_store_message"].value = false;
        } else {
          const serverName = `upgrade-greeter-${randomUUID()}`;
          const config = {
            url: available
              ? mcpUrl
              : `http://127.0.0.1:${await unusedPort()}/mcp`,
          };
          const registered = await page.request.post(
            `/api/v2/mcp/servers/${serverName}`,
            { data: config },
          );
          expect(registered.ok()).toBeTruthy();
          resources.servers.push(serverName);
          saved.template.mcp_server.value = { name: serverName, config };
          saved.template.times.value = 3;
        }
        const before = preservedState(flow, node.id, generatedFields);
        const created = await page.request.post("/api/v1/flows/", {
          data: {
            name: `generated-upgrade-${componentType}-${available}-${randomUUID()}`,
            data: flow.data,
          },
        });
        expect(created.status()).toBe(201);
        const flowId = (await created.json()).id as string;
        resources.flows.push(flowId);
        await page.goto(`/flow/${flowId}`);
        await expect(page.getByTestId("div-generic-node")).toHaveCount(
          flow.data!.nodes.length,
        );
        await page.keyboard.press("ControlOrMeta+Digit1");
        const updated = page.waitForResponse(
          (response) =>
            new URL(response.url()).pathname === "/api/v1/custom_component" &&
            response.request().method() === "POST" &&
            response.request().postDataJSON()?.frontend_node?.display_name ===
              saved.display_name,
        );
        const canvasNodeBefore = page.locator(
          `.react-flow__node[data-id="${node.id}"]`,
        );
        const updateButton =
          componentType === "RunFlow"
            ? canvasNodeBefore
                .getByTestId("review-button")
                .or(canvasNodeBefore.getByTestId("update-button"))
            : page.getByTestId("update-all-button");
        const requiresReview = (await updateButton.innerText()).includes(
          "Review",
        );
        await updateButton.click();
        const dialog = page
          .getByRole("dialog")
          .filter({ hasText: "Create backup flow before updating" });
        if (requiresReview) {
          await expect(dialog).toBeVisible();
          await dialog.getByTestId("backup-flow-checkbox").uncheck();
          if (componentType === "MCPTools") {
            await dialog
              .getByRole("row")
              .filter({ hasText: saved.display_name })
              .getByRole("checkbox")
              .check();
          }
          await dialog
            .getByRole("button", { name: /^Update Component/ })
            .click();
        }
        const response = await updated;
        expect(response.ok()).toBeTruthy();
        const result = await response.json();
        if (!available) {
          expect(result.warnings).toEqual(
            expect.arrayContaining([
              expect.objectContaining({
                code: "generated_fields_not_restored",
              }),
            ]),
          );
          await expect(
            page.getByText(
              `Some fields could not be restored in ${saved.display_name}`,
              { exact: true },
            ),
          ).toBeVisible();
          const expectedFields =
            componentType === "RunFlow"
              ? ["Text (Text Input)", "Sender Name (Chat Input)"]
              : ["Name", "Times"];
          for (const field of expectedFields)
            await expect(
              page.getByText(field, { exact: true }).last(),
            ).toBeVisible();
          await expect
            .poll(async () => {
              const persisted = await page.request.get(
                `/api/v1/flows/${flowId}`,
              );
              expect(persisted.ok()).toBeTruthy();
              const savedFlow = (await persisted.json()) as FlowType;
              return fixtureNode(savedFlow, componentType).data.node?.template
                .code.value;
            })
            .toBe(definitions[componentType].template.code.value);
          await page.screenshot({
            path: testInfo.outputPath(`${componentType}-missing-fields.png`),
          });
          return;
        }
        expect(result.warnings ?? []).toEqual([]);
        await expect
          .poll(async () => {
            const persisted = await page.request.get(`/api/v1/flows/${flowId}`);
            expect(persisted.ok()).toBeTruthy();
            const savedFlow = (await persisted.json()) as FlowType;
            const updatedNode = fixtureNode(savedFlow, componentType);
            return {
              code: updatedNode.data.node?.template.code.value,
              state: preservedState(savedFlow, node.id, generatedFields),
            };
          })
          .toEqual({
            code: definitions[componentType].template.code.value,
            state: before,
          });
        await Promise.all([
          page.waitForResponse(
            (response) =>
              new URL(response.url()).pathname === "/api/v1/all" &&
              response.ok(),
          ),
          page.reload(),
        ]);
        await expect(page.getByTestId("div-generic-node")).toHaveCount(
          flow.data!.nodes.length,
        );
        await expect(page.locator(".react-flow__edge")).toHaveCount(
          before.edges.length,
        );
        const canvasNode = page.locator(
          `.react-flow__node[data-id="${node.id}"]`,
        );
        await expect(
          canvasNode
            .getByTestId("review-button")
            .or(canvasNode.getByTestId("update-button")),
        ).toHaveCount(0);
        await page.screenshot({
          path: testInfo.outputPath(`${componentType}-after-reload.png`),
        });
      },
    );
  }
}

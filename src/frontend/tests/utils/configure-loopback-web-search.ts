import type { Page } from "@playwright/test";
import { expect } from "../fixtures";
import { waitForFlowEditorReady } from "./flow/wait-for-flow-editor-ready";
import {
  flushPendingFlowAutosave,
  reloadAndWaitForFlowPersistence,
} from "./flow-editor-persistence";

const LOOPBACK_WEB_SEARCH_CODE = `
from lfx.custom import Component
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema import Data


class WebSearchComponent(Component):
    display_name = "Web Search"
    description = "Deterministic loopback search fixture for Playwright."
    icon = "search"
    name = "UnifiedWebSearch"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            tool_mode=True,
            required=True,
        ),
        IntInput(name="max_results", display_name="Max Results", value=3, advanced=True),
    ]
    outputs = [Output(name="results", display_name="Results", method="perform_search")]

    def perform_search(self) -> list[Data]:
        return [
            Data(
                data={
                    "marker": "LOOPBACK_WEB_SEARCH_USED",
                    "query": self.query,
                    "title": "Deterministic Langflow travel and social research",
                    "url": "https://example.test/langflow-search-fixture",
                    "content": "Local attractions, transit, food, and current social content research.",
                }
            )
        ]
`;

/** Replace the starter project's networked search implementation, preserving its real tool edge. */
export async function configureLoopbackWebSearch(page: Page): Promise<void> {
  const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
  expect(flowId).toBeTruthy();
  if (!flowId) throw new Error(`Expected a flow URL, received ${page.url()}`);
  await flushPendingFlowAutosave(page);
  const response = await page.request.get(`/api/v1/flows/${flowId}`);
  expect(response.ok(), `GET flow ${flowId}`).toBeTruthy();
  const flow = await response.json();
  const searchNodes = flow.data.nodes.filter(
    (node: { id?: string; data?: { type?: string } }) =>
      node.data?.type === "UnifiedWebSearch",
  );
  expect(searchNodes.length).toBeGreaterThan(0);
  const searchNodeIds = searchNodes.map(
    (node: { id?: string }, index: number) =>
      node.id ?? `missing-unified-web-search-id-${index}`,
  );
  expect(
    searchNodeIds.filter((id) => id.startsWith("missing-")),
    "UnifiedWebSearch nodes must have stable ids",
  ).toHaveLength(0);
  for (const node of searchNodes) {
    const codeField = node.data?.node?.template?.code;
    expect(
      codeField,
      "UnifiedWebSearch node is missing template.code",
    ).toBeTruthy();
    codeField.value = LOOPBACK_WEB_SEARCH_CODE;
  }
  const update = await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: flow.data },
  });
  expect(update.ok(), `PATCH flow ${flowId}`).toBeTruthy();
  await reloadAndWaitForFlowPersistence(
    page,
    flowId,
    flow.data,
    (persistedData) => {
      const persistedNodes = new Map(
        (persistedData.nodes ?? []).map((node) => [
          (node as { id?: string }).id,
          node,
        ]),
      );
      return searchNodeIds.every((nodeId) => {
        const node = persistedNodes.get(nodeId) as
          | {
              data?: {
                type?: string;
                node?: { template?: { code?: { value?: string } } };
              };
            }
          | undefined;
        return (
          node?.data?.type === "UnifiedWebSearch" &&
          node.data.node?.template?.code?.value?.includes(
            "LOOPBACK_WEB_SEARCH_USED",
          ) === true
        );
      });
    },
  );
  await waitForFlowEditorReady(page);

  const verifyResponse = await page.request.get(`/api/v1/flows/${flowId}`);
  expect(verifyResponse.ok(), `Verify flow ${flowId}`).toBeTruthy();
  const verifiedFlow = await verifyResponse.json();
  const verifiedNodesById = new Map(
    verifiedFlow.data.nodes.map((node: { id?: string }) => [node.id, node]),
  );
  const missingFixtureNodes = searchNodeIds.filter((nodeId) => {
    const node = verifiedNodesById.get(nodeId) as
      | {
          data?: {
            type?: string;
            node?: { template?: { code?: { value?: string } } };
          };
        }
      | undefined;
    return (
      node?.data?.type !== "UnifiedWebSearch" ||
      !node.data.node?.template?.code?.value?.includes(
        "LOOPBACK_WEB_SEARCH_USED",
      )
    );
  });
  expect(
    missingFixtureNodes,
    "Loopback web-search configuration was overwritten after reload",
  ).toHaveLength(0);
}

import { expect, type LangflowPage } from "../fixtures";
import { adjustScreenView } from "./adjust-screen-view";
import { awaitBootstrapTest } from "./await-bootstrap-test";
import { TIMEOUTS } from "./constants/timeouts";
import { buildMockTrigger, type TriggerMockServer } from "./trigger-mocks";

/** The search box mounts before it takes input, so wait until the text sticks. */
export async function searchPalette(page: LangflowPage, query: string) {
  const search = page.getByTestId("sidebar-search-input");
  await expect(search).toBeVisible({ timeout: TIMEOUTS.standard });
  await expect(async () => {
    await search.click();
    await search.fill(query);
    await expect(search).toHaveValue(query, { timeout: TIMEOUTS.fast });
  }).toPass();
}

/**
 * Adds the Schedule trigger to a blank flow and stands in for the backend's
 * save-time reconciliation by registering the row the server would create.
 * Returns the canvas node.
 */
export async function placeScheduleTrigger(
  page: LangflowPage,
  server: TriggerMockServer,
  { triggerId, flowName }: { triggerId: string; flowName: string },
) {
  // The delayed assistant onboarding popover would consume the badge's Escape.
  await page.addInitScript(() => {
    localStorage.setItem("langflow-assistant-discovered", "true");
  });
  await awaitBootstrapTest(page);
  await page.getByTestId("blank-flow").click();
  await searchPalette(page, "schedule");
  await page.getByTestId("add-component-button-schedule").click();
  await adjustScreenView(page);

  const node = page.locator(".react-flow__node").first();
  // Nothing on the server yet: the node asks for a save, not a state.
  await expect(node.getByTestId("trigger-node-unsaved")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });

  const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
  const nodeId = await node.getAttribute("data-id");
  expect(flowId, "flow id should be in the URL").toBeTruthy();
  expect(nodeId, "trigger node should carry its id").toBeTruthy();

  server.upsert(
    buildMockTrigger({
      id: triggerId,
      flow_id: flowId!,
      flow_name: flowName,
      node_id: nodeId!,
    }),
  );
  await expect(node.getByTestId("trigger-node-badge")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  return node;
}

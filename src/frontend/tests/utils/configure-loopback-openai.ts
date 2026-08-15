import type { Page } from "@playwright/test";
import { expect } from "../fixtures";
import { adjustScreenView } from "./adjust-screen-view";
import { waitForFlowEditorReady } from "./flow/wait-for-flow-editor-ready";
import {
  flushPendingFlowAutosave,
  reloadAndWaitForFlowPersistence,
} from "./flow-editor-persistence";
import { modelRefreshNodeCount } from "./flow-editor-persistence-policy.mjs";
import {
  applyLoopbackToFlowData,
  isFlowDataLoopbackConfigured,
  isNodeLoopbackConfigured,
  type LoopbackFlowData,
  type LoopbackNode,
} from "./loopback-provider-policy.mjs";
import {
  isLoopbackProviderSeeded,
  waitForMountModelRefresh,
} from "./seed-loopback-provider";
import { updateOldComponents } from "./update-old-components";

export {
  LOOPBACK_MODEL,
  LOOPBACK_OPENAI_API_KEY,
  LOOPBACK_OPENAI_BASE_URL,
} from "./loopback-provider-policy.mjs";

type FlowRead = {
  data?: LoopbackFlowData;
};

function currentFlowId(page: Page): string {
  const match = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/);
  if (!match) throw new Error(`Expected a flow URL, received ${page.url()}`);
  return match[1];
}

async function readFlow(
  page: Page,
  flowId: string,
  description: string,
): Promise<FlowRead> {
  const response = await page.request.get(`/api/v1/flows/${flowId}`);
  expect(response.ok(), `${description} ${flowId}`).toBeTruthy();
  return (await response.json()) as FlowRead;
}

function nodesById(
  data: LoopbackFlowData | undefined,
): Map<string, LoopbackNode> {
  return new Map(
    (data?.nodes ?? []).flatMap((node) =>
      node.id ? ([[node.id, node]] as [string, LoopbackNode][]) : [],
    ),
  );
}

export async function configureLoopbackOpenAI(
  page: Page,
  options?: {
    skipAdjustScreenView?: boolean;
    skipUpdateOldComponents?: boolean;
  },
): Promise<void> {
  if (!options?.skipAdjustScreenView) await adjustScreenView(page);
  if (!options?.skipUpdateOldComponents) await updateOldComponents(page);

  const flowId = currentFlowId(page);
  await flushPendingFlowAutosave(page);
  const flow = await readFlow(page, flowId, "GET flow");
  const { data: configuredData, targetNodeIds } = applyLoopbackToFlowData(
    flow.data ?? {},
  );
  if (targetNodeIds.length === 0) {
    throw new Error(`Flow ${flowId} has no OpenAI-compatible model inputs`);
  }

  if (
    isLoopbackProviderSeeded(page) &&
    isFlowDataLoopbackConfigured(flow.data ?? {})
  ) {
    // The starter template was served pre-configured, so the persisted flow and
    // the editor already agree — there is no out-of-band patch to reload for.
    // Only the mount refresh can still write these nodes, so wait for it to
    // land before anything reads them back. Size the wait the way the editor
    // does: a target node without a `model`-typed field never refreshes.
    const expectedRefreshes = modelRefreshNodeCount(flow.data ?? {});
    if (expectedRefreshes > 0) {
      await waitForMountModelRefresh(page, flowId, expectedRefreshes);
    }
    await flushPendingFlowAutosave(page);
  } else {
    if (isLoopbackProviderSeeded(page)) {
      // Correct but slow: the seed did not reach this flow, so we are paying
      // for the reload this spec opted out of. Say so rather than letting the
      // optimization rot silently across every seeded spec.
      console.warn(
        `Flow ${flowId} was not seeded with the loopback provider; falling back to patch-and-reload`,
      );
    }
    const updateResponse = await page.request.patch(`/api/v1/flows/${flowId}`, {
      data: { data: configuredData },
    });
    expect(updateResponse.ok(), `PATCH flow ${flowId}`).toBeTruthy();

    await reloadAndWaitForFlowPersistence(
      page,
      flowId,
      configuredData,
      (persistedData) => {
        const persistedNodes = nodesById(persistedData);
        return targetNodeIds.every((id) => {
          const node = persistedNodes.get(id);
          return node !== undefined && isNodeLoopbackConfigured(node);
        });
      },
    );
  }

  await waitForFlowEditorReady(page);
  const verifiedFlow = await readFlow(page, flowId, "Verify flow");
  const verifiedNodes = nodesById(verifiedFlow.data);
  const clobberedNodeIds = targetNodeIds.filter((id) => {
    const node = verifiedNodes.get(id);
    return !node || !isNodeLoopbackConfigured(node);
  });
  if (clobberedNodeIds.length > 0) {
    throw new Error(
      `Loopback model configuration was overwritten for nodes: ${clobberedNodeIds.join(", ")}`,
    );
  }
  if (!options?.skipAdjustScreenView) {
    await adjustScreenView(page);
    await flushPendingFlowAutosave(page);
  }
}

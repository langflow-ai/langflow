import type { Page, Request, Response } from "@playwright/test";
import {
  canTrackFullFlowAutosavePayload,
  isFlowPersistenceBarrierSatisfied,
  isModelRefreshBody,
  modelRefreshNodeCount,
  requiresPostRefreshAutosave,
} from "./flow-editor-persistence-policy.mjs";

type FlowNode = {
  id?: string;
  type?: string;
  data?: {
    node?: {
      template?: Record<string, unknown>;
    };
  };
};

export type FlowData = {
  nodes?: FlowNode[];
  [key: string]: unknown;
};

type BrowserFlowStoreModule = {
  default: {
    getState: () => {
      autoSaveFlow?: {
        flush: () => Promise<void> | void;
      };
    };
  };
};

function requestBody(request: Request): unknown {
  try {
    return request.postDataJSON();
  } catch {
    return undefined;
  }
}

function isModelRefreshRequest(request: Request): boolean {
  if (
    request.method() !== "POST" ||
    new URL(request.url()).pathname !== "/api/v1/custom_component/update"
  ) {
    return false;
  }

  return isModelRefreshBody(requestBody(request));
}

async function assertFinishedResponse(
  response: Response,
  description: string,
): Promise<void> {
  if (!response.ok()) {
    throw new Error(`${description} returned ${response.status()}`);
  }
  const failure = await response.finished();
  if (failure) {
    throw new Error(`${description} did not finish: ${failure.message}`);
  }
}

/**
 * Flush the editor's real debounced save and serialized save queue.
 *
 * Test helpers patch the persisted flow directly. Draining the browser queue
 * first prevents an older canvas snapshot from landing after that direct PATCH.
 */
export async function flushPendingFlowAutosave(page: Page): Promise<void> {
  const didFlush = await page.evaluate(async () => {
    const storeModulePath = "/src/stores/flowStore.ts";
    const flowStoreModule = (await import(
      /* @vite-ignore */ storeModulePath
    )) as BrowserFlowStoreModule;
    const autoSaveFlow = flowStoreModule.default.getState().autoSaveFlow;
    if (!autoSaveFlow?.flush) return false;
    await autoSaveFlow.flush();
    return true;
  });

  if (!didFlush) {
    throw new Error(
      "Flow editor autosave queue was unavailable before fixture persistence",
    );
  }
}

/**
 * Reload a flow and wait for its model refreshes and their exact full-flow
 * autosave. The listener is armed before navigation so fast CI responses cannot
 * escape the barrier. A data-only fixture PATCH cannot satisfy this matcher.
 */
export async function reloadAndWaitForFlowPersistence(
  page: Page,
  flowId: string,
  data: FlowData,
  matchesPersistedData: (persistedData: FlowData) => boolean,
): Promise<void> {
  const flowPath = `/api/v1/flows/${flowId}`;
  const expectedModelRefreshes = modelRefreshNodeCount(data);
  if (!requiresPostRefreshAutosave(data)) {
    await page.reload();
    return;
  }

  const trackedModelRefreshes = new Set<Request>();
  const trackedAutosaves = new Set<Request>();
  let completedModelRefreshes = 0;
  let autosaveFinished = false;
  let sawReloadNavigation = false;
  let sawReloadFlowRead = false;
  let dispose = () => {};
  let failPersistence = (_error: unknown) => {};

  const persistence = new Promise<void>((resolve, reject) => {
    let settled = false;

    const finish = (error?: unknown) => {
      if (settled) return;
      settled = true;
      dispose();
      if (error) reject(error);
      else resolve();
    };
    failPersistence = finish;

    const maybeFinish = () => {
      if (
        isFlowPersistenceBarrierSatisfied(
          autosaveFinished,
          completedModelRefreshes,
          trackedModelRefreshes.size,
        )
      ) {
        finish();
      }
    };

    const onRequest = (request: Request) => {
      const pathname = new URL(request.url()).pathname;
      if (
        request.isNavigationRequest() &&
        request.frame() === page.mainFrame() &&
        pathname.includes(`/flow/${flowId}`)
      ) {
        sawReloadNavigation = true;
        return;
      }
      if (!sawReloadNavigation) return;

      if (request.method() === "GET" && pathname === flowPath) {
        sawReloadFlowRead = true;
        return;
      }
      if (!sawReloadFlowRead) return;

      if (isModelRefreshRequest(request)) {
        trackedModelRefreshes.add(request);
        return;
      }
      if (request.method() !== "PATCH" || pathname !== flowPath) return;

      const body = requestBody(request);
      if (
        canTrackFullFlowAutosavePayload(
          body,
          matchesPersistedData,
          trackedModelRefreshes.size,
          expectedModelRefreshes,
        )
      ) {
        trackedAutosaves.add(request);
      }
    };

    const onResponse = (response: Response) => {
      const request = response.request();
      if (trackedModelRefreshes.has(request)) {
        void assertFinishedResponse(response, `Model refresh in flow ${flowId}`)
          .then(() => {
            completedModelRefreshes += 1;
            maybeFinish();
          })
          .catch(finish);
        return;
      }
      if (!trackedAutosaves.has(request)) return;

      void assertFinishedResponse(response, `Autosave for flow ${flowId}`)
        .then(() => {
          autosaveFinished = true;
          maybeFinish();
        })
        .catch(finish);
    };

    dispose = () => {
      page.off("request", onRequest);
      page.off("response", onResponse);
    };
    page.on("request", onRequest);
    page.on("response", onResponse);
  });

  try {
    await page.reload();
    await persistence;
  } catch (error) {
    failPersistence(error);
    await persistence.catch(() => undefined);
    throw error;
  } finally {
    dispose();
  }
}

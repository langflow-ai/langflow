import type { Page, Request, Response } from "@playwright/test";
import { TIMEOUTS } from "./constants/timeouts";
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
        cancel: () => void;
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

async function cancelPendingFlowAutosave(page: Page): Promise<void> {
  const didCancel = await page.evaluate(async () => {
    const storeModulePath = "/src/stores/flowStore.ts";
    const flowStoreModule = (await import(
      /* @vite-ignore */ storeModulePath
    )) as BrowserFlowStoreModule;
    const autoSaveFlow = flowStoreModule.default.getState().autoSaveFlow;
    if (!autoSaveFlow?.cancel) return false;
    autoSaveFlow.cancel();
    return true;
  });

  if (!didCancel) {
    throw new Error(
      "Flow editor autosave queue was unavailable before fixture reload",
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
  // A viewport/layout update can schedule a stale browser snapshot after the
  // fixture's direct PATCH. Cancel that pending debounce before navigation so
  // it cannot overwrite the configured graph during reload.
  await cancelPendingFlowAutosave(page);
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
  let persistenceTimeout: ReturnType<typeof setTimeout> | undefined;
  // The budget covers the model refresh and its autosave, not the page load
  // that precedes them. Playwright serves the editor from a Vite dev server, so
  // a reload replays ~3.5k unbundled module requests; on Windows CI that alone
  // measures 19-35s. Arming the deadline before the reload spent the entire
  // budget before the first tracked request was even sent.
  const deadlineAfterReload = () =>
    new Promise<never>((_, reject) => {
      persistenceTimeout = setTimeout(() => {
        reject(
          new Error(
            `Flow ${flowId} did not finish model refresh and autosave persistence within ${TIMEOUTS.long}ms after reload`,
          ),
        );
      }, TIMEOUTS.long);
    });

  try {
    await page.reload();
    await Promise.race([persistence, deadlineAfterReload()]);
  } catch (error) {
    failPersistence(error);
    await persistence.catch(() => undefined);
    throw error;
  } finally {
    if (persistenceTimeout !== undefined) clearTimeout(persistenceTimeout);
    dispose();
  }
}

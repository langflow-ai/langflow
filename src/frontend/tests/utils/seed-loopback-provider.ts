import { expect, type Page, type Request } from "@playwright/test";
import { TIMEOUTS } from "./constants/timeouts";
import {
  isModelRefreshBody,
  modelRefreshFlowId,
} from "./flow-editor-persistence-policy.mjs";
import {
  applyLoopbackToExamples,
  type LoopbackExample,
} from "./loopback-provider-policy.mjs";

const STARTER_TEMPLATE_CATALOG = "**/api/v1/flows/basic_examples/**";
const MODEL_REFRESH_PATH = "/api/v1/custom_component/update";

type MountRefreshTracker = {
  completedByFlow: Map<string, number>;
};

const trackers = new WeakMap<Page, MountRefreshTracker>();

function trackMountModelRefreshes(page: Page): MountRefreshTracker {
  const tracker: MountRefreshTracker = { completedByFlow: new Map() };
  const inFlight = new Map<Request, string>();

  page.on("request", (request) => {
    if (
      request.method() !== "POST" ||
      new URL(request.url()).pathname !== MODEL_REFRESH_PATH
    ) {
      return;
    }
    let body: unknown;
    try {
      body = request.postDataJSON();
    } catch {
      return;
    }
    if (!isModelRefreshBody(body)) return;
    const flowId = modelRefreshFlowId(body);
    if (flowId) inFlight.set(request, flowId);
  });

  page.on("response", (response) => {
    const request = response.request();
    const flowId = inFlight.get(request);
    if (!flowId) return;
    inFlight.delete(request);
    if (!response.ok()) return;
    tracker.completedByFlow.set(
      flowId,
      (tracker.completedByFlow.get(flowId) ?? 0) + 1,
    );
  });

  return tracker;
}

/**
 * Serve the starter-template catalog already configured for the loopback
 * provider, so a flow created from a template is born pointed at the local
 * fixture server instead of a real provider.
 *
 * This is the fast path for {@link configureLoopbackOpenAI}: with the template
 * pre-seeded there is nothing to patch behind the editor's back, so that helper
 * can skip its reload — which costs 19-35s on Windows CI, where Playwright
 * serves the app from a Vite dev server and a reload replays ~3.5k unbundled
 * module requests.
 *
 * Call before the first navigation. `configureLoopbackOpenAI` still works
 * without it (it falls back to patch-and-reload), so this is an optimization,
 * never a correctness requirement.
 */
export async function seedLoopbackProvider(page: Page): Promise<void> {
  if (trackers.has(page)) return;

  // React Query caches the catalog for the session, so seeding after the app
  // has loaded would silently do nothing and leave the slow path in place.
  expect(
    page.url(),
    "seedLoopbackProvider must run before the first navigation",
  ).toBe("about:blank");

  trackers.set(page, trackMountModelRefreshes(page));

  await page.route(STARTER_TEMPLATE_CATALOG, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }

    const response = await route.fetch();
    if (!response.ok()) {
      await route.fulfill({ response });
      return;
    }

    let examples: unknown;
    try {
      examples = await response.json();
    } catch {
      await route.fulfill({ response });
      return;
    }
    if (!Array.isArray(examples)) {
      await route.fulfill({ response });
      return;
    }

    await route.fulfill({
      status: response.status(),
      contentType: "application/json",
      body: JSON.stringify(
        applyLoopbackToExamples(examples as LoopbackExample[]),
      ),
    });
  });
}

export function isLoopbackProviderSeeded(page: Page): boolean {
  return trackers.has(page);
}

/**
 * Wait for the model refreshes the editor fires when it mounts a flow.
 *
 * `useApplyFlowToCanvas` kicks off `refreshAllModelInputs` for every model node
 * on mount, and its result is written back into the node. Waiting for it means
 * a caller that reads the flow afterwards cannot be overtaken by a refresh that
 * was still in flight.
 */
export async function waitForMountModelRefresh(
  page: Page,
  flowId: string,
  expectedRefreshes: number,
): Promise<void> {
  const tracker = trackers.get(page);
  expect(
    tracker,
    "waitForMountModelRefresh requires seedLoopbackProvider",
  ).toBeDefined();

  await expect
    .poll(() => tracker!.completedByFlow.get(flowId) ?? 0, {
      timeout: TIMEOUTS.long,
      message: `Flow ${flowId} did not complete ${expectedRefreshes} mount model refresh(es)`,
    })
    .toBeGreaterThanOrEqual(expectedRefreshes);
}

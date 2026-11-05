import type { Frame, Page, Request } from "@playwright/test";
import type { PendingRequestTracker } from "./server-error-contract.mjs";

/** Retire fetch and XHR requests abandoned when Chromium replaces their document. */
export async function installDocumentRequestCleanup(
  page: Page,
  trackers: PendingRequestTracker<Request>[],
): Promise<() => void> {
  const navigationCandidates = new Map<Frame, Set<Request>>();
  const frameForRequest = (request: Request): Frame | undefined => {
    try {
      return request.frame();
    } catch {
      // Early navigation requests can arrive before their frame exists.
      return undefined;
    }
  };
  const onRequest = (request: Request) => {
    if (!request.isNavigationRequest()) return;
    const frame = frameForRequest(request);
    if (!frame) return;
    navigationCandidates.set(
      frame,
      new Set(
        trackers.flatMap((tracker) =>
          tracker
            .snapshot()
            .filter(
              (pending) =>
                (pending.resourceType() === "xhr" ||
                  pending.resourceType() === "fetch") &&
                frameForRequest(pending) === frame,
            ),
        ),
      ),
    );
  };

  await page.exposeBinding(
    "__langflowPlaywrightDocumentStarted",
    ({ frame }) => {
      const abandoned = navigationCandidates.get(frame);
      navigationCandidates.delete(frame);
      for (const request of abandoned ?? []) {
        for (const tracker of trackers) tracker.finish(request);
      }
    },
  );
  await page.addInitScript(() => {
    // Init scripts run for a replacement document, not history/hash changes or
    // aborted navigations. The captured set excludes requests from this new
    // document even if its scripts run before the binding reaches Node.
    void (
      globalThis as typeof globalThis & {
        __langflowPlaywrightDocumentStarted: () => Promise<void>;
      }
    ).__langflowPlaywrightDocumentStarted();
  });
  page.on("request", onRequest);

  return () => {
    page.off("request", onRequest);
    navigationCandidates.clear();
  };
}

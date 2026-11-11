import type { Frame, Page, Request } from "@playwright/test";
import type { PendingRequestTracker } from "./server-error-contract.mjs";

/** Retire requests abandoned when Chromium replaces their owning document. */
export async function installDocumentRequestCleanup(
  page: Page,
  trackers: PendingRequestTracker<Request>[],
): Promise<() => void> {
  const navigationCandidates = new Map<
    Frame,
    { requests: Set<Request>; committed: boolean }
  >();
  const frameForRequest = (request: Request): Frame | undefined => {
    try {
      return request.frame();
    } catch {
      // Early navigation requests can arrive before their frame exists.
      return undefined;
    }
  };
  const onRequest = (request: Request) => {
    const frame = frameForRequest(request);
    if (!frame) return;
    const isDocumentRequest =
      request.resourceType() === "xhr" || request.resourceType() === "fetch";
    if (!request.isNavigationRequest()) {
      const candidate = navigationCandidates.get(frame);
      // The old document can keep polling while the navigation response is
      // pending. Chromium can omit cancellation events for these late XHRs
      // too, so capture them until the replacement commits. Requests started
      // by the new document must remain tracked even if its init binding has
      // not reached Node yet.
      if (isDocumentRequest && candidate && !candidate.committed) {
        candidate.requests.add(request);
      }
      return;
    }
    navigationCandidates.set(frame, {
      committed: false,
      requests: new Set(
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
    });
  };

  const onFrameNavigated = (frame: Frame) => {
    const candidate = navigationCandidates.get(frame);
    if (candidate) candidate.committed = true;
  };

  const onFrameDetached = (frame: Frame) => {
    navigationCandidates.delete(frame);
    for (const tracker of trackers) {
      for (const request of tracker.snapshot()) {
        if (
          !request.isNavigationRequest() &&
          frameForRequest(request) === frame
        ) {
          tracker.finish(request);
        }
      }
    }
  };

  await page.exposeBinding(
    "__langflowPlaywrightDocumentStarted",
    ({ frame }) => {
      const abandoned = navigationCandidates.get(frame);
      navigationCandidates.delete(frame);
      for (const request of abandoned?.requests ?? []) {
        for (const tracker of trackers) tracker.finish(request);
      }
    },
  );
  await page.addInitScript(() => {
    // Init scripts confirm a replacement document, not history/hash changes
    // or aborted navigations. The candidate set freezes at navigation commit,
    // before the new document can start its own API requests.
    void (
      globalThis as typeof globalThis & {
        __langflowPlaywrightDocumentStarted: () => Promise<void>;
      }
    ).__langflowPlaywrightDocumentStarted();
  });
  page.on("request", onRequest);
  page.on("framenavigated", onFrameNavigated);
  page.on("framedetached", onFrameDetached);

  return () => {
    page.off("request", onRequest);
    page.off("framenavigated", onFrameNavigated);
    page.off("framedetached", onFrameDetached);
    navigationCandidates.clear();
  };
}

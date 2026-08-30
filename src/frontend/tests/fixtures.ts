// tests/fixtures.ts

import {
  test as base,
  expect,
  type Page,
  type Request,
  type Response,
} from "@playwright/test";
import type { ICheckerResult } from "accessibility-checker";
import * as aChecker from "accessibility-checker";
import "./playwrightCoverage";
import {
  buildA11yScanLabel,
  buildA11ySummaryAttachment,
  countNewA11yViolations,
  formatA11yFailure,
  isCheckerReport,
} from "./utils/accessibility-checker";
import {
  createPendingRequestTracker,
  createServerErrorContract,
  expectServerError,
  getServerErrorContractFailures,
  observeServerError,
  readResponseBodyWithTimeout,
  sanitizeResponseExcerpt,
  shouldSettleApiRequestOnResponse,
  shouldTrackApiRequest,
} from "./utils/server-error-contract.mjs";
import type {
  A11yScanOptions,
  ExpectedServerError,
  LangflowPage,
} from "./utils/types";

export type { A11yScanOptions, LangflowPage } from "./utils/types";

const RUN_A11Y = process.env.RUN_A11Y === "true";
const RUN_A11Y_ASSERT = process.env.RUN_A11Y_ASSERT === "true";
const MAX_FLOW_ERROR_DIAGNOSTICS = 20;
// How long teardown waits for in-flight API requests to settle. Windows CI
// runners routinely need more than 2s to finish the last few requests a test
// kicked off (an MCP server list, a component template refresh), and the wait
// only costs that long when something really is still pending.
const API_REQUEST_DRAIN_TIMEOUT_MS = process.platform === "win32" ? 6000 : 2000;
const RESPONSE_BODY_READ_TIMEOUT_MS = API_REQUEST_DRAIN_TIMEOUT_MS;
const RESPONSE_INSPECTION_DRAIN_TIMEOUT_MS = API_REQUEST_DRAIN_TIMEOUT_MS;
const MAX_PENDING_REQUEST_DIAGNOSTICS = 20;

/**
 * A request a spec intentionally leaves in flight — e.g. a route mocked with a
 * long delay so a loading state stays on screen for the duration of the test.
 * Such a request cannot settle inside the teardown drain window, so it must be
 * declared rather than treated as a stuck request.
 */
type AllowedPendingRequest = {
  method?: string;
  path: string;
};

type ObservedHttpError = {
  method: string;
  path: string;
  status: number;
  statusText: string;
  responseBody?: string;
};
const MAX_CLIENT_ERROR_DIAGNOSTICS = 20;

const getResponseBody = async (
  response: {
    text: () => Promise<string>;
  },
  label: string,
): Promise<string> => {
  const result = await readResponseBodyWithTimeout(response, {
    timeoutMs: RESPONSE_BODY_READ_TIMEOUT_MS,
    label,
  });
  if (result.status === "success") {
    return sanitizeResponseExcerpt(result.body);
  }
  return result.diagnostic;
};

type A11yFixtures = {
  _a11ySession: void;
};

// Optional CPU throttling for reproducing race conditions seen on slower
// runners (Windows CI). Enable with LF_CPU_THROTTLE=<rate>, e.g. 4.
const CPU_THROTTLE_RATE = (() => {
  const raw = process.env.LF_CPU_THROTTLE;
  if (!raw) return 0;
  const n = Number.parseFloat(raw);
  return Number.isFinite(n) && n > 1 ? n : 0;
})();

// Extend test to log backend errors
export const test = base.extend<{ page: LangflowPage }, A11yFixtures>({
  _a11ySession: [
    async ({ browserName }, use) => {
      void browserName;
      await use();

      if (RUN_A11Y) {
        await aChecker.close();
      }
    },
    { scope: "worker", auto: true },
  ],
  page: async ({ page }, use, testInfo) => {
    if (CPU_THROTTLE_RATE > 0) {
      try {
        const client = await page.context().newCDPSession(page);
        await client.send("Emulation.setCPUThrottlingRate", {
          rate: CPU_THROTTLE_RATE,
        });
      } catch {
        // Throttling is best-effort and only supported on Chromium.
      }
    }

    const errors: Array<{
      path: string;
      status: number;
      statusText: string;
      responseBody?: string;
      type?: string;
    }> = [];
    const clientErrors: ObservedHttpError[] = [];
    const serverErrorContract = createServerErrorContract();
    const pendingApiResponseStatuses = createPendingRequestTracker<Request>();
    const pendingApiRequestLifecycles = createPendingRequestTracker<Request>();
    const pendingResponseInspections = new Set<Promise<void>>();
    const responseInspectionErrors: Error[] = [];

    // Flag to allow flow errors (for tests that expect errors)
    let allowFlowErrors = false;

    // Add helper method to page context — see LangflowPage type in utils/types.ts
    (page as Page & { allowFlowErrors?: () => void }).allowFlowErrors = () => {
      allowFlowErrors = true;
    };
    (
      page as Page & {
        expectServerError?: (expectation: ExpectedServerError) => void;
      }
    ).expectServerError = (expectation) => {
      expectServerError(serverErrorContract, expectation);
    };
    const allowedPendingRequests: AllowedPendingRequest[] = [];
    (
      page as Page & {
        expectPendingRequest?: (expectation: AllowedPendingRequest) => void;
      }
    ).expectPendingRequest = (expectation) => {
      allowedPendingRequests.push(expectation);
    };

    let a11yScanIndex = 0;
    (
      page as Page & {
        runA11yScan?: (
          label: string,
          options?: A11yScanOptions,
        ) => Promise<ICheckerResult | null>;
      }
    ).runA11yScan = async (label: string, options?: A11yScanOptions) => {
      if (!RUN_A11Y) {
        return null;
      }

      if (options?.colorScheme) {
        await page.emulateMedia({ colorScheme: options.colorScheme });
      }

      // Let enter animations (Radix popover/dialog fade-ins) finish before
      // scanning. The IBM checker composites element opacity into its
      // contrast measurement, so a popover caught mid `fade-in` reports
      // phantom text_contrast_sufficient violations (LE-2235: 4.00:1 on
      // the model picker that measures 4.95:1 once settled). Infinite
      // animations (spinners) are skipped; the 2s cap keeps a stuck
      // animation from hanging the scan.
      await page.evaluate(() =>
        Promise.race([
          Promise.all(
            document
              .getAnimations()
              .filter((a) => {
                const timing = a.effect?.getTiming();
                return timing?.iterations !== Infinity;
              })
              .map((a) => a.finished.catch(() => undefined)),
          ),
          new Promise((resolve) => setTimeout(resolve, 2000)),
        ]),
      );

      const scanIndex = a11yScanIndex++;
      const scanLabel = buildA11yScanLabel(
        testInfo.project.name,
        label,
        scanIndex,
      );

      const result = await aChecker.getCompliance(page, scanLabel);

      if (!isCheckerReport(result.report)) {
        throw new Error(
          `IBM accessibility scan failed for ${scanLabel}: checker returned an error payload.`,
        );
      }

      testInfo.attachments.push(
        buildA11ySummaryAttachment(scanIndex, scanLabel, result.report),
      );

      if (RUN_A11Y_ASSERT) {
        const newViolationCount = countNewA11yViolations(result.report);
        const failureMessage = formatA11yFailure(scanLabel, result.report);

        expect(newViolationCount, failureMessage).toBe(0);
      }

      return result;
    };

    // Monitor API responses for errors
    const inspectResponse = async (response: Response) => {
      const url = response.url();
      const status = response.status();

      if (url.includes("/api/") && status >= 400) {
        const method = response.request().method().toUpperCase();
        const path = new URL(url).pathname;
        const observed: ObservedHttpError = {
          method,
          path,
          status,
          statusText: response.statusText(),
          responseBody: await getResponseBody(response, `${method} ${path}`),
        };

        if (status < 500) {
          if (clientErrors.length < MAX_CLIENT_ERROR_DIAGNOSTICS) {
            clientErrors.push(observed);
          }
        } else {
          observeServerError(serverErrorContract, observed);
        }
      }

      // Monitor event delivery endpoints for error messages (streaming/polling/direct)
      if (
        status === 200 &&
        (url.includes("/events?event_delivery=") ||
          url.includes("/build/") ||
          url.includes("/run/"))
      ) {
        try {
          const headers = response.headers();
          const contentType = (headers["content-type"] || "").toLowerCase();
          const streamingContentHints = [
            "text/event-stream",
            "application/grpc",
            "application/octet-stream",
            "application/x-ndjson",
          ];
          const isStreamLike = streamingContentHints.some((hint) =>
            contentType.includes(hint),
          );
          if (isStreamLike) {
            return;
          }

          const method = response.request().method().toUpperCase();
          const path = new URL(url).pathname;
          const bodyResult = await readResponseBodyWithTimeout(response, {
            timeoutMs: RESPONSE_BODY_READ_TIMEOUT_MS,
            label: `${method} ${path}`,
          });
          if (bodyResult.status !== "success") {
            console.warn(`${bodyResult.diagnostic} Skipping body inspection.`);
            return;
          }
          const responseBody = bodyResult.body;
          if (!responseBody) {
            return;
          }

          // Try to parse as JSON and extract error details
          let errorPreview: string | null = null;
          let hasError = false;

          try {
            const lines = responseBody.split("\n");
            for (const line of lines) {
              if (line.trim()) {
                try {
                  const json = JSON.parse(line);

                  // Check for error in params field (build errors)
                  if (json.data?.build_data?.params?.startsWith("Error")) {
                    errorPreview = json.data.build_data.params;
                    hasError = true;
                    break;
                  }

                  // Check for error: true (not error: false)
                  if (json.data?.error === true || json.error === true) {
                    const errMsg =
                      json.data?.error_message ||
                      json.error_message ||
                      "Unknown error";
                    errorPreview = errMsg;
                    hasError = true;
                    break;
                  }
                } catch (_lineParseErr) {
                  // Skip lines that aren't valid JSON
                }
              }
            }
          } catch (_parseErr) {
            // Fallback to string search if JSON parsing completely fails
          }

          // Fallback: check for Python exceptions in the raw text
          if (!hasError) {
            const exceptionPatterns = [
              /NameError: .+/,
              /TypeError: .+/,
              /ValueError: .+/,
              /AttributeError: .+/,
              /ImportError: .+/,
              /KeyError: .+/,
              /An error occured .+/,
            ];

            for (const pattern of exceptionPatterns) {
              const match = responseBody.match(pattern);
              if (match) {
                errorPreview = match[0];
                hasError = true;
                break;
              }
            }
          }

          if (hasError && errorPreview) {
            const sanitizedErrorPreview = sanitizeResponseExcerpt(errorPreview);
            const error = {
              path: new URL(url).pathname,
              status: 200,
              statusText: "Flow Error",
              responseBody: sanitizedErrorPreview,
              type: "flow_error",
            };
            if (errors.length < MAX_FLOW_ERROR_DIAGNOSTICS) {
              errors.push(error);
            }

            // Event listeners are not awaited by Playwright. Record the error
            // here and fail deterministically after all response inspections
            // settle during fixture teardown.
          }
        } catch (e) {
          // Only ignore parsing errors, not our intentional throws
          if (
            e instanceof Error &&
            e.message.includes("Flow execution error")
          ) {
            throw e;
          }
          // Ignore parsing errors for event streams
        }
      }
    };

    const requestListener = (request: Request) => {
      if (shouldTrackApiRequest(request.url())) {
        pendingApiResponseStatuses.start(request);
        pendingApiRequestLifecycles.start(request);
      }
    };
    const responseListener = (response: Response) => {
      if (shouldTrackApiRequest(response.url())) {
        // HTTP status is final as soon as Playwright emits `response`; body
        // completion is tracked separately so a valid long-lived stream is not
        // mistaken for a request whose eventual 5xx status is still unknown.
        pendingApiResponseStatuses.finish(response.request());
      }
      if (
        shouldSettleApiRequestOnResponse(
          response.url(),
          response.headers()["content-type"] ?? "",
        )
      ) {
        // A genuine long-lived stream can remain open after its terminal event
        // has rendered. Its status is already final and inspectResponse below
        // still owns bounded error-body inspection. Finite API responses stay
        // tracked until requestfinished/requestfailed so body-triggered follow-
        // up requests remain visible to teardown.
        pendingApiRequestLifecycles.finish(response.request());
      }
      const inspection = inspectResponse(response)
        .catch((error: unknown) => {
          responseInspectionErrors.push(
            error instanceof Error
              ? error
              : new Error("Unknown response inspection failure"),
          );
        })
        .finally(() => {
          pendingResponseInspections.delete(inspection);
        });
      pendingResponseInspections.add(inspection);
    };
    const requestFinishedListener = (request: Request) => {
      if (shouldTrackApiRequest(request.url())) {
        pendingApiResponseStatuses.finish(request);
        pendingApiRequestLifecycles.finish(request);
      }
    };
    const requestFailedListener = (request: Request) => {
      if (shouldTrackApiRequest(request.url())) {
        pendingApiResponseStatuses.finish(request);
        pendingApiRequestLifecycles.finish(request);
      }
    };
    page.on("request", requestListener);
    page.on("response", responseListener);
    page.on("requestfinished", requestFinishedListener);
    page.on("requestfailed", requestFailedListener);

    await use(page as LangflowPage);
    // Freeze only the finite lifecycle set at the test boundary. Existing
    // requests must still finish, while teardown polling must not continually
    // extend this drain. Keep request/status observation active through the
    // tracker's quiet period so a causal follow-up request is still admitted.
    pendingApiRequestLifecycles.stop();
    await pendingApiRequestLifecycles.drain(API_REQUEST_DRAIN_TIMEOUT_MS);

    // The lifecycle quiet period has admitted any immediate follow-up request
    // into the status tracker. Close that admission boundary now, then drain
    // the already-admitted statuses while response listeners remain attached;
    // this preserves late 5xx inspection without admitting later polling.
    pendingApiResponseStatuses.stop();
    page.off("request", requestListener);
    await pendingApiResponseStatuses.drain(API_REQUEST_DRAIN_TIMEOUT_MS);
    const isAllowedPending = (request: Request) => {
      const { pathname } = new URL(request.url());
      const method = request.method().toUpperCase();
      return allowedPendingRequests.some(
        (allowed) =>
          pathname === allowed.path &&
          (allowed.method === undefined ||
            allowed.method.toUpperCase() === method),
      );
    };
    const unresolvedApiRequests = pendingApiResponseStatuses
      .snapshot()
      .filter((request) => !isAllowedPending(request));
    page.off("response", responseListener);
    page.off("requestfinished", requestFinishedListener);
    page.off("requestfailed", requestFailedListener);
    let responseInspectionDrainTimeoutId:
      | ReturnType<typeof setTimeout>
      | undefined;
    const responseInspectionDrainTimedOut = await Promise.race([
      Promise.allSettled([...pendingResponseInspections]).then(() => false),
      new Promise<true>((resolve) => {
        responseInspectionDrainTimeoutId = setTimeout(
          () => resolve(true),
          RESPONSE_INSPECTION_DRAIN_TIMEOUT_MS,
        );
      }),
    ]);
    if (responseInspectionDrainTimeoutId !== undefined) {
      clearTimeout(responseInspectionDrainTimeoutId);
    }
    if (responseInspectionDrainTimedOut) {
      responseInspectionErrors.push(
        new Error(
          `${pendingResponseInspections.size} response inspection(s) remained unresolved after ${RESPONSE_INSPECTION_DRAIN_TIMEOUT_MS}ms`,
        ),
      );
    }

    if (responseInspectionErrors.length > 0) {
      throw new Error(
        `Response inspection failed ${responseInspectionErrors.length} time(s): ${responseInspectionErrors[0].message}`,
      );
    }

    if (clientErrors.length > 0) {
      await testInfo.attach("api-4xx-responses", {
        body: Buffer.from(JSON.stringify(clientErrors, null, 2)),
        contentType: "application/json",
      });
    }

    const {
      unexpected: unexpectedServerErrors,
      missing: missingServerErrors,
      droppedUnexpected,
    } = getServerErrorContractFailures(serverErrorContract);
    if (
      unexpectedServerErrors.length > 0 ||
      missingServerErrors.length > 0 ||
      unresolvedApiRequests.length > 0
    ) {
      const unexpected = unexpectedServerErrors
        .map(
          ({ method, path, status, responseBody }) =>
            `  - unexpected ${method} ${path} -> ${status}: ${responseBody ?? "No response body"}`,
        )
        .join("\n");
      const missing = missingServerErrors
        .map(
          ({ method, path, status, count, observed }) =>
            `  - expected ${method} ${path} -> ${status} exactly ${count} time(s), observed ${observed}`,
        )
        .join("\n");
      const dropped =
        droppedUnexpected > 0
          ? `  - ${droppedUnexpected} additional unexpected 5xx response(s) omitted`
          : "";
      const unresolved = unresolvedApiRequests.length
        ? [
            `  - ${unresolvedApiRequests.length} API request(s) remained unresolved after ${API_REQUEST_DRAIN_TIMEOUT_MS}ms:`,
            ...unresolvedApiRequests
              .slice(0, MAX_PENDING_REQUEST_DIAGNOSTICS)
              .map(
                (request) =>
                  `    ${request.method().toUpperCase()} ${new URL(request.url()).pathname}`,
              ),
            unresolvedApiRequests.length > MAX_PENDING_REQUEST_DIAGNOSTICS
              ? `    ${unresolvedApiRequests.length - MAX_PENDING_REQUEST_DIAGNOSTICS} additional request(s) omitted`
              : "",
          ]
            .filter(Boolean)
            .join("\n")
        : "";
      const hasServerErrors =
        unexpectedServerErrors.length > 0 || missingServerErrors.length > 0;
      throw new Error(
        [
          hasServerErrors
            ? "Server-error contract failed:"
            : "API requests did not settle before teardown:",
          unexpected,
          dropped,
          missing,
          unresolved,
          hasServerErrors
            ? "Register intentional failures with page.expectServerError({ method, path, status, count })."
            : "If the request is deliberately left in flight (e.g. a delayed route mock holding a loading state), declare it with page.expectPendingRequest({ method, path }).",
        ]
          .filter(Boolean)
          .join("\n"),
      );
    }

    // Check for errors and fail test if not allowed
    if (errors.length > 0) {
      const flowErrors = errors.filter((e) => e.type === "flow_error");

      // Fail the test if flow errors occurred and weren't allowed
      if (flowErrors.length > 0 && !allowFlowErrors) {
        const errorDetails = flowErrors
          .map((e) => {
            const bodyPreview = e.responseBody
              ? e.responseBody.substring(0, 300)
              : "No response body";
            return `\n  - ${e.path}\n    ${bodyPreview}`;
          })
          .join("\n");

        throw new Error(
          `Test failed due to ${flowErrors.length} flow execution error(s):${errorDetails}\n\n` +
            `If this error is expected, call page.allowFlowErrors() at the start of your test.`,
        );
      }
    }
  },
});

export { expect };

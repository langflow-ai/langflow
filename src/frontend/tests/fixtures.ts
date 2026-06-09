// tests/fixtures.ts

import { test as base, expect, Page } from "@playwright/test";
import type { ICheckerResult } from "accessibility-checker";
import * as aChecker from "accessibility-checker";
import "./playwrightCoverage";
import {
  buildA11yScanLabel,
  buildA11ySummaryAttachment,
  formatA11yFailure,
  isCheckerReport,
} from "./utils/accessibility-checker";
import type { LangflowPage } from "./utils/types";

export type { LangflowPage } from "./utils/types";

const RUN_A11Y = process.env.RUN_A11Y === "true";
const RUN_A11Y_ASSERT = process.env.RUN_A11Y_ASSERT === "true";

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
    async ({}, use) => {
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
      url: string;
      status: number;
      statusText: string;
      responseBody?: string;
      type?: string;
    }> = [];

    // Flag to allow flow errors (for tests that expect errors)
    let allowFlowErrors = false;

    // Add helper method to page context — see LangflowPage type in utils/types.ts
    (page as Page & { allowFlowErrors?: () => void }).allowFlowErrors = () => {
      allowFlowErrors = true;
    };

    let a11yScanIndex = 0;
    (
      page as Page & {
        runA11yScan?: (label: string) => Promise<ICheckerResult | null>;
      }
    ).runA11yScan = async (label: string) => {
      if (!RUN_A11Y) {
        return null;
      }

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
        const returnCode = aChecker.assertCompliance(result.report);
        const failureMessage = formatA11yFailure(scanLabel, result.report);

        expect(returnCode, failureMessage).toBe(0);
      }

      return result;
    };

    // Monitor API responses for errors
    page.on("response", async (response) => {
      const url = response.url();
      const status = response.status();

      // Log 400/404/422/500 API errors (ignore auth endpoints)
      if (
        url.includes("/api/") &&
        (status === 400 || status === 404 || status === 422 || status === 500)
      ) {
        const isAuth =
          url.includes("/login") ||
          url.includes("/refresh") ||
          url.includes("/auto_login") ||
          url.includes("/logout");
        if (!isAuth) {
          let responseBody: string | undefined;
          try {
            responseBody = await response.text();
          } catch (_e) {
            responseBody = "Could not read response";
          }
          errors.push({
            url,
            status,
            statusText: response.statusText(),
            responseBody,
            type: "http_error",
          });
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

          const READ_BODY_TIMEOUT_MS = 2000;
          const bodyTimeoutToken = Symbol("response-body-timeout");
          let responseBody: string | undefined;
          let timeoutId: ReturnType<typeof setTimeout> | undefined;

          try {
            const bodyResult = await Promise.race([
              response.text(),
              new Promise<symbol>((resolve) => {
                timeoutId = setTimeout(
                  () => resolve(bodyTimeoutToken),
                  READ_BODY_TIMEOUT_MS,
                );
              }),
            ]);

            if (timeoutId) {
              clearTimeout(timeoutId);
              timeoutId = undefined;
            }

            if (bodyResult === bodyTimeoutToken) {
              console.warn(
                `Timed out reading response body for ${url}; skipping body inspection.`,
              );
              return;
            }

            if (typeof bodyResult !== "string") {
              return;
            }

            responseBody = bodyResult;
          } catch (bodyReadErr) {
            if (timeoutId) {
              clearTimeout(timeoutId);
              timeoutId = undefined;
            }
            console.warn(
              `Failed to read response body for ${url}; skipping body inspection.`,
              bodyReadErr,
            );
            return;
          }

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
            const error = {
              url,
              status: 200,
              statusText: "Flow Error",
              responseBody: errorPreview,
              type: "flow_error",
            };
            errors.push(error);

            // Fail immediately if flow errors are not allowed
            if (!allowFlowErrors) {
              const errorMessage =
                `Flow execution error detected during test:\n\n` +
                `URL: ${url}\n` +
                `Error: ${errorPreview}\n\n` +
                `If this error is expected, call page.allowFlowErrors() at the start of your test.`;

              throw new Error(errorMessage);
            }
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
    });

    await use(page as LangflowPage);

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
            return `\n  - ${e.url}\n    ${bodyPreview}`;
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

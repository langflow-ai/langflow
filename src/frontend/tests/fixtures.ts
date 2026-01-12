// tests/fixtures.ts
import { test as base, expect } from "@playwright/test";

// Extend test to log backend errors
export const test = base.extend({
  page: async ({ page }, use) => {
    const errors: Array<{
      url: string;
      status: number;
      statusText: string;
      responseBody?: string;
      type?: string;
    }> = [];

    // Flag to allow flow errors (for tests that expect errors)
    let allowFlowErrors = false;

    // Add helper method to page context
    (page as any).allowFlowErrors = () => {
      allowFlowErrors = true;
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
          console.log(
            `🚨 Backend Error: ${status} ${response.statusText()} - ${url}`,
          );
          let responseBody: string | undefined;
          try {
            responseBody = await response.text();
            console.log(`   Response: ${responseBody}`);
          } catch (e) {
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
            console.log(
              `Skipping streaming response body parsing for ${url} (${contentType || "unknown content-type"})`,
            );
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
                } catch (lineParseErr) {
                  // Skip lines that aren't valid JSON
                }
              }
            }
          } catch (parseErr) {
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
            console.log(`🚨 Flow Error Detected in Event Stream - ${url}`);
            console.log(`   Error: ${errorPreview}`);

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

              // Use page.close() to fail the test immediately
              page.emit("pageerror", new Error(errorMessage));
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

    await use(page);

    // Check for errors and fail test if not allowed
    if (errors.length > 0) {
      const flowErrors = errors.filter((e) => e.type === "flow_error");
      const httpErrors = errors.filter((e) => e.type === "http_error");

      console.log(`\n📋 Found ${errors.length} backend error(s) during test`);

      if (flowErrors.length > 0) {
        console.log(
          `   ⚠️  ${flowErrors.length} flow execution error(s) detected`,
        );
      }
      if (httpErrors.length > 0) {
        console.log(`   ⚠️  ${httpErrors.length} HTTP error(s) detected`);
      }

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

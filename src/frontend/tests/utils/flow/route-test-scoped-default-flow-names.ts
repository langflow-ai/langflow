import type { Page, TestInfo } from "@playwright/test";

const DEFAULT_FLOW_NAME = /^New Flow(?: \(\d+\))?$/;

/**
 * Give fixture-created default flows a test-specific name.
 *
 * The product computes `New Flow (n)` from a client-side inventory snapshot.
 * Parallel tests can choose the same suffix before either POST commits, so
 * suites that do not exercise naming should isolate those generated names.
 */
export async function routeTestScopedDefaultFlowNames(
  page: Page,
  testInfo: TestInfo,
  prefix: string,
): Promise<void> {
  let flowCreationIndex = 0;
  await page.route("**/api/v1/flows/", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.continue();
      return;
    }

    const body = request.postDataJSON() as Record<string, unknown>;
    if (typeof body.name !== "string" || !DEFAULT_FLOW_NAME.test(body.name)) {
      await route.continue();
      return;
    }

    await route.continue({
      postData: JSON.stringify({
        ...body,
        name: `${prefix}-${testInfo.testId}-${testInfo.retry}-${flowCreationIndex++}`,
      }),
    });
  });
}

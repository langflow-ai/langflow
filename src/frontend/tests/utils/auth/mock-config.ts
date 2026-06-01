import type { Page } from "@playwright/test";

/**
 * Override fields returned by /api/v1/config. The mock is "merge-shaped":
 * everything in `overrides` replaces the matching field in the response;
 * the rest is whatever the route originally returned.
 *
 * Use with `page.allowFlowErrors()` if the mock returns an `error: true`
 * shape — fixtures.ts treats those as flow execution errors and fails
 * the test unless explicitly allowed.
 */
export async function mockConfig(
  page: Page,
  overrides: Record<string, unknown>,
): Promise<void> {
  await page.route("**/api/v1/config", async (route) => {
    let baseBody: Record<string, unknown> = {};
    try {
      const response = await route.fetch();
      baseBody = await response.json();
    } catch {
      // First-load: backend may not be reachable yet — start from empty.
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...baseBody, ...overrides }),
    });
  });
}

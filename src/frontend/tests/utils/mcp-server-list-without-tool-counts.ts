import type { Page } from "@playwright/test";

/**
 * Keep structural MCP UI tests from executing every configured server merely
 * to decorate the list with tool counts. Tool discovery is exercised against
 * the checked-in loopback MCP fixture in the focused interaction tests.
 */
export async function useMcpServerListWithoutToolCounts(
  page: Page,
): Promise<void> {
  await page.route(
    /\/api\/v2\/mcp\/servers\?[^#]*action_count=true/,
    async (route) => {
      const url = new URL(route.request().url());
      url.searchParams.set("action_count", "false");
      const response = await route.fetch({ url: url.toString() });
      await route.fulfill({ response });
    },
  );
}

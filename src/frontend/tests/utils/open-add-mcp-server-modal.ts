import type { Page } from "@playwright/test";

export async function openAddMcpServerModal(page: Page) {
  // Try the simple button first (when no servers exist)
  const simpleButton = page.getByTestId("add-mcp-server-simple-button");
  if (await simpleButton.isVisible({ timeout: 1000 }).catch(() => false)) {
    await simpleButton.click();
  } else {
    // Otherwise use the dropdown
    await page.getByTestId("mcp-server-dropdown").click({ timeout: 3000 });
    await page.getByText("Add MCP Server", { exact: true }).click({
      timeout: 5000,
    });
  }

  await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
    state: "visible",
    timeout: 30000,
  });
}

import type { Page } from "@playwright/test";

export async function openAddMcpServerModal(
  page: Page,
  { source = "component" }: { source?: "component" | "sidebar" } = {},
) {
  const componentTriggers = [
    '[data-testid="add-mcp-server-simple-button"]:visible:not([disabled])',
    '[data-testid="mcp-server-dropdown"]:visible:not([disabled])',
  ];
  const sidebarTriggers = [
    '[data-testid="sidebar-add-mcp-server-button"]:visible:not([disabled])',
    '[data-testid="add-mcp-server-button-sidebar"]:visible:not([disabled])',
  ];
  const availableTrigger = page
    .locator(
      (source === "component" ? componentTriggers : sidebarTriggers).join(", "),
    )
    .first();
  await availableTrigger.waitFor({ state: "visible", timeout: 30_000 });

  const testId = await availableTrigger.getAttribute("data-testid");
  await availableTrigger.click();
  if (testId === "mcp-server-dropdown") {
    await page.getByText("Add MCP Server", { exact: true }).last().click({
      timeout: 30_000,
    });
  }

  await page.waitForSelector('[data-testid="add-mcp-server-button"]', {
    state: "visible",
    timeout: 30000,
  });
}

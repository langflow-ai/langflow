import type { Page } from "@playwright/test";

export const LOCAL_MCP_SERVER_ARGS = [
  "tests/fixtures/mcp-loopback-server.py",
  "--transport",
  "stdio",
  "--tool-set",
  "fetch",
];

/** Configure the checked-in MCP server with the allowlisted Python executable. */
export async function fillLocalMcpServerCommand(page: Page): Promise<void> {
  await page.getByTestId("stdio-command-input").fill("python");

  for (const [index, argument] of LOCAL_MCP_SERVER_ARGS.entries()) {
    if (index > 0) await page.getByTestId("input-list-plus-btn_-0").click();
    await page.getByTestId(`stdio-args_${index}`).fill(argument);
  }
}

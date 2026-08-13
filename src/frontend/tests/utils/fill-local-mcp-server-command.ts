import type { Page } from "@playwright/test";

export const LOCAL_MCP_SERVER_ARGS = [
  "run",
  "python",
  "tests/fixtures/mcp-loopback-server.py",
  "--transport",
  "stdio",
  "--tool-set",
  "fetch",
];

/** Configure a checked-in MCP server; `uv run` uses the existing lock/env only. */
export async function fillLocalMcpServerCommand(page: Page): Promise<void> {
  await page.getByTestId("stdio-command-input").fill("uv");

  for (const [index, argument] of LOCAL_MCP_SERVER_ARGS.entries()) {
    if (index > 0) await page.getByTestId("input-list-plus-btn_-0").click();
    await page.getByTestId(`stdio-args_${index}`).fill(argument);
  }
}

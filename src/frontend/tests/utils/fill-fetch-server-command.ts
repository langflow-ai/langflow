import type { Page } from "@playwright/test";

// uvx resolves each stdio server into its own environment, and mcp-server-fetch still
// declares an unbounded `mcp>=1.1.3`. The 2.0 SDK renamed `McpError`, so an unconstrained
// resolve installs a release the server cannot import and it exposes no tools. Pin the SDK
// the same way Langflow pins it for the servers it launches itself.
export const FETCH_SERVER_ARGS = ["--with", "mcp~=1.28", "mcp-server-fetch"];

/** Fill the stdio command and argument rows that launch mcp-server-fetch. */
export async function fillFetchServerCommand(page: Page) {
  await page.getByTestId("stdio-command-input").fill("uvx");

  for (const [index, arg] of FETCH_SERVER_ARGS.entries()) {
    if (index > 0) {
      await page.getByTestId("input-list-plus-btn_-0").click();
    }
    await page.getByTestId(`stdio-args_${index}`).fill(arg);
  }
}

// The MCP server check (api/v2/mcp.py `check_server`) reports failures as
// English sentences. Translate the fixed ones and the sentence around the
// prefixed ones; the underlying exception text stays as the server sent it.
const EXACT: Readonly<Record<string, string>> = {
  "No tools found": "mcp.servers.statusNoTools",
  "Timeout when checking server tools": "mcp.servers.errorTimeout",
};

// Longest prefix first: "Configuration data error" before "Configuration error".
const PREFIXED: ReadonlyArray<readonly [string, string]> = [
  ["Configuration data error: ", "mcp.servers.errorConfigurationData"],
  ["Configuration error: ", "mcp.servers.errorConfiguration"],
  ["Connection failed: ", "mcp.servers.errorConnection"],
  ["System error: ", "mcp.servers.errorSystem"],
  ["Runtime error: ", "mcp.servers.errorRuntime"],
  ["Error loading server: ", "mcp.servers.errorLoading"],
];

/** The slice of i18next's `t` this helper needs. */
export type Translate = (key: string, options?: { detail: string }) => string;

export function serverErrorText(error: string, t: Translate): string {
  const exact = EXACT[error];
  if (exact) return t(exact);
  for (const [prefix, key] of PREFIXED) {
    if (error.startsWith(prefix)) {
      return t(key, { detail: error.slice(prefix.length) });
    }
  }
  return error;
}

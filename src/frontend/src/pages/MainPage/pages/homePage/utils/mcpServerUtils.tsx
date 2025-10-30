import { parseString } from "@/utils/stringManipulation";

type RawFlow = {
  id: string;
  action_name?: string;
  action_description?: string;
  name?: string;
  description?: string;
  mcp_enabled?: boolean;
};

export type ToolFlow = {
  id: string;
  name: string;
  description: string;
  display_name?: string;
  display_description?: string;
  status: boolean;
  tags?: string[];
};

type InstalledClient = { installed?: boolean; name?: string };

export const MAX_MCP_SERVER_NAME_LENGTH = 64;

export const autoInstallers = [
  { name: "cursor", title: "Cursor", icon: "Cursor" },
  { name: "claude", title: "Claude", icon: "Claude" },
  { name: "windsurf", title: "Windsurf", icon: "Windsurf" },
];

export const operatingSystemTabs = [
  { name: "macoslinux", title: "macOS/Linux", icon: "FaApple" },
  { name: "windows", title: "Windows", icon: "FaWindows" },
  { name: "wsl", title: "WSL", icon: "FaLinux" },
];

export const getCommandForPlatform = (platform?: string) =>
  platform === "windows" ? "cmd" : platform === "wsl" ? "wsl" : "uvx";

export const getServerName = (
  folderName?: string,
  maxLen = MAX_MCP_SERVER_NAME_LENGTH,
) => {
  const name =
    folderName?.trim() && folderName.trim().length > 0
      ? folderName.trim()
      : "project";
  return `lf-${parseString(name, [
    "snake_case",
    "no_blank",
    "lowercase",
    "sanitize_mcp_name",
  ]).slice(0, maxLen - 3)}`;
};

export const getAuthHeaders = ({
  enableComposer,
  authType,
  isAutoLogin,
  apiKey,
}: {
  enableComposer: boolean;
  authType?: string | null;
  isAutoLogin: boolean;
  apiKey?: string;
}): string => {
  if (!enableComposer) {
    if (isAutoLogin) return "";
    return `"--headers","x-api-key","${apiKey ?? "YOUR_API_KEY"}"`;
  }
  if (!authType || authType === "none") return "";
  if (authType === "apikey")
    return `"--headers","x-api-key","${apiKey ?? "YOUR_API_KEY"}"`;
  return "";
};

export const buildMcpServerJson = (opts: {
  folderName?: string;
  selectedPlatform?: string;
  apiUrl: string;
  isOAuthProject: boolean;
  authHeadersFragment: string;
  maxNameLength?: number;
}): string => {
  const {
    folderName,
    selectedPlatform,
    apiUrl,
    isOAuthProject,
    authHeadersFragment,
    maxNameLength = MAX_MCP_SERVER_NAME_LENGTH,
  } = opts;

  const serverName = getServerName(folderName, maxNameLength);
  const command = getCommandForPlatform(selectedPlatform);
  const proxy = isOAuthProject ? '"mcp-composer"' : '"mcp-proxy"';
  const composerArgs = isOAuthProject ? ["--mode", "stdio", "--sse-url"] : [];
  const composerTail = isOAuthProject
    ? ["--disable-composer-tools", "--client_auth_type", "oauth"]
    : [];

  // Build args as an array of fragments, keeping each argument separate so we can
  // render them one-per-line and avoid stray commas or blank entries when some
  // fragments are empty.
  const argsParts: string[] = [];

  if (selectedPlatform === "windows") {
    argsParts.push(`"/c"`, `"uvx"`);
  } else if (selectedPlatform === "wsl") {
    argsParts.push(`"uvx"`);
  }
  argsParts.push(proxy);
  if (authHeadersFragment && authHeadersFragment.trim() !== "") {
    const matches = Array.from(authHeadersFragment.matchAll(/"([^"]*)"/g)).map(
      (m) => `"${m[1]}"`,
    );
    if (matches.length) argsParts.push(...matches);
  }
  if (composerArgs.length) argsParts.push(...composerArgs.map((a) => `"${a}"`));
  argsParts.push(`"${apiUrl}"`);
  if (composerTail.length) argsParts.push(...composerTail.map((a) => `"${a}"`));
  const argsString = argsParts.join(",\n        ");

  return `{
  "mcpServers": {
    "${serverName}": {
      "command": "${command}",
      "args": [
        ${argsString}
      ]
    }
  }
}`;
};

export const mapFlowsToTools = (flows: RawFlow[] = []): ToolFlow[] =>
  flows.map((flow) => ({
    id: flow.id,
    name: flow.action_name ?? "",
    description: flow.action_description ?? "",
    display_name: flow.name,
    display_description: flow.description,
    status: flow.mcp_enabled ?? false,
    tags: [flow.name ?? ""],
  }));

export const extractInstalledClientNames = (
  installedData?: InstalledClient[],
): string[] =>
  installedData
    ?.filter((c) => c.installed && c.name)
    .map((c) => c.name as string) ?? [];

export const createSyntaxHighlighterStyle = (isDarkMode: boolean) => ({
  "hljs-string": { color: isDarkMode ? "hsla(158, 64%, 52%, 1)" : "#059669" },
  "hljs-attr": { color: isDarkMode ? "hsla(329, 86%, 70%, 1)" : "#DB2777" },
});

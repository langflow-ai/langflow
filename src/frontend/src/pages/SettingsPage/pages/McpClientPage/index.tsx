import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { cn } from "@/utils/utils";

type AgentTab = "bob" | "claude-code";

const agents: { id: AgentTab; title: string; icon: string }[] = [
  { id: "bob", title: "Bob (IBM)", icon: "Bot" },
  { id: "claude-code", title: "Claude Code", icon: "Terminal" },
];

function buildMcpJson(serverUrl: string): string {
  return JSON.stringify(
    {
      mcpServers: {
        langflow: {
          command: "uvx",
          args: ["--from", "lfx", "lfx-mcp"],
          env: {
            LANGFLOW_SERVER_URL: serverUrl,
            LANGFLOW_API_KEY: "YOUR_API_KEY", // pragma: allowlist secret
          },
        },
      },
    },
    null,
    2,
  );
}

function getAgentInstructions(agent: AgentTab): {
  configPath: string;
  steps: string[];
} {
  switch (agent) {
    case "bob":
      return {
        configPath: "~/.bob/settings/mcp_settings.json",
        steps: [
          "Open Bob and go to Settings > MCP",
          'Click "Edit Global MCP" (or "Edit Project MCP" for per-project setup)',
          "Paste the JSON config below and save",
        ],
      };
    case "claude-code":
      return {
        configPath: "",
        steps: [
          "Run the command below in your terminal:",
          "Or add the JSON config to ~/.claude.json manually",
        ],
      };
  }
}

function getClaudeCodeCommand(serverUrl: string): string {
  return `claude mcp add langflow -- uvx --from lfx lfx-mcp \\
  -e LANGFLOW_SERVER_URL=${serverUrl} \\
  -e LANGFLOW_API_KEY=YOUR_API_KEY`;
}

export default function McpClientPage() {
  const [selectedAgent, setSelectedAgent] = useState<AgentTab>("bob");
  const [isCopied, setIsCopied] = useState(false);

  const { host, protocol } = customGetHostProtocol();
  const serverUrl = `${protocol}//${host}`;

  const mcpJson = useMemo(() => buildMcpJson(serverUrl), [serverUrl]);
  const instructions = getAgentInstructions(selectedAgent);
  const claudeCommand = useMemo(
    () => getClaudeCodeCommand(serverUrl),
    [serverUrl],
  );

  const copyToClipboard = useCallback((text: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 1000);
    });
  }, []);

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Langflow MCP Client
            <ForwardedIconComponent
              name="Mcp"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Connect coding agents to build and run flows on this Langflow
            instance.
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-row justify-start border-b border-border">
          {agents.map((agent) => (
            <Button
              unstyled
              key={agent.id}
              className={cn(
                "flex h-6 flex-row items-end gap-2 text-nowrap border-b-2 border-b-transparent px-3 py-2 text-[13px] font-medium",
                selectedAgent === agent.id
                  ? "border-b-2 border-black dark:border-b-white"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => {
                setSelectedAgent(agent.id);
                setIsCopied(false);
              }}
            >
              <ForwardedIconComponent
                name={agent.icon}
                className="h-4 w-4"
                aria-hidden="true"
              />
              <span>{agent.title}</span>
            </Button>
          ))}
        </div>

        <div className="flex flex-col gap-3">
          <ol className="list-decimal pl-5 text-sm text-muted-foreground space-y-1">
            {instructions.steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>

          {selectedAgent === "claude-code" && (
            <div className="relative overflow-hidden rounded-lg border border-border bg-background">
              <div className="absolute right-3 top-3">
                <Button
                  unstyled
                  size="icon"
                  className="h-4 w-4 text-muted-foreground hover:text-foreground"
                  onClick={() => copyToClipboard(claudeCommand)}
                >
                  <ForwardedIconComponent
                    name={isCopied ? "Check" : "Copy"}
                    className="h-4 w-4"
                    aria-hidden="true"
                  />
                </Button>
              </div>
              <pre className="overflow-x-auto p-4 text-[13px]">
                <code>{claudeCommand}</code>
              </pre>
            </div>
          )}

          {instructions.configPath && (
            <p className="text-sm text-muted-foreground">
              Config file:{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-[13px]">
                {instructions.configPath}
              </code>
            </p>
          )}

          <div className="relative overflow-hidden rounded-lg border border-border bg-background">
            <div className="absolute right-3 top-3">
              <Button
                unstyled
                size="icon"
                className="h-4 w-4 text-muted-foreground hover:text-foreground"
                onClick={() => copyToClipboard(mcpJson)}
              >
                <ForwardedIconComponent
                  name={isCopied ? "Check" : "Copy"}
                  className="h-4 w-4"
                  aria-hidden="true"
                />
              </Button>
            </div>
            <pre className="overflow-x-auto p-4 text-[13px]">
              <code>{mcpJson}</code>
            </pre>
          </div>

          <div className="flex items-start gap-2 rounded-md bg-accent-amber px-3 py-2 text-sm text-accent-amber-foreground">
            <ForwardedIconComponent
              name="Info"
              className="mt-0.5 h-4 w-4 shrink-0"
            />
            <span>
              If you don't provide an API key, the agent will need to log in
              using the <code className="font-semibold">login</code> tool with
              your username and password. You can generate an API key in{" "}
              <Link
                to="/settings/api-keys"
                className="underline hover:text-foreground"
              >
                API Keys settings
              </Link>
              .
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

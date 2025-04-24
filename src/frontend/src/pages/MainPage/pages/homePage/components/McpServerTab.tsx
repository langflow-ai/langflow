import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ToolsComponent from "@/components/core/parameterRenderComponent/components/ToolsComponent";
import { Button } from "@/components/ui/button";
import { createApiKey } from "@/controllers/API";
import {
  useGetFlowsMCP,
  usePatchFlowsMCP,
} from "@/controllers/API/queries/mcp";
import useTheme from "@/customization/hooks/use-custom-theme";
import useAuthStore from "@/stores/authStore";
import { useFolderStore } from "@/stores/foldersStore";
import { MCPSettingsType } from "@/types/mcp";
import { parseString } from "@/utils/stringManipulation";
import { cn } from "@/utils/utils";
import { useState } from "react";
import Markdown from "react-markdown";
import { useParams } from "react-router-dom";
import SyntaxHighlighter from "react-syntax-highlighter";
import rehypeMathjax from "rehype-mathjax";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

const McpServerTab = ({ folderName }: { folderName: string }) => {
  const [selectedMode, setSelectedMode] = useState<string>("Cursor");
  const isDarkMode = useTheme().dark;
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const projectId = folderId ?? myCollectionId ?? "";
  const [isCopied, setIsCopied] = useState(false);
  const [apiKey, setApiKey] = useState<string>("");
  const [isGeneratingApiKey, setIsGeneratingApiKey] = useState(false);

  const { data: flowsMCP } = useGetFlowsMCP({ projectId });
  const { mutate: patchFlowsMCP } = usePatchFlowsMCP({ project_id: projectId });

  const isAutoLogin = useAuthStore((state) => state.autoLogin);

  const flowsMCPData = flowsMCP?.map((flow) => ({
    id: flow.id,
    name: flow.action_name,
    description: flow.action_description,
    display_name: flow.name,
    display_description: flow.description,
    status: flow.mcp_enabled,
    tags: [flow.name],
  }));

  const syntaxHighlighterStyle = {
    "hljs-string": {
      color: isDarkMode ? "hsla(158, 64%, 52%, 1)" : "#059669", // Accent Green
    },
    "hljs-attr": {
      color: isDarkMode ? "hsla(329, 86%, 70%, 1)" : "#DB2777", // Accent Pink
    },
  };

  const host = window.location.host;
  const protocol = window.location.protocol;
  const apiUrl = `${protocol}//${host}/api/v1/mcp/project/${projectId}/sse`;

  const MCP_SERVER_JSON = `{
  "mcpServers": {
    "langflow-${parseString(folderName ?? "project", ["snake_case", "no_blank", "lowercase"])}": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "${apiUrl}"
      ]
    }
  }
}`;

  const MCP_SERVER_JSON_WITH_API_KEY = `{
  "mcpServers": {
    "langflow-${parseString(folderName ?? "project", ["snake_case", "no_blank", "lowercase"])}": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "${apiUrl}",
        "--header",
        "x-api-key:${apiKey || "YOUR_API_KEY"}"
      ]
    }
  }
}`;

  const MCP_SERVER_TUTORIAL = {
    Claude: `- Open **File** -> **Settings**
- Click on **Developer**
- Click on **Edit Config**
- Paste the following JSON and save:`,
    Cursor: `- Open **Settings** -> **Cursor Settings**
- Click on **MCP**
- Click on **Add new global MCP server**
- Paste the following JSON and save:`,
    "Raw JSON": `- You need a **Langflow API key** to access the MCP server.`,
  };

  const copyToClipboard = () => {
    navigator.clipboard
      .writeText(MCP_SERVER_JSON)
      .then(() => {
        setIsCopied(true);
        setTimeout(() => {
          setIsCopied(false);
        }, 1000);
      })
      .catch((err) => console.error("Failed to copy text: ", err));
  };

  return (
    <div>
      <div className="text-md -mt-2 pb-2 font-bold">MCP Server</div>
      <div className="pb-4 text-xs text-muted-foreground">
        Access your Project's flows as Actions within a MCP Server. Learn how to
        <a
          className="text-accent-pink-foreground"
          href="https://docs.langflow.org/mcp-server/deploying-mcp-server"
          target="_blank"
          rel="noreferrer"
        >
          {" "}
          deploy your MCP server to the internet.
        </a>
      </div>
      <div className="flex flex-row">
        <div className="w-1/3">
          <div className="flex flex-row justify-between">
            <div className="text-sm font-normal">Flows/Actions</div>
          </div>
          <div className="flex flex-row flex-wrap gap-2 pt-2">
            <ToolsComponent
              value={flowsMCPData}
              title="MCP Server Actions"
              description="Select actions to add to this server"
              handleOnNewValue={(value) => {
                const flowsMCPData: MCPSettingsType[] = value.value.map(
                  (flow) => ({
                    id: flow.id,
                    action_name: flow.name,
                    action_description: flow.description,
                    mcp_enabled: flow.status,
                  }),
                );
                patchFlowsMCP(flowsMCPData);
              }}
              id="mcp-server-tools"
              button_description="Edit Actions"
              editNode={false}
              isAction
              disabled={false}
            />
          </div>
        </div>
        <div className="w-2/3 pl-4">
          <div className="rounded-lg border border-border">
            <div className="flex flex-row justify-start border-b border-border">
              {[
                { name: "Cursor", icon: "Cursor" },
                { name: "Claude", icon: "Claude" },
                { name: "Raw JSON", icon: "file-json" },
              ].map((item, index) => (
                <Button
                  unstyled
                  key={item.name}
                  className={`flex flex-row items-center gap-2 text-nowrap border-b-2 border-border border-b-transparent font-medium ${
                    selectedMode === item.name
                      ? "border-b-2 border-black dark:border-b-white"
                      : "text-muted-foreground hover:text-foreground"
                  } border-r border-r-border px-3 py-2 text-[13px]`}
                  onClick={() => setSelectedMode(item.name)}
                >
                  <ForwardedIconComponent
                    name={item.icon}
                    className="h-4 w-4"
                    aria-hidden="true"
                  />
                  {item.name}
                </Button>
              ))}
            </div>
            {(!isAutoLogin || selectedMode !== "Raw JSON") && (
              <div className="flex flex-row items-start justify-between border-b border-border p-1.5 px-4">
                {(selectedMode !== "Raw JSON" || !isAutoLogin) && (
                  <span className="py-2 text-[13px]">
                    <Markdown
                      remarkPlugins={[remarkGfm as any]}
                      rehypePlugins={[rehypeMathjax, rehypeRaw]}
                      className={cn(
                        "markdown prose flex w-fit max-w-full flex-col items-baseline text-[14px] font-normal word-break-break-word dark:prose-invert",
                      )}
                    >
                      {MCP_SERVER_TUTORIAL[selectedMode]}
                    </Markdown>
                  </span>
                )}

                {!isAutoLogin && (
                  <Button
                    size="sm"
                    className="my-2"
                    disabled={apiKey !== ""}
                    loading={isGeneratingApiKey}
                    onClick={() => {
                      setIsGeneratingApiKey(true);
                      createApiKey(`MCP Server ${folderName}`)
                        .then((res) => {
                          setApiKey(res["api_key"]);
                        })
                        .catch((err) => {})
                        .finally(() => {
                          setIsGeneratingApiKey(false);
                        });
                    }}
                  >
                    <span>
                      {apiKey === "" ? "Generate API key" : "API key generated"}
                    </span>
                  </Button>
                )}
              </div>
            )}

            <SyntaxHighlighter
              style={syntaxHighlighterStyle}
              CodeTag={({ children }) => (
                <div className="relative rounded-lg bg-background text-[13px]">
                  <Button
                    unstyled
                    size="icon"
                    className={cn(
                      "absolute right-4 top-4 h-4 w-4 text-muted-foreground hover:text-foreground",
                      selectedMode === "Cursor" && "top-[15px]",
                    )}
                    onClick={copyToClipboard}
                  >
                    <ForwardedIconComponent
                      name={isCopied ? "check" : "copy"}
                      className="h-4 w-4"
                      aria-hidden="true"
                    />
                  </Button>
                  <div className="overflow-x-auto p-4">{children}</div>
                </div>
              )}
              language="json"
            >
              {isAutoLogin ? MCP_SERVER_JSON : MCP_SERVER_JSON_WITH_API_KEY}
            </SyntaxHighlighter>
          </div>
        </div>
      </div>
    </div>
  );
};

export default McpServerTab;

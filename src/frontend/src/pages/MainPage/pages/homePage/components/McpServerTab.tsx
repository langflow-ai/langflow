import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ToolsComponent from "@/components/core/parameterRenderComponent/components/ToolsComponent";
import { Button } from "@/components/ui/button";
import {
  useGetFlowsMCP,
  usePatchFlowsMCP,
} from "@/controllers/API/queries/mcp";
import useTheme from "@/customization/hooks/use-custom-theme";
import { useFolderStore } from "@/stores/foldersStore";
import { MCPSettingsType } from "@/types/mcp";
import { cn } from "@/utils/utils";
import { useState } from "react";
import { useParams } from "react-router-dom";
import SyntaxHighlighter from "react-syntax-highlighter";

const McpServerTab = () => {
  const [selectedMode, setSelectedMode] = useState<string>("Cursor");
  const isDarkMode = useTheme().dark;
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const projectId = folderId ?? myCollectionId ?? "";

  const { data: flowsMCP, isLoading } = useGetFlowsMCP({ projectId });
  const { mutate: patchFlowsMCP } = usePatchFlowsMCP({ project_id: projectId });

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

  const MCP_SERVER_EXAMPLE = {
    Cursor: `{
      "Cursor": {
        "flow-id": {
          "name": "Example Cursor Flow",
          "description": "Short description of this cursor flow",
          "command": "run-flow.sh",
          "args": ["--some-flag"],
          "env": {
            "MCP_HOST": "http://127.0.0.1:7860"
          }     
        } 
      }
    }`,
    Claude: `{
      "Claude": {
        "flow-id": {
          "name": "Example Claude Flow",
          "description": "Short description of this claude flow",
          "command": "run-flow.sh",
          "args": ["--some-flag"],
          "env": {
            "MCP_HOST": "http://127.0.0.1:7860"
          }
        }
      }
    }`,
    "Raw JSON": `{
      "JSON": {
        "flow-id": {
          "name": "Example JSON Flow",
          "description": "Short description of this json flow",
          "command": "run-flow.sh",
          "args": ["--some-flag"],
          "env": {
            "MCP_HOST": "http://127.0.0.1:7860"
          }
        }
      }
    }`,
  };

  const copyToClipboard = () => {
    navigator.clipboard
      .writeText(MCP_SERVER_EXAMPLE[selectedMode])
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
              value={isLoading ? undefined : flowsMCPData}
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
            {selectedMode === "Cursor" && (
              <div className="flex flex-row items-center justify-between border-b border-border p-1.5 px-4">
                <span className="text-[13px]">
                  Add this server to Cursor config
                </span>
                <Button className="text-[13px]" size="sm">
                  Add to Client
                </Button>
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
                      name="copy"
                      className="h-4 w-4"
                      aria-hidden="true"
                    />
                  </Button>
                  <div className="p-4">{children}</div>
                </div>
              )}
              language="json"
            >
              {MCP_SERVER_EXAMPLE[selectedMode]}
            </SyntaxHighlighter>
          </div>
        </div>
      </div>
    </div>
  );
};

export default McpServerTab;

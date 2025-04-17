import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useTheme from "@/customization/hooks/use-custom-theme";
import { cn } from "@/utils/utils";
import { useState } from "react";
import SyntaxHighlighter from "react-syntax-highlighter";

const McpServerTab = () => {
  const [selectedMode, setSelectedMode] = useState<string>("Cursor");
  const isDarkMode = useTheme().dark;

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
            <div className="text-[13px] font-bold">Flows/Actions</div>
            <Button
              unstyled
              size="icon"
              className="flex items-center gap-2 text-[13px] text-muted-foreground hover:text-foreground"
            >
              <ForwardedIconComponent
                name="settings-2"
                className="h-4 w-4"
                aria-hidden="true"
              />{" "}
              Edit Actions
            </Button>
          </div>
          <div className="flex flex-row flex-wrap gap-2 pt-3">
            {false ? (
              <div className="flex w-full flex-col items-center justify-center rounded-lg border border-dashed border-border p-6">
                <div className="pb-2 text-xs text-muted-foreground">
                  No actions added to this server.
                </div>
                <Button className="h-9 text-[13px]">Add Actions</Button>
              </div>
            ) : (
              [
                "something",
                "something_else",
                "something_other",
                "something_new",
                "something_else_again",
                "something_other_again",
                "something_new_again",
              ].map((item) => (
                <div
                  key={item}
                  className="rounded-sm border border-muted bg-muted p-1 text-xs text-muted-foreground"
                >
                  {item}
                </div>
              ))
            )}
          </div>
        </div>
        <div className="w-2/3 pl-4">
          <div className="rounded-lg border border-border">
            <div className="flex flex-row justify-start">
              {[
                { name: "Cursor", icon: "Cursor" },
                { name: "Claude", icon: "Claude" },
                { name: "Raw JSON", icon: "file-json" },
              ].map((item, index) => (
                <Button
                  unstyled
                  key={item.name}
                  className={`flex flex-row items-center gap-2 text-nowrap border-b border-border ${
                    selectedMode === item.name
                      ? "border-b-2 border-black font-bold dark:border-white"
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
              <div className="w-full border-b border-border" />
            </div>
            <SyntaxHighlighter
              style={syntaxHighlighterStyle}
              CodeTag={({ children }) => (
                <div className="relative rounded-lg bg-background text-[13px]">
                  {selectedMode === "Cursor" && (
                    <div className="flex flex-row items-center justify-between border-b border-border p-1.5 px-4">
                      <span className="font-[Inter] text-[13px]">
                        Add this server to Cursor config
                      </span>
                      <Button className="font-[Inter] text-[13px]" size="sm">
                        Add to Client
                      </Button>
                    </div>
                  )}
                  <Button
                    unstyled
                    size="icon"
                    className={cn(
                      "absolute right-4 top-4 h-4 w-4 text-muted-foreground hover:text-foreground",
                      selectedMode === "Cursor" && "top-[65px]",
                    )}
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

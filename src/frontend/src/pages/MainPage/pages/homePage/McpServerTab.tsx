import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import React, { useEffect, useState } from "react";

const McpServerTab = () => {
  const [selectedMode, setSelectedMode] = useState<string>("Cursor");

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
      <div className="text-md pb-2 font-bold">MCP Server</div>
      <div className="pb-4 text-xs text-muted-foreground">
        Access your Project's flows as Actions within a MCP Server. Learn how to
        <a
          className="text-pink-500"
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
            {[
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
            ))}
          </div>
        </div>
        <div className="w-2/3 pl-4">
          <div className="rounded-lg border border-border">
            <div className="flex flex-row justify-start">
              {["Cursor", "Claude", "Raw JSON"].map((item, index) => (
                <Button
                  unstyled
                  key={item}
                  className={`flex flex-row items-center gap-2 text-nowrap border-b border-border ${
                    selectedMode === item
                      ? "border-b-2 border-white font-bold"
                      : ""
                  } border-r border-r-border p-2 text-[13px]`}
                  onClick={() => setSelectedMode(item)}
                >
                  <ForwardedIconComponent
                    name={"unknown"}
                    className="h-4 w-4"
                    aria-hidden="true"
                  />
                  {item}
                </Button>
              ))}
              <div className="w-full border-b border-border" />
            </div>
            <div className="p-4">
              {/* Use a <pre> tag for preserving whitespace and applying font */}
              <div className="whitespace-pre-wrap font-mono text-sm">
                {MCP_SERVER_EXAMPLE[selectedMode]}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default McpServerTab;

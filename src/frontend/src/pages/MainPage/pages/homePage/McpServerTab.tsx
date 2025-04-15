import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

const McpServerTab = () => {
  return (
    <div>
      <div className="text-md pb-2 font-bold">MCP Server</div>
      <div className="pb-4 text-xs text-muted-foreground">
        Access your Project’s flows as Actions within a MCP Server. Learn how to
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
              className="flex items-center gap-2 text-[13px] text-muted-foreground"
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
            <div className="flex flex-row justify-start gap-2 border-b border-border p-2">
              {["Cursor", "Claude", "Raw JSON"].map((item) => (
                <div key={item} className="flex flex-row items-center gap-2">
                  <ForwardedIconComponent
                    name={"unknown"}
                    className="h-4 w-4"
                    aria-hidden="true"
                  />
                  {item}
                </div>
              ))}
            </div>
            <div className="p-4">content</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default McpServerTab;

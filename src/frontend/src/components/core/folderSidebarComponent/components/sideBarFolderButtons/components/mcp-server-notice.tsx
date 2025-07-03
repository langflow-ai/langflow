import MCPLangflow from "@/assets/MCPLangflow.png";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { FC } from "react";

export const MCPServerNotice: FC<{
  handleDismissDialog: () => void;
}> = ({ handleDismissDialog }) => {
  const navigate = useCustomNavigate();
  return (
    <div className="relative flex flex-col gap-3 rounded-xl border p-4 shadow-md">
      <Button
        unstyled
        className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
        onClick={handleDismissDialog}
      >
        <ForwardedIconComponent name="X" className="h-5 w-5" />
      </Button>
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <div className="font-mono text-sm text-muted-foreground">New</div>
          <div className="">Projects as MCP Servers</div>
        </div>
        <img src={MCPLangflow} alt="MCP Notice Modal" className="rounded-xl" />
        <p className="text-sm text-secondary-foreground">
          Expose flows as tools from clients like Cursor or Claude.
        </p>
      </div>

      <div className="flex gap-3">
        <Button
          onClick={() => {
            navigate("/mcp");
            handleDismissDialog();
          }}
          className="w-full"
        >
          <span>Go to Server</span>
        </Button>
      </div>
    </div>
  );
};

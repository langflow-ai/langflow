import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import type { ForgeButtonProps } from "./types";

const ForgeButton = ({ onClick, isTerminalOpen }: ForgeButtonProps) => {
  return (
    <Button
      variant="primary"
      size="sm"
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 px-4 py-2",
        "bg-gradient-to-r from-violet-600 to-fuchsia-600",
        "hover:from-violet-500 hover:to-fuchsia-500",
        "border-0 text-white shadow-lg",
        "transition-all duration-200",
        isTerminalOpen && "ring-2 ring-fuchsia-400/50",
      )}
      data-testid="component-forge-btn"
    >
      <ForwardedIconComponent
        name="Sparkles"
        className="h-4 w-4"
        strokeWidth={2}
      />
      <span className="font-medium">Component Forge</span>
    </Button>
  );
};

export default ForgeButton;

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";
import { ASSISTANT_TITLE } from "../assistant-panel.constants";
import type { AssistantViewMode } from "../assistant-panel.types";

interface AssistantHeaderProps {
  onClose: () => void;
  onClearHistory: () => void;
  disabled?: boolean;
  viewMode: AssistantViewMode;
  onViewModeChange: (mode: AssistantViewMode) => void;
}

export function AssistantHeader({
  onClose,
  onClearHistory,
  disabled = false,
  viewMode,
  onViewModeChange,
}: AssistantHeaderProps) {
  return (
    <div className="flex h-12 items-center justify-between px-4">
      <h2 className="text-sm font-medium text-foreground">{ASSISTANT_TITLE}</h2>
      <div className="flex items-center gap-1">
        {/* View Mode Toggle */}
        <div className="flex items-center rounded-md border border-border bg-muted/50 p-0.5">
          <button
            type="button"
            onClick={() => onViewModeChange("sidebar")}
            className={cn(
              "flex h-6 w-6 items-center justify-center rounded transition-colors",
              viewMode === "sidebar"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
            title="Sidebar view"
          >
            <ForwardedIconComponent name="PanelLeft" className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => onViewModeChange("floating")}
            className={cn(
              "flex h-6 w-6 items-center justify-center rounded transition-colors",
              viewMode === "floating"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
            title="Floating view"
          >
            <ForwardedIconComponent name="Square" className="h-3.5 w-3.5" />
          </button>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild disabled={disabled}>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title="Options"
              disabled={disabled}
            >
              <ForwardedIconComponent
                name="MoreVertical"
                className="h-4 w-4 text-muted-foreground"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="z-[70]">
            <DropdownMenuItem onClick={onClearHistory}>
              <ForwardedIconComponent name="Trash2" className="mr-2 h-4 w-4" />
              Clear history
            </DropdownMenuItem>
            <DropdownMenuItem onClick={onClose}>
              <ForwardedIconComponent name="X" className="mr-2 h-4 w-4" />
              Close
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

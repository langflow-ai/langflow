import React, { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select-custom";
import { cn } from "@/utils/utils";

export interface SessionMoreMenuProps {
  onRename: () => void;
  onMessageLogs?: () => void;
  onDelete: () => void;
  showMessageLogs?: boolean;
  showDelete?: boolean;
  // Positioning props
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  sideOffset?: number;
  triggerClassName?: string;
  contentClassName?: string;
  isVisible?: boolean;
  tooltipContent?: string;
  tooltipSide?: "top" | "right" | "bottom" | "left";
}

const DEFAULT_SIDE_OFFSET = 4;

export function SessionMoreMenu({
  onRename,
  onMessageLogs,
  onDelete,
  showMessageLogs = true,
  showDelete = true,
  side = "bottom",
  align = "end",
  sideOffset = DEFAULT_SIDE_OFFSET,
  triggerClassName,
  contentClassName,
  isVisible = true,
  tooltipContent = "More options",
  tooltipSide = "left",
}: SessionMoreMenuProps) {
  const [selectValue, setSelectValue] = useState("");

  const handleValueChange = (value: string) => {
    setSelectValue(value);
    // Execute the action immediately
    switch (value) {
      case "rename":
        onRename();
        break;
      case "messageLogs":
        onMessageLogs?.();
        break;
      case "delete":
        onDelete();
        break;
    }
    setSelectValue("");
  };

  return (
    <div className="relative">
      <Select value={selectValue} onValueChange={handleValueChange}>
        <ShadTooltip
          styleClasses="z-50"
          side={tooltipSide}
          content={tooltipContent}
        >
          <SelectTrigger
            className={cn(
              "h-8 w-8 border-none bg-transparent p-2 rounded transition-colors text-muted-foreground hover:bg-accent hover:text-foreground focus:ring-0",
              !isVisible && "invisible group-hover:visible",
              triggerClassName,
            )}
            aria-label={tooltipContent}
            aria-haspopup="true"
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            <ForwardedIconComponent
              name="MoreVertical"
              className="h-4 w-4"
              aria-hidden="true"
            />
          </SelectTrigger>
        </ShadTooltip>
        <SelectContent
          side={side}
          align={align}
          sideOffset={sideOffset}
          className={cn("p-0", contentClassName)}
        >
          <SelectItem value="rename" className="session-more-menu-item">
            <div className="flex items-center">
              <ForwardedIconComponent
                name="SquarePen"
                className="mr-2 h-4 w-4"
              />
              Rename
            </div>
          </SelectItem>
          {showMessageLogs && (
            <SelectItem value="messageLogs" className="session-more-menu-item">
              <div className="flex items-center">
                <ForwardedIconComponent
                  name="Scroll"
                  className="mr-2 h-4 w-4"
                />
                Message logs
              </div>
            </SelectItem>
          )}
          {showDelete && (
            <SelectItem value="delete" className="session-more-menu-item">
              <div className="flex items-center text-status-red hover:text-status-red">
                <ForwardedIconComponent
                  name="Trash2"
                  className="mr-2 h-4 w-4"
                />
                Delete
              </div>
            </SelectItem>
          )}
        </SelectContent>
      </Select>
    </div>
  );
}

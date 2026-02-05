import { useState } from "react";
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
  onClearChat?: () => void;
  showMessageLogs?: boolean;
  showRename?: boolean;
  showDelete?: boolean;
  showClearChat?: boolean;
  // Positioning props
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  sideOffset?: number;
  triggerClassName?: string;
  contentClassName?: string;
  isVisible?: boolean;
  tooltipContent?: string;
  tooltipSide?: "top" | "right" | "bottom" | "left";
  dataTestid?: string;
  // Controlled state props
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

const DEFAULT_SIDE_OFFSET = 4;

export function SessionMoreMenu({
  onRename,
  onMessageLogs,
  onDelete,
  onClearChat,
  showMessageLogs = true,
  showRename = true,
  showDelete = true,
  showClearChat = false,
  side = "bottom",
  align = "end",
  sideOffset = DEFAULT_SIDE_OFFSET,
  triggerClassName,
  contentClassName,
  isVisible = true,
  tooltipContent = "More options",
  tooltipSide = "left",
  dataTestid,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: SessionMoreMenuProps) {
  const [selectValue, setSelectValue] = useState("");
  const [internalOpen, setInternalOpen] = useState(false);

  // Use controlled state if provided, otherwise use internal state
  const open = controlledOpen !== undefined ? controlledOpen : internalOpen;
  const setOpen = controlledOnOpenChange || setInternalOpen;

  const handleValueChange = (value: string) => {
    // Execute the action immediately
    switch (value) {
      case "rename":
        onRename();
        break;
      case "messageLogs":
        onMessageLogs?.();
        break;
      case "clearChat":
        onClearChat?.();
        break;
      case "delete":
        onDelete();
        break;
    }
    setOpen(false);
    setSelectValue("");
  };

  return (
    <div className="relative">
      <Select
        value={selectValue}
        onValueChange={handleValueChange}
        open={open}
        onOpenChange={setOpen}
      >
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
            data-testid={dataTestid}
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
          {showRename && (
            <SelectItem
              value="rename"
              className="session-more-menu-item"
              data-testid="rename-session-option"
            >
              <div className="flex items-center">
                <ForwardedIconComponent
                  name="SquarePen"
                  className="mr-2 h-4 w-4"
                />
                Rename
              </div>
            </SelectItem>
          )}
          {showMessageLogs && (
            <SelectItem
              value="messageLogs"
              className="session-more-menu-item"
              data-testid="message-logs-option"
            >
              <div className="flex items-center">
                <ForwardedIconComponent
                  name="Scroll"
                  className="mr-2 h-4 w-4"
                />
                Message logs
              </div>
            </SelectItem>
          )}
          {showClearChat && (
            <SelectItem
              value="clearChat"
              className="session-more-menu-item"
              data-testid="clear-chat-option"
            >
              <div className="flex items-center text-status-red hover:text-status-red">
                <ForwardedIconComponent name="X" className="mr-2 h-4 w-4" />
                Clear chat
              </div>
            </SelectItem>
          )}
          {showDelete && (
            <SelectItem
              value="delete"
              className="session-more-menu-item"
              data-testid="delete-session-option"
            >
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

import React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SelectContent, SelectItem } from "@/components/ui/select-custom";

export interface SessionMoreMenuProps {
  onRename?: () => void;
  onMessageLogs?: () => void;
  onDelete?: () => void;
  showMessageLogs?: boolean;
  className?: string;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  sideOffset?: number;
}

const MENU_ITEM_CLASS = "cursor-pointer px-3 py-2 focus:bg-muted";

export function SessionMoreMenu({
  onRename,
  onMessageLogs,
  onDelete,
  showMessageLogs = true,
  className,
  side,
  align,
  sideOffset,
}: SessionMoreMenuProps) {
  return (
    <SelectContent
      side={side}
      align={align}
      sideOffset={sideOffset}
      className={className}
    >
      <SelectItem value="rename" className={MENU_ITEM_CLASS}>
        <div className="flex items-center">
          <ForwardedIconComponent name="SquarePen" className="mr-2 h-4 w-4" />
          Rename
        </div>
      </SelectItem>
      {showMessageLogs && (
        <SelectItem value="messageLogs" className={MENU_ITEM_CLASS}>
          <div className="flex items-center">
            <ForwardedIconComponent name="Scroll" className="mr-2 h-4 w-4" />
            Message logs
          </div>
        </SelectItem>
      )}
      <SelectItem value="delete" className={MENU_ITEM_CLASS}>
        <div className="flex items-center text-status-red hover:text-status-red">
          <ForwardedIconComponent name="Trash2" className="mr-2 h-4 w-4" />
          Delete
        </div>
      </SelectItem>
    </SelectContent>
  );
}

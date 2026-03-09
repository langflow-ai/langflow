import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import type { FlowVersionEntry } from "@/types/flow/version";
import { cn } from "@/utils/utils";
import { formatTimestamp } from "../utils";

interface HistoryListItemProps {
  entry: FlowVersionEntry;
  deploymentCount: number;
  isSelected: boolean;
  isAnimating: boolean;
  onSelect: (id: string) => void;
  onExport: (entry: FlowVersionEntry) => void;
  onDeleteClick: (entry: FlowVersionEntry) => void;
}

export default function HistoryListItem({
  entry,
  deploymentCount,
  isSelected,
  isAnimating,
  onSelect,
  onExport,
  onDeleteClick,
}: HistoryListItemProps) {
  return (
    <SidebarMenuItem
      className={cn(
        "group/histitem relative flex items-center border-b border-border",
        isAnimating ? "history-item-drop-in" : "",
      )}
    >
      <SidebarMenuButton
        isActive={isSelected}
        onClick={() => onSelect(entry.id)}
        className="h-auto flex flex-1 flex-row items-center justify-between rounded-none py-3 pl-3"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="truncate pb-0.5 text-sm font-medium">
            {entry.version_tag}
          </span>
          <div className="flex items-center justify-between pr-2">
            <span className="text-xs text-muted-foreground">
              {formatTimestamp(entry.created_at)}
            </span>
            <span className="inline-flex min-h-[16px] items-center gap-1 text-xs text-muted-foreground">
              {deploymentCount > 0 && (
                <>
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  {deploymentCount > 1
                    ? `Deployed (${deploymentCount})`
                    : "Deployed"}
                </>
              )}
            </span>
          </div>
        </div>
        <div className="flex items-center">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                onClick={(e) => e.stopPropagation()}
                className="flex h-6 w-6 items-center justify-center rounded"
                title="More options"
              >
                <ForwardedIconComponent
                  name="EllipsisVertical"
                  className="h-3.5 w-3.5 text-muted-foreground group-hover/histitem:text-primary"
                />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="right" align="start" className="w-40">
              <DropdownMenuItem
                onClick={() => onExport(entry)}
                className="cursor-pointer"
              >
                <ForwardedIconComponent
                  name="Download"
                  className="mr-2 h-3.5 w-3.5"
                />
                Export
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onDeleteClick(entry)}
                className="cursor-pointer text-destructive focus:bg-destructive/10 focus:text-destructive"
              >
                <ForwardedIconComponent
                  name="Trash2"
                  className="mr-2 h-3.5 w-3.5"
                />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

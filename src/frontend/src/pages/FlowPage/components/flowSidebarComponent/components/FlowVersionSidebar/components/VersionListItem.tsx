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

interface VersionListItemProps {
  entry: FlowVersionEntry;
  isSelected: boolean;
  isAnimating: boolean;
  onSelect: (id: string) => void;
  onExport: (entry: FlowVersionEntry) => void;
  onDeleteClick: (entry: FlowVersionEntry) => void;
}

export default function VersionListItem({
  entry,
  isSelected,
  isAnimating,
  onSelect,
  onExport,
  onDeleteClick,
}: VersionListItemProps) {
  return (
    <SidebarMenuItem
      className={cn(
        "group/histitem relative flex items-center border-b border-border",
        isAnimating ? "version-item-drop-in" : "",
      )}
    >
      <SidebarMenuButton
        isActive={isSelected}
        onClick={() => onSelect(entry.id)}
        className={cn(
          "h-auto flex flex-1 flex-row items-center justify-between pl-3 py-3 rounded-none",
          isSelected && "border-l-2 border-l-[#6366F1] !bg-[#6366F1]/10",
        )}
      >
        <div className="flex flex-col items-start">
          <span className="font-medium text-sm pb-1">{entry.version_tag}</span>
          <span className="text-xs text-muted-foreground">
            {formatTimestamp(entry.created_at)}
          </span>
        </div>
        <div className="flex items-center">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                onClick={(e) => e.stopPropagation()}
                className="group/trigger flex h-6 w-6 items-center justify-center rounded"
                title="More options"
              >
                {isSelected ? (
                  <>
                    <span className="block h-2 w-2 rounded-full bg-[#6366F1] group-hover/trigger:hidden" />
                    <ForwardedIconComponent
                      name="EllipsisVertical"
                      className="hidden h-3.5 w-3.5 text-muted-foreground group-hover/trigger:block"
                    />
                  </>
                ) : (
                  <ForwardedIconComponent
                    name="EllipsisVertical"
                    className="h-3.5 w-3.5 text-muted-foreground group-hover/histitem:text-primary"
                  />
                )}
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

import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import VersionLabel from "@/components/common/versionLabelComponent";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import type { FlowVersionEntry } from "@/types/flow/version";
import { cn } from "@/utils/utils";
import { formatTimestamp, protectedReasonText } from "../utils";

interface VersionListItemProps {
  entry: FlowVersionEntry;
  isSelected: boolean;
  isAnimating: boolean;
  onSelect: (id: string) => void;
  onExport: (entry: FlowVersionEntry) => void;
  onDeleteClick: (entry: FlowVersionEntry) => void;
}

/** One saved version in the history sidebar. A retained version shows a
 * "Protected" badge and cannot be deleted. */
export default function VersionListItem({
  entry,
  isSelected,
  isAnimating,
  onSelect,
  onExport,
  onDeleteClick,
}: VersionListItemProps) {
  const { t } = useTranslation();
  const isProtected = entry.retained === true;
  const protectedReason = isProtected
    ? protectedReasonText(entry.retained_reason, t)
    : "";

  const deleteItem = (
    <DropdownMenuItem
      disabled={isProtected}
      // onSelect, not onClick: Radix never fires it for a disabled item.
      onSelect={() => onDeleteClick(entry)}
      className="cursor-pointer text-destructive focus:bg-destructive/10 focus:text-destructive"
      data-testid="version-delete-item"
    >
      <ForwardedIconComponent name="Trash2" className="mr-2 h-3.5 w-3.5" />
      {t("flow.menu.delete")}
    </DropdownMenuItem>
  );

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
        <div className="flex min-w-0 flex-col items-start">
          <span className="flex w-full min-w-0 items-center gap-2 pb-1">
            <VersionLabel
              versionTag={entry.version_tag}
              description={entry.description}
              className="truncate font-medium text-sm"
            />
            {isProtected && (
              <ShadTooltip content={protectedReason}>
                <span className="shrink-0">
                  <Badge
                    variant="secondaryStatic"
                    size="tag"
                    data-testid="version-protected-badge"
                  >
                    {t("version.protected")}
                  </Badge>
                  {/* The tooltip needs a pointer; this gives the reason to
                      screen readers when the row is focused. */}
                  <span className="sr-only">{protectedReason}</span>
                </span>
              </ShadTooltip>
            )}
          </span>
          <span className="w-full truncate text-xs text-muted-foreground">
            {entry.username
              ? t("version.lastModifiedBy", {
                  time: formatTimestamp(entry.created_at),
                  name: entry.username,
                })
              : formatTimestamp(entry.created_at)}
          </span>
        </div>
        <div className="flex items-center">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                onClick={(e) => e.stopPropagation()}
                className="group/trigger flex h-6 w-6 items-center justify-center rounded"
                title={t("flow.moreOptions")}
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
                {t("flow.menu.export")}
              </DropdownMenuItem>
              {isProtected ? (
                // A disabled item ignores the pointer, so the wrapper takes the hover.
                <ShadTooltip content={protectedReason} side="right">
                  <div>{deleteItem}</div>
                </ShadTooltip>
              ) : (
                deleteItem
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

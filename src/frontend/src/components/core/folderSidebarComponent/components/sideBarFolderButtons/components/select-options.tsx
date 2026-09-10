import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePermissions } from "@/contexts/permissionsContext";
import CustomResourceShareAction from "@/customization/components/custom-resource-share-action";
import type { FolderType } from "@/pages/MainPage/entities";
import { getProjectDisplayName } from "@/utils/project-display-name";
import { cn } from "@/utils/utils";
import { handleSelectChange } from "../helpers/handle-select-change";
import { FolderSelectItem } from "./folder-select-item";

export const SelectOptions = ({
  item,
  handleDeleteFolder,
  handleDownloadFolder,
  handleSelectFolderToRename,
  checkPathName,
}: {
  item: FolderType;
  handleDeleteFolder: ((folder: FolderType) => void) | undefined;
  handleDownloadFolder: (folderId: string) => void;
  handleSelectFolderToRename: (folder: FolderType) => void;
  checkPathName: (folderId: string) => boolean;
}) => {
  const { t } = useTranslation();
  const { can } = usePermissions();
  const canRename = can(item.id, "write");
  const canDownload = can(item.id, "read");
  const canDelete = can(item.id, "delete");
  const displayName = getProjectDisplayName(item, t);
  const select = (option: string) =>
    handleSelectChange(
      option,
      item,
      handleDeleteFolder,
      handleDownloadFolder,
      handleSelectFolderToRename,
    );
  return (
    // A menu of commands, not a value to pick: Knowledge Bases, Files and
    // Deployments all use DropdownMenu here, and Share is a menu item on each.
    // The sidebar was the one surface rendering Share as a second, always-on
    // icon beside the trigger -- the only permanently visible control in the
    // list, on every row (LE-1905).
    <DropdownMenu>
      <ShadTooltip
        content={t("folder.options")}
        side="right"
        styleClasses="z-50"
      >
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 min-h-[24px] min-w-[24px]"
            id={`options-trigger-${item.id}`}
            data-testid={`more-options-button_${item.id}`}
            aria-label={t("folder.optionsFor", { name: displayName })}
            onClick={(e) => e.stopPropagation()}
          >
            <IconComponent
              name={"MoreHorizontal"}
              className={cn(
                `w-4 stroke-[1.5] px-0 text-muted-foreground group-hover/menu-button:block group-hover/menu-button:text-foreground group-focus-within/menu-button:block group-focus-within/menu-button:text-foreground`,
                checkPathName(item.id!) ? "block" : "hidden",
              )}
            />
          </Button>
        </DropdownMenuTrigger>
      </ShadTooltip>
      <DropdownMenuContent
        align="end"
        alignOffset={-16}
        className="min-w-[11.5rem]"
      >
        <DropdownMenuItem
          id="rename-button"
          data-testid="btn-rename-project"
          className="text-xs"
          disabled={!canRename}
          onClick={(e) => {
            e.stopPropagation();
            select("rename");
          }}
        >
          <FolderSelectItem name={t("folder.rename")} iconName="SquarePen" />
        </DropdownMenuItem>
        <DropdownMenuItem
          data-testid="btn-download-project"
          className="text-xs"
          disabled={!canDownload}
          onClick={(e) => {
            e.stopPropagation();
            select("download");
          }}
        >
          <FolderSelectItem name={t("folder.download")} iconName="Download" />
        </DropdownMenuItem>
        <CustomResourceShareAction
          resourceId={item.id!}
          resourceType="project"
          resourceName={displayName}
          display="menu"
        />
        <DropdownMenuItem
          data-testid="btn-delete-project"
          className="text-xs"
          disabled={!canDelete}
          onClick={(e) => {
            e.stopPropagation();
            select("delete");
          }}
        >
          <FolderSelectItem name={t("folder.delete")} iconName="Trash2" />
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

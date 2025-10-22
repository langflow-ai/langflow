import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select-custom";
import type { FolderType } from "@/pages/MainPage/entities";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";
import { handleSelectChange } from "../helpers/handle-select-change";
import { FolderSelectItem } from "./folder-select-item";

export const SelectOptions = ({
  item,
  index,
  handleDeleteFolder,
  handleDownloadFolder,
  handleSelectFolderToRename,
  checkPathName,
}: {
  item: FolderType;
  index: number;
  handleDeleteFolder: ((folder: FolderType) => void) | undefined;
  handleDownloadFolder: (folderId: string) => void;
  handleSelectFolderToRename: (folder: FolderType) => void;
  checkPathName: (folderId: string) => boolean;
}) => {
  const defaultFolderName = useUtilityStore((state) => state.defaultFolderName);
  return (
    <div>
      <Select
        onValueChange={(value) =>
          handleSelectChange(
            value,
            item,
            handleDeleteFolder,
            handleDownloadFolder,
            handleSelectFolderToRename,
          )
        }
        value=""
      >
        <ShadTooltip content="Options" side="right" styleClasses="z-50">
          <SelectTrigger
            className="w-fit"
            id={`options-trigger-${item.name}`}
            data-testid={
              "more-options-button" + `_${convertTestName(item?.name ?? "")}`
            }
          >
            <IconComponent
              name={"MoreHorizontal"}
              className={cn(
                `w-4 stroke-[1.5] px-0 text-muted-foreground group-hover/menu-button:block group-hover/menu-button:text-foreground`,
                checkPathName(item.id!) ? "block" : "hidden",
              )}
            />
          </SelectTrigger>
        </ShadTooltip>
        <SelectContent align="end" alignOffset={-16} position="popper">
          {item.name !== defaultFolderName && (
            <SelectItem
              id="rename-button"
              value="rename"
              data-testid="btn-rename-project"
              className="text-xs"
            >
              <FolderSelectItem name="Rename" iconName="SquarePen" />
            </SelectItem>
          )}
          <SelectItem
            value="download"
            data-testid="btn-download-project"
            className="text-xs"
          >
            <FolderSelectItem name="Download" iconName="Download" />
          </SelectItem>
          {index > 0 && (
            <SelectItem
              value="delete"
              data-testid="btn-delete-project"
              className="text-xs"
            >
              <FolderSelectItem name="Delete" iconName="Trash2" />
            </SelectItem>
          )}
        </SelectContent>
      </Select>
    </div>
  );
};

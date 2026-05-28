import { memo } from "react";
import { useTranslation } from "react-i18next";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import {
  SelectContentWithoutPortal,
  SelectItem,
} from "@/components/ui/select-custom";
import ToolbarSelectItem from "@/pages/FlowPage/components/nodeToolbarComponent/toolbarSelectItem";
import type { NoteDataType } from "@/types/flow";

export const SelectItems = memo(
  ({ shortcuts, data }: { shortcuts: any[]; data: NoteDataType }) => {
    const { t } = useTranslation();
    return (
      <SelectContentWithoutPortal>
        <SelectItem value="duplicate">
          <ToolbarSelectItem
            shortcut={
              shortcuts.find((obj) => obj.name === "Duplicate")?.shortcut!
            }
            value={t("nodeToolbar.duplicate")}
            icon="Copy"
            dataTestId="copy-button-modal"
          />
        </SelectItem>
        <SelectItem value="copy">
          <ToolbarSelectItem
            shortcut={shortcuts.find((obj) => obj.name === "Copy")?.shortcut!}
            value={t("nodeToolbar.copy")}
            icon="Clipboard"
            dataTestId="copy-button-modal"
          />
        </SelectItem>
        <SelectItem
          value="documentation"
          disabled={data.node?.documentation === ""}
        >
          <ToolbarSelectItem
            shortcut={shortcuts.find((obj) => obj.name === "Docs")?.shortcut!}
            value={t("nodeToolbar.docs")}
            icon="FileText"
            dataTestId="docs-button-modal"
          />
        </SelectItem>
        <SelectItem value="delete" className="focus:bg-destructive/[.20]">
          <div className="font-red flex text-status-red">
            <ForwardedIconComponent
              name="Trash2"
              className="relative top-0.5 mr-2 h-4 w-4"
            />
            <span>{t("nodeToolbar.delete")}</span>
            <span className="absolute right-2 top-2 flex items-center justify-center rounded-sm px-1 py-[0.2]">
              <ForwardedIconComponent
                name="Delete"
                className="h-4 w-4 stroke-2 text-destructive"
              />
            </span>
          </div>
        </SelectItem>
      </SelectContentWithoutPortal>
    );
  },
);

SelectItems.displayName = "SelectItems";

import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import {
  SelectContentWithoutPortal,
  SelectItem,
} from "@/components/ui/select-custom";
import ToolbarSelectItem from "@/pages/FlowPage/components/nodeToolbarComponent/toolbarSelectItem";
import { NoteDataType } from "@/types/flow";

import { memo } from "react";

export const SelectItems = memo(
  ({ shortcuts, data }: { shortcuts: any[]; data: NoteDataType }) => (
    <SelectContentWithoutPortal>
      <SelectItem value="duplicate">
        <ToolbarSelectItem
          shortcut={
            shortcuts.find((obj) => obj.name === "Duplicate")?.shortcut!
          }
          value="Duplicate"
          icon="Copy"
          dataTestId="copy-button-modal"
        />
      </SelectItem>
      <SelectItem value="copy">
        <ToolbarSelectItem
          shortcut={shortcuts.find((obj) => obj.name === "Copy")?.shortcut!}
          value="Copy"
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
          value="Docs"
          icon="FileText"
          dataTestId="docs-button-modal"
        />
      </SelectItem>
      <SelectItem value="delete" className="focus:bg-red-400/[.20]">
        <div className="font-red flex text-status-red">
          <ForwardedIconComponent
            name="Trash2"
            className="relative top-0.5 mr-2 h-4 w-4"
          />
          <span>Delete</span>
          <span className="absolute right-2 top-2 flex items-center justify-center rounded-sm px-1 py-[0.2]">
            <ForwardedIconComponent
              name="Delete"
              className="h-4 w-4 stroke-2 text-red-400"
            />
          </span>
        </div>
      </SelectItem>
    </SelectContentWithoutPortal>
  ),
);

SelectItems.displayName = "SelectItems";

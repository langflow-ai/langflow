import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContentWithoutPortal,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { useShortcutsStore } from "@/stores/shortcuts";
import ToolbarSelectItem from "../toolbarSelectItem";

export interface ToolbarMoreMenuProps {
  onSelect: (value: string) => void;
  selectedValue: string | null;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  onTriggerClick: () => void;
  isOutdated: boolean;
  hasBreakingChange: boolean;
  isUserEdited: boolean;
  hasStore: boolean;
  hasApiKey: boolean;
  validApiKey: boolean;
  documentation: string | undefined;
  showNode: boolean;
  isGroup: boolean;
  hasToolMode: boolean;
  frozen: boolean;
}

/**
 * The "more options" dropdown of the node toolbar (save/duplicate/copy/update/
 * share/docs/minimize/ungroup/freeze/download/delete). Extracted verbatim from
 * NodeToolbarComponent (LE-1736 W30); reads shortcuts from the store.
 */
export function ToolbarMoreMenu({
  onSelect,
  selectedValue,
  onOpenChange,
  open,
  onTriggerClick,
  isOutdated,
  hasBreakingChange,
  isUserEdited,
  hasStore,
  hasApiKey,
  validApiKey,
  documentation,
  showNode,
  isGroup,
  hasToolMode,
  frozen,
}: ToolbarMoreMenuProps): JSX.Element {
  const { t } = useTranslation();
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  return (
    <Select
      onValueChange={onSelect}
      value={selectedValue!}
      onOpenChange={onOpenChange}
      open={open}
    >
      <SelectTrigger
        variant="plain"
        className="w-62"
        aria-label={t("nodeToolbar.showMore")}
      >
        <ShadTooltip content={t("nodeToolbar.showMore")} side="top">
          <div data-testid="more-options-modal">
            <Button
              className="node-toolbar-buttons h-[2rem] w-[2rem]"
              variant="ghost"
              onClick={onTriggerClick}
              size="node-toolbar"
              asChild
            >
              <IconComponent name="MoreHorizontal" className="h-4 w-4" />
            </Button>
          </div>
        </ShadTooltip>
      </SelectTrigger>
      <SelectContentWithoutPortal
        className={"relative top-1 w-56 bg-background"}
      >
        <SelectItem variant="plain" value={"save"}>
          <ToolbarSelectItem
            shortcut={
              shortcuts.find((obj) => obj.name === "Save Component")?.shortcut!
            }
            value={t("nodeToolbar.save")}
            icon={"SaveAll"}
            dataTestId="save-button-modal"
          />
        </SelectItem>
        <SelectItem variant="plain" value={"duplicate"}>
          <ToolbarSelectItem
            shortcut={
              shortcuts.find((obj) => obj.name === "Duplicate")?.shortcut!
            }
            value={t("nodeToolbar.duplicate")}
            icon={"Copy"}
            dataTestId="copy-button-modal"
          />
        </SelectItem>
        <SelectItem variant="plain" value={"copy"}>
          <ToolbarSelectItem
            shortcut={shortcuts.find((obj) => obj.name === "Copy")?.shortcut!}
            value={t("nodeToolbar.copy")}
            icon={"Clipboard"}
            dataTestId="copy-button-modal"
          />
        </SelectItem>
        {isOutdated && (
          <SelectItem variant="plain" value={"update"}>
            <ToolbarSelectItem
              shortcut={
                shortcuts.find((obj) => obj.name === "Update")?.shortcut!
              }
              style={hasBreakingChange ? "text-accent-amber-foreground" : ""}
              value={
                isUserEdited
                  ? t("nodeToolbar.restore")
                  : t("nodeToolbar.update")
              }
              icon={isUserEdited ? "RefreshCcwDot" : "CircleArrowUp"}
              dataTestId="update-button-modal"
            />
          </SelectItem>
        )}
        {hasStore && (
          <SelectItem
            variant="plain"
            value={"Share"}
            disabled={!hasApiKey || !validApiKey}
          >
            <ToolbarSelectItem
              shortcut={
                shortcuts.find((obj) => obj.name === "Component Share")
                  ?.shortcut!
              }
              value={t("nodeToolbar.share")}
              icon={"Share3"}
              dataTestId="share-button-modal"
            />
          </SelectItem>
        )}

        <SelectItem
          variant="plain"
          value={"documentation"}
          disabled={documentation === ""}
        >
          <ToolbarSelectItem
            shortcut={shortcuts.find((obj) => obj.name === "Docs")?.shortcut!}
            value={t("nodeToolbar.docs")}
            icon={"FileText"}
            dataTestId="docs-button-modal"
          />
        </SelectItem>

        <SelectItem
          variant="plain"
          value={"show"}
          data-testid={`${showNode ? "minimize" : "expand"}-button-modal`}
        >
          <ToolbarSelectItem
            shortcut={
              shortcuts.find((obj) => obj.name === "Minimize")?.shortcut!
            }
            value={
              showNode ? t("nodeToolbar.minimize") : t("nodeToolbar.expand")
            }
            icon={showNode ? "Minimize2" : "Maximize2"}
          />
        </SelectItem>
        {isGroup && (
          <SelectItem variant="plain" value="ungroup">
            <ToolbarSelectItem
              shortcut={
                shortcuts.find((obj) => obj.name === "Group")?.shortcut!
              }
              value={t("nodeToolbar.ungroup")}
              icon={"Ungroup"}
              dataTestId="group-button-modal"
            />
          </SelectItem>
        )}
        {hasToolMode && (
          <SelectItem
            variant="plain"
            value="freezeAll"
            data-testid="freeze-all-button-modal"
          >
            <ToolbarSelectItem
              shortcut={
                shortcuts.find((obj) =>
                  obj.name.toLowerCase().startsWith("freeze"),
                )?.shortcut!
              }
              value={t("nodeToolbar.freeze")}
              icon={"FreezeAll"}
              dataTestId="freeze-path-button"
              style={`${frozen ? " text-ice" : ""} transition-all`}
            />
          </SelectItem>
        )}
        <SelectItem variant="plain" value="Download">
          <ToolbarSelectItem
            shortcut={
              shortcuts.find((obj) => obj.name === "Download")?.shortcut!
            }
            value={t("nodeToolbar.download")}
            icon={"Download"}
            dataTestId="download-button-modal"
          />
        </SelectItem>
        <SelectItem
          variant="plain"
          value={"delete"}
          className="focus:bg-destructive/[.20]"
        >
          <div className="font-red flex text-status-red">
            <IconComponent
              name="Trash2"
              className="relative top-0.5 mr-2 h-4 w-4"
            />{" "}
            <span className="">{t("nodeToolbar.delete")}</span>{" "}
            <span
              className={`absolute right-2 top-2 flex items-center justify-center rounded-sm px-1 py-[0.2]`}
            >
              <IconComponent
                name="Delete"
                className="h-4 w-4 stroke-2 text-destructive"
              ></IconComponent>
            </span>
          </div>
        </SelectItem>
      </SelectContentWithoutPortal>
    </Select>
  );
}

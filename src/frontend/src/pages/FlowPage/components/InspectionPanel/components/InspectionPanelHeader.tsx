import { useCallback, useMemo, useState } from "react";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import CodeAreaModal from "@/modals/codeAreaModal";
import useAlertStore from "@/stores/alertStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import type { NodeDataType } from "@/types/flow";
import { cn } from "@/utils/utils";
import { ToolbarButton } from "../../nodeToolbarComponent/components/toolbar-button";
import EditableHeaderContent from "./EditableHeaderContent";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { useHotkeys } from "react-hotkeys-hook";

interface InspectionPanelHeaderProps {
  data: NodeDataType;
  isEditingFields: boolean;
  setIsEditingFields: (value: boolean) => void;
}

export default function InspectionPanelHeader({
  data,
  isEditingFields,
  setIsEditingFields,
}: InspectionPanelHeaderProps) {
  const [openCodeModal, setOpenCodeModal] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [isHoveringContent, setIsHoveringContent] = useState(false);
  const { handleNodeClass } = useHandleNodeClass(data.id);
  const { handleOnNewValue } = useHandleOnNewValue({
    node: data.node!,
    nodeId: data.id,
    name: "code",
  });

  const hasCode = useMemo(
    () => Object.keys(data.node!.template).includes("code"),
    [data.node],
  );

  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const handleCopyId = useCallback(() => {
    navigator.clipboard.writeText(data.id);
    setSuccessData({ title: "Component ID copied to clipboard" });
  }, [data.id, setSuccessData]);

  const handleOpenCode = useCallback(() => {
    if (hasCode) {
      setOpenCodeModal(true);
    }
  }, [hasCode]);

  const openDocs = useCallback(() => {
    if (data.node?.documentation) {
      return customOpenNewTab(data.node.documentation);
    }
    setNoticeData({
      title: `${data.id} docs is not available at the moment.`,
    });
  }, [data.id, data.node?.documentation, setNoticeData]);

  // Wrapper to match CodeAreaModal's expected signature
  const handleSetValue = useCallback(
    (value: string) => {
      handleOnNewValue({ value });
    },
    [handleOnNewValue],
  );

  const shortcuts = useShortcutsStore((state) => state.shortcuts);

  const hasDocs = (data.node?.documentation ?? "") !== "";

  const isCustomComponent = useMemo(() => {
    const isCustom = data.type === "CustomComponent" && !data.node?.edited;
    if (isCustom) {
      data.node.edited = true;
    }
    return isCustom;
  }, [data.type, data.node]);

  const { containerRef, handleSave, nameElement, descriptionElement } =
    EditableHeaderContent({
      data,
      editMode,
      setEditMode,
    });

  const toggleEditMode = useCallback(() => {
    if (editMode) {
      // Save changes when exiting edit mode
      handleSave();
    }
    setEditMode((prev) => !prev);
  }, [editMode, handleSave]);

  const advancedSettings = useShortcutsStore((state) => state.advancedSettings);

  useHotkeys(advancedSettings, () => setIsEditingFields(!isEditingFields), {
    preventDefault: true,
  });

  return (
    <>
      <div
        className="flex flex-col py-3 px-4"
        ref={containerRef}
        data-testid="panel-description"
        onMouseEnter={() => setIsHoveringContent(true)}
        onMouseLeave={() => setIsHoveringContent(false)}
      >
        <div className="absolute -left-2 top-[18px] w-7 pr-2">
          <ShadTooltip content={editMode ? "Save" : "Edit"} side="top">
            <Button
              unstyled
              onClick={() => {
                toggleEditMode();
              }}
              className={cn(
                "nodrag z-50 flex h-5 w-5 ml-1 cursor-pointer items-center justify-center rounded-md",
                "transform transition-all duration-300 ease-out",
                editMode ? "bg-accent-emerald" : "bg-zinc-foreground",
                isHoveringContent ? "opacity-100" : "opacity-0",
              )}
              data-testid={
                editMode
                  ? "save-name-description-button"
                  : "edit-name-description-button"
              }
            >
              <ForwardedIconComponent
                name={editMode ? "Check" : "PencilLine"}
                strokeWidth={ICON_STROKE_WIDTH}
                className={cn(
                  editMode
                    ? "text-accent-emerald-foreground"
                    : "text-muted-foreground",
                  "w-4 h-4",
                )}
              />
            </Button>
          </ShadTooltip>
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 overflow-hidden">
            <span className="font-semibold truncate" data-testid="panel-name">
              {nameElement}
            </span>
            <ShadTooltip content="Click to copy full ID">
              <Badge
                variant="secondaryStatic"
                size="sm"
                className="shrink-0 cursor-pointer rounded-full px-2 text-[10px] font-normal hover:bg-muted-foreground/20"
                onClick={handleCopyId}
              >
                ID: {data.id.split("-").pop()}
              </Badge>
            </ShadTooltip>
          </div>
          <div
            className="flex items-center gap-1"
            onMouseEnter={() => setIsHoveringContent(false)}
          >
            {hasDocs && (
              <ToolbarButton
                icon="FileText"
                onClick={openDocs}
                shortcut={shortcuts.find((s) =>
                  s.name.toLowerCase().startsWith("docs"),
                )}
                className="!text-muted-foreground"
                dataTestId="docs-button-modal"
              />
            )}
            {hasCode && (
              <ToolbarButton
                icon="SlidersHorizontal"
                onClick={() => setIsEditingFields(!isEditingFields)}
                shortcut={shortcuts.find((s) =>
                  s.name.toLowerCase().startsWith("advanced"),
                )}
                className={cn(
                  "!text-muted-foreground",
                  isEditingFields && "!text-foreground !bg-muted",
                )}
                dataTestId="edit-fields-button"
              />
            )}
          </div>
        </div>

        {hasCode && openCodeModal && (
          <div className="hidden">
            <CodeAreaModal
              setValue={handleSetValue}
              open={openCodeModal}
              setOpen={setOpenCodeModal}
              dynamic={true}
              setNodeClass={(apiClassType, type) => {
                handleNodeClass(apiClassType, type);
              }}
              nodeClass={data.node}
              value={data.node?.template?.code?.value ?? ""}
              componentId={data.id}
            >
              <></>
            </CodeAreaModal>
          </div>
        )}
        {descriptionElement}
      </div>
    </>
  );
}

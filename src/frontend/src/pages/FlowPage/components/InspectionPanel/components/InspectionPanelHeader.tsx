import { useState, useCallback, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import CodeAreaModal from "@/modals/codeAreaModal";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import type { NodeDataType } from "@/types/flow";
import { ToolbarButton } from "../../nodeToolbarComponent/components/toolbar-button";
import { useShortcutsStore } from "@/stores/shortcuts";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";

interface InspectionPanelHeaderProps {
  data: NodeDataType;
  onClose?: () => void;
  isEditingFields?: boolean;
  onToggleEditFields?: () => void;
}

export default function InspectionPanelHeader({
  data,
  onClose,
  isEditingFields = false,
  onToggleEditFields,
}: InspectionPanelHeaderProps) {
  const [openCodeModal, setOpenCodeModal] = useState(false);
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

  return (
    <div className="flex flex-col gap-2 py-3 px-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold">
            {data.node?.display_name ?? data.type}
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
        <div className="flex items-center gap-1">
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
              className={cn(
                isCustomComponent ? "animate-pulse-pink" : "",
                "!text-muted-foreground",
              )}
              icon="Code"
              onClick={handleOpenCode}
              shortcut={shortcuts.find((s) =>
                s.name.toLowerCase().startsWith("code"),
              )}
              dataTestId="code-button-modal"
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
      <div className="flex items-end justify-between gap-4">
        <p className="max-w-[230px] text-xs text-muted-foreground">
          Configure component settings and toggle parameter visibility.
        </p>
        <button
          onClick={onToggleEditFields}
          className={cn(
            "shrink-0 text-xs font-medium transition-colors",
            isEditingFields
              ? "text-primary hover:text-primary/80"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {isEditingFields ? "Done" : "Edit"}
        </button>
      </div>
    </div>
  );
}

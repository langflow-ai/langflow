import { useState, useCallback, useMemo } from "react";
import { NodeIcon } from "@/CustomNodes/GenericNode/components/nodeIcon";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import CodeAreaModal from "@/modals/codeAreaModal";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import type { NodeDataType } from "@/types/flow";
import { ToolbarButton } from "../../nodeToolbarComponent/components/toolbar-button";
import { useShortcutsStore } from "@/stores/shortcuts";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import useAlertStore from "@/stores/alertStore";

interface InspectionPanelHeaderProps {
  data: NodeDataType;
  onClose?: () => void;
}

export default function InspectionPanelHeader({
  data,
  onClose,
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

  const isCustomComponent = useMemo(() => {
    const isCustom = data.type === "CustomComponent" && !data.node?.edited;
    if (isCustom) {
      data.node.edited = true;
    }
    return isCustom;
  }, [data.type, data.node]);

  return (
    <div className="flex flex-col gap-0.5 pt-2 pb-1 px-3 pl-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-sm">
            {data.node?.display_name ?? data.type}
          </span>
        </div>
        <div className="flex items-center gap-0.5">
          <ShadTooltip content="Documentation" side="left">
            <ToolbarButton
              icon="FileText"
              onClick={openDocs}
              shortcut={shortcuts.find((s) =>
                s.name.toLowerCase().startsWith("docs"),
              )}
              dataTestId="docs-button-modal"
            />
          </ShadTooltip>
          {hasCode && (
            <ShadTooltip content="View Code" side="left">
              <ToolbarButton
                className={isCustomComponent ? "animate-pulse-pink" : ""}
                icon="Code"
                onClick={handleOpenCode}
                shortcut={shortcuts.find((s) =>
                  s.name.toLowerCase().startsWith("code"),
                )}
                dataTestId="code-button-modal"
              />
            </ShadTooltip>
          )}
          {onClose && (
            <ShadTooltip content="Close" side="top">
              <Button
                variant="ghost"
                size="node-toolbar"
                onClick={onClose}
              >
                <IconComponent name="X" className="h-4 w-4" />
              </Button>
            </ShadTooltip>
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
      <p className="text-mmd text-muted-foreground">{data.node?.description}</p>
    </div>
  );
}

// Made with Bob

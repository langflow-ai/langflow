import { useState, useCallback } from "react";
import { NodeIcon } from "@/CustomNodes/GenericNode/components/nodeIcon";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import CodeAreaModal from "@/modals/codeAreaModal";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import type { NodeDataType } from "@/types/flow";

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

  const hasCode = data.node?.template?.code !== undefined;

  const handleOpenCode = useCallback(() => {
    if (hasCode) {
      setOpenCodeModal(true);
    }
  }, [hasCode]);

  // Wrapper to match CodeAreaModal's expected signature
  const handleSetValue = useCallback(
    (value: string) => {
      handleOnNewValue({ value });
    },
    [handleOnNewValue],
  );

  return (
    <>
      <div className="flex items-center justify-between border-b p-4">
        <div className="flex items-center gap-3">
          <NodeIcon
            dataType={data.type}
            icon={data.node?.icon}
            isGroup={!!data.node?.flow}
          />
          <div className="flex flex-col">
            <span className="font-semibold text-sm">
              {data.node?.display_name ?? data.type}
            </span>
            <span className="text-xs text-muted-foreground">
              Component Settings
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {hasCode && (
            <ShadTooltip content="View Code" side="left">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handleOpenCode}
              >
                <IconComponent name="Code" className="h-4 w-4" />
              </Button>
            </ShadTooltip>
          )}
          {onClose && (
            <ShadTooltip content="Close" side="left">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
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
    </>
  );
}

// Made with Bob

import type { CustomCellRendererProps } from "ag-grid-react";
import { useTranslation } from "react-i18next";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useFlowStore from "@/stores/flowStore";
import { useTweaksStore } from "@/stores/tweaksStore";
import type { APIClassType } from "@/types/api";
import { isTargetHandleConnected } from "@/utils/reactflowUtils";
import VisibilityToggleButton from "./VisibilityToggleButton";

export default function TableAdvancedToggleCellRender({
  value: { nodeId, parameterId, isTweaks },
}: CustomCellRendererProps) {
  const { t } = useTranslation();
  const edges = useFlowStore((state) => state.edges);
  const node = isTweaks
    ? useTweaksStore((state) => state.getNode(nodeId))
    : useFlowStore((state) => state.getNode(nodeId));
  const parameter = node?.data?.node?.template?.[parameterId];

  const setNode = useTweaksStore((state) => state.setNode);
  const isApiEditable = parameter?.api_editable === true;

  const disabled = isTargetHandleConnected(
    edges,
    parameterId,
    parameter,
    nodeId,
  );

  const { handleOnNewValue } = useHandleOnNewValue({
    node: node?.data.node as APIClassType,
    nodeId,
    name: parameterId,
    setNode: isTweaks ? setNode : undefined,
  });

  // LE-1810: in the tweaks table the toggle drives the persisted
  // api_editable flag on the real flow node, mirrored to the tweaks copy so
  // the snippets recompute. The flow write must clone the REAL node — the
  // tweaks copy carries a filtered template.
  const flowNode = useFlowStore((state) => state.getNode(nodeId));
  const { handleOnNewValue: handleOnNewValueOnFlowNode } = useHandleOnNewValue({
    node: flowNode?.data.node as APIClassType,
    nodeId,
    name: parameterId,
  });

  const handleToggle = () => {
    if (isTweaks) {
      handleOnNewValueOnFlowNode({ api_editable: !isApiEditable });
      handleOnNewValue({ api_editable: !isApiEditable });
      return;
    }
    handleOnNewValue({ advanced: !parameter.advanced });
  };

  return (
    parameter && (
      <ShadTooltip
        content={
          disabled
            ? isTweaks
              ? t("editNode.tooltipCannotEnableInput")
              : t("editNode.tooltipCannotChangeVisibility")
            : isTweaks
              ? t("editNode.tooltipToggleInput")
              : t("editNode.tooltipChangeVisibility")
        }
        styleClasses="z-50"
      >
        <div className="flex h-full w-full items-center justify-center">
          <VisibilityToggleButton
            id={"show" + parameterId}
            checked={isTweaks ? isApiEditable : !parameter.advanced}
            disabled={disabled}
            onToggle={handleToggle}
          />
        </div>
      </ShadTooltip>
    )
  );
}

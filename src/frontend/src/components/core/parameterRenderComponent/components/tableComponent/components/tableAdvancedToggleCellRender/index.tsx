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
            checked={!parameter.advanced}
            disabled={disabled}
            onToggle={() => handleOnNewValue({ advanced: !parameter.advanced })}
          />
        </div>
      </ShadTooltip>
    )
  );
}

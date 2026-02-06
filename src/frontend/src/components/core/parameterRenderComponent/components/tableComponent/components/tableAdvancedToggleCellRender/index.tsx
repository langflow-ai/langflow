import type { CustomCellRendererProps } from "ag-grid-react";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useFlowStore from "@/stores/flowStore";
import { useTweaksStore } from "@/stores/tweaksStore";
import type { APIClassType } from "@/types/api";
import { isTargetHandleConnected } from "@/utils/reactflowUtils";
import ToggleShadComponent from "../../../toggleShadComponent";

export default function TableAdvancedToggleCellRender({
  value: { nodeId, parameterId, isTweaks },
}: CustomCellRendererProps) {
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

  // For tweaks mode, use api_only field; otherwise use advanced field
  // Default: if api_only not set, fields are exposed when visible (not advanced)
  const isExposed = isTweaks
    ? (parameter.api_only ?? !parameter.advanced)
    : !parameter.advanced;

  return (
    parameter && (
      <ShadTooltip
        content={
          disabled
            ? isTweaks
              ? "Cannot enable input of connected handles"
              : "Cannot change visibility of connected handles"
            : isTweaks
              ? "Toggle input of the field in the API"
              : "Change visibility of the field"
        }
        styleClasses="z-50"
      >
        <div className="flex h-full w-full items-center justify-center">
          <ToggleShadComponent
            disabled={disabled}
            value={isExposed}
            handleOnNewValue={handleOnNewValue}
            editNode={true}
            showToogle
            toggleField={isTweaks ? "api_only" : "advanced"}
            id={"show" + parameterId}
          />
        </div>
      </ShadTooltip>
    )
  );
}

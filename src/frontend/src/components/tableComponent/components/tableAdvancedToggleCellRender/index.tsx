import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import ShadTooltip from "@/components/shadTooltipComponent";
import useFlowStore from "@/stores/flowStore";
import { isTargetHandleConnected } from "@/utils/reactflowUtils";
import { CustomCellRendererProps } from "ag-grid-react";
import ToggleShadComponent from "../../../toggleShadComponent";

export default function TableAdvancedToggleCellRender({
  node: { data },
  value: { nodeId },
}: CustomCellRendererProps) {
  const edges = useFlowStore((state) => state.edges);
  const node = useFlowStore((state) => state.getNode(nodeId));
  const parameter = node?.data?.node?.template?.[data.key];

  const disabled = isTargetHandleConnected(edges, data.key, data, nodeId);

  const { handleOnNewValue } = useHandleOnNewValue({
    node: node?.data.node,
    nodeId,
    name: data.key,
  });

  return (
    parameter && (
      <ShadTooltip
        content={
          disabled
            ? "Cannot change visibility of connected handles"
            : "Change visibility of the field"
        }
        styleClasses="z-50"
      >
        <div>
          <div className="flex h-full items-center">
            <ToggleShadComponent
              id={"show" + data.key}
              disabled={disabled}
              enabled={!parameter?.advanced ?? true}
              setEnabled={(e) => {
                console.log(e, parameter);
                handleOnNewValue({ advanced: !e });
              }}
              size="small"
              editNode={true}
            />
          </div>
        </div>
      </ShadTooltip>
    )
  );
}

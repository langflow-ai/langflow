import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import ShadTooltip from "@/components/shadTooltipComponent";
import useFlowStore from "@/stores/flowStore";
import { isTargetHandleConnected } from "@/utils/reactflowUtils";
import { CustomCellRendererProps } from "ag-grid-react";
import { useState } from "react";
import ToggleShadComponent from "../../../toggleShadComponent";

export default function TableAdvancedToggleCellRender({
  node: { data },
  value: { value: enabled, nodeId, nodeClass },
}: CustomCellRendererProps) {
  const [value, setValue] = useState(enabled);
  const edges = useFlowStore((state) => state.edges);

  const disabled = isTargetHandleConnected(edges, data.key, data, nodeId);

  const { handleOnNewValue } = useHandleOnNewValue({
    node: nodeClass,
    nodeId,
    name: data.key,
  });

  return (
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
            id={"show" + name}
            disabled={disabled}
            enabled={value}
            setEnabled={(e) => {
              setValue(e);
              handleOnNewValue({ advanced: value });
            }}
            size="small"
            editNode={true}
          />
        </div>
      </div>
    </ShadTooltip>
  );
}

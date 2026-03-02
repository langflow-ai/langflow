import { useMemo } from "react";
import type { NodeDataType } from "@/types/flow";
import useFlowStore from "@/stores/flowStore";
import SwitchOutputView from "@/CustomNodes/GenericNode/components/outputModal/components/switchOutputView";
import { getGroupOutputNodeId } from "@/utils/reactflowUtils";

interface InspectionPanelOutputsProps {
  data: NodeDataType;
}

export default function InspectionPanelOutputs({
  data,
}: InspectionPanelOutputsProps) {
  const flowPool = useFlowStore((state) => state.flowPool);

  // Get all outputs from the node
  const outputs = useMemo(() => {
    return data.node?.outputs?.filter((output) => !output.hidden) ?? [];
  }, [data.node?.outputs]);

  // Get the first output with data
  const firstOutputWithData = useMemo(() => {
    for (const output of outputs) {
      const outputProxy = output.proxy;
      let flowPoolId = data.id;
      let internalOutputName = output.name;

      if (data.node?.flow && outputProxy) {
        const realOutput = getGroupOutputNodeId(
          data.node.flow,
          outputProxy.name,
          outputProxy.id,
        );
        if (realOutput) {
          flowPoolId = realOutput.id;
          internalOutputName = realOutput.outputName;
        }
      }

      const flowPoolNode =
        flowPool[flowPoolId]?.[(flowPool[flowPoolId]?.length ?? 1) - 1];

      if (flowPoolNode?.data?.outputs?.[internalOutputName]?.message) {
        return {
          nodeId: flowPoolId,
          outputName: internalOutputName,
          displayName: output.display_name || output.name,
        };
      }
    }
    return null;
  }, [outputs, data.id, data.node?.flow, flowPool]);

  if (!firstOutputWithData) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
        No output data available. Please build the component first.
      </div>
    );
  }

  return (
    <div className="p-2 space-y-2 h-full flex flex-col">
      <div className="text-xs font-medium text-muted-foreground px-2">
        {firstOutputWithData.displayName}
      </div>
      <div className="overflow-hidden h-80 max-h-80">
        <SwitchOutputView
          nodeId={firstOutputWithData.nodeId}
          outputName={firstOutputWithData.outputName}
          type="Outputs"
        />
      </div>
    </div>
  );
}

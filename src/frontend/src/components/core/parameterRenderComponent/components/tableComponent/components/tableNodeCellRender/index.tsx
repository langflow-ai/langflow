import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { ParameterRenderComponent } from "@/components/core/parameterRenderComponent";
import useFlowStore from "@/stores/flowStore";
import { useTweaksStore } from "@/stores/tweaksStore";
import { APIClassType } from "@/types/api";
import { isTargetHandleConnected } from "@/utils/reactflowUtils";
import { CustomCellRendererProps } from "ag-grid-react";

export default function TableNodeCellRender({
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

  const { handleNodeClass } = useHandleNodeClass(
    nodeId,
    isTweaks ? setNode : undefined,
  );

  return (
    parameter && (
      <div className="group mx-auto flex h-full max-h-48 w-[300px] items-center justify-center overflow-auto px-1 py-2.5 custom-scroll">
        <ParameterRenderComponent
          nodeId={nodeId}
          handleOnNewValue={handleOnNewValue}
          templateData={parameter}
          name={parameterId}
          templateValue={parameter.value}
          editNode={true}
          handleNodeClass={handleNodeClass}
          nodeClass={node?.data.node}
          disabled={disabled}
        />
      </div>
    )
  );
}

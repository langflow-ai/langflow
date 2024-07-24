import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { ParameterRenderComponent } from "@/components/parameterRenderComponent";
import { useTweaksStore } from "@/stores/tweaksStore";
import { CustomCellRendererProps } from "ag-grid-react";
import useFlowStore from "../../../../stores/flowStore";
import { isTargetHandleConnected } from "../../../../utils/reactflowUtils";

export default function TableNodeCellRender({
  node: { data },
  value: { nodeId, isTweaks },
}: CustomCellRendererProps) {
  const edges = useFlowStore((state) => state.edges);
  const node = isTweaks
    ? useTweaksStore((state) => state.getNode(nodeId))
    : useFlowStore((state) => state.getNode(nodeId));
  const parameter = node?.data?.node?.template?.[data.key];

  const setNode = useTweaksStore((state) => state.setNode);

  const disabled = isTargetHandleConnected(edges, data.key, data, nodeId);

  const { handleOnNewValue } = useHandleOnNewValue({
    node: node?.data.node,
    nodeId,
    name: data.key,
    setNode: isTweaks ? setNode : undefined,
  });

  const { handleNodeClass } = useHandleNodeClass(
    nodeId,
    isTweaks ? setNode : undefined,
  );

  console.log("oi");

  return (
    parameter && (
      <div className="group mx-auto flex h-full max-h-48 w-[300px] items-center justify-center overflow-auto py-2.5 custom-scroll">
        <ParameterRenderComponent
          nodeId={nodeId}
          handleOnNewValue={handleOnNewValue}
          templateData={parameter}
          name={data.key}
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

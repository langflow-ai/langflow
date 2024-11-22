import { IPatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import { APIClassType } from "@/types/api";
import { FlowType } from "@/types/flow";
import { UseMutateFunction } from "@tanstack/react-query";
import { cloneDeep } from "lodash";

export function useFlowUpdate({
  patchUpdateFlow,
  currentFlow,
}: {
  patchUpdateFlow: UseMutateFunction<any, any, IPatchUpdateFlow, unknown>;
  currentFlow: FlowType | undefined;
}) {
  const updateNodeInFlow = (componentId: string, data: APIClassType) => {
    if (!componentId || !data) return;

    const flow = cloneDeep(currentFlow);
    const node = flow?.data?.nodes.find((node) => node.id === componentId);

    const currentFlowAvailable = flow && flow?.data && node;

    if (currentFlowAvailable) {
      const nodeIndex = flow.data!.nodes.indexOf(node);

      node.data.node = data;
      flow!.data!.nodes[nodeIndex] = node;

      const newFlow = {
        id: flow.id!,
        name: flow.name!,
        data: flow.data!,
        description: flow.description!,
        folder_id: flow.folder_id || null,
        endpoint_name: flow.endpoint_name || null,
      };

      patchUpdateFlow(newFlow);
    }
  };

  return { updateNodeInFlow };
}

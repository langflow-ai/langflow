import { cloneDeep } from "lodash"; // or any other deep cloning library you prefer
import { useCallback } from "react";
import {
  applyNodeFieldUpdates,
  buildSetNodeFieldUpdate,
  buildThreeWayComponentNodeUpdates,
  type ThreeWayComponentDiffPolicy,
} from "@/hooks/flows/flow-operation-diff";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType } from "@/types/flow";
import type { NodeFieldPath } from "@/types/flow-operations";
import type { APIClassType } from "../../types/api";

function pathStartsWith(path: NodeFieldPath, prefix: string[]): boolean {
  return prefix.every((segment, index) => path[index] === segment);
}

const useUpdateNodeCode = (
  dataId: string,
  dataNode: APIClassType, // Define YourNodeType according to your data structure
  setNode: ReturnType<typeof useFlowStore.getState>["setNode"],
  updateNodeInternals: (id: string) => void,
) => {
  const setComponentsToUpdate = useFlowStore(
    (state) => state.setComponentsToUpdate,
  );

  const updateNodeCode = useCallback(
    (newNodeClass: APIClassType, code: string, name: string, type: string) => {
      const latestNode = useFlowStore.getState().getNode(dataId);
      if (!latestNode) {
        throw new Error("Node not found");
      }
      const generatedNodeClass = cloneDeep({
        ...newNodeClass,
        edited: false,
      });
      const policy: ThreeWayComponentDiffPolicy = {
        generatedWinsOnOverlap: (path) =>
          pathStartsWith(path, ["data", "node", "template", name, "value"]),
      };
      if (generatedNodeClass.template?.[name]) {
        generatedNodeClass.template[name].value = code;
      }
      const collaborationUpdates = buildThreeWayComponentNodeUpdates(
        dataId,
        dataNode as unknown as Record<string, unknown>,
        (latestNode.data.node ?? {}) as unknown as Record<string, unknown>,
        generatedNodeClass as unknown as Record<string, unknown>,
        policy,
      );
      if (type) {
        collaborationUpdates.push(
          buildSetNodeFieldUpdate(dataId, ["data", "type"], type),
        );
      }
      collaborationUpdates.push(
        buildSetNodeFieldUpdate(
          dataId,
          ["data", "description"],
          newNodeClass.description ?? dataNode.description,
        ),
        buildSetNodeFieldUpdate(
          dataId,
          ["data", "display_name"],
          newNodeClass.display_name ?? dataNode.display_name,
        ),
      );

      setNode(
        dataId,
        applyNodeFieldUpdates(
          latestNode as unknown as Record<string, unknown>,
          collaborationUpdates,
        ) as unknown as AllNodeType,
        true,
        undefined,
        { collaborationUpdates },
      );

      setComponentsToUpdate((old) =>
        old.filter((component) => component.id !== dataId),
      );
      updateNodeInternals(dataId);
    },
    [dataId, dataNode, setNode, updateNodeInternals, setComponentsToUpdate],
  );

  return updateNodeCode;
};

export default useUpdateNodeCode;

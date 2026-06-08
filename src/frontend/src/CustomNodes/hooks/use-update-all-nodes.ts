import { cloneDeep } from "lodash";
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

export type UpdateNodesType = {
  nodeId: string;
  baseNode: APIClassType;
  newNode: APIClassType;
  code: string;
  name: string;
  type?: string;
};

const useUpdateAllNodes = (
  setNodes: ReturnType<typeof useFlowStore.getState>["setNodes"],
  updateNodeInternals: (nodeId: string) => void,
) => {
  const updateAllNodes = useCallback(
    (updates: UpdateNodesType[]) => {
      const latestNodes = useFlowStore.getState().nodes;
      const collaborationUpdates = updates.flatMap(
        ({ nodeId, baseNode, newNode, code, name, type }) => {
          const latestNode = latestNodes.find((n) => n.id === nodeId);
          if (!latestNode) return [];
          const generatedNode = cloneDeep({ ...newNode, edited: false });
          if (generatedNode.template?.[name]) {
            generatedNode.template[name].value = code;
          }
          const policy: ThreeWayComponentDiffPolicy = {
            generatedWinsOnOverlap: (path) =>
              pathStartsWith(path, ["data", "node", "template", name, "value"]),
          };
          const nodeUpdates = buildThreeWayComponentNodeUpdates(
            nodeId,
            baseNode as unknown as Record<string, unknown>,
            (latestNode.data.node ?? {}) as unknown as Record<string, unknown>,
            generatedNode as unknown as Record<string, unknown>,
            policy,
          );
          if (type) {
            nodeUpdates.push(
              buildSetNodeFieldUpdate(nodeId, ["data", "type"], type),
            );
          }
          nodeUpdates.push(
            buildSetNodeFieldUpdate(
              nodeId,
              ["data", "description"],
              newNode.description ?? baseNode.description,
            ),
            buildSetNodeFieldUpdate(
              nodeId,
              ["data", "display_name"],
              newNode.display_name ?? baseNode.display_name,
            ),
          );
          return nodeUpdates;
        },
      );
      if (collaborationUpdates.length === 0) {
        return;
      }

      setNodes(
        (oldNodes) => {
          const newNodes = cloneDeep(oldNodes);

          updates.forEach(({ nodeId }) => {
            const nodeIndex = newNodes.findIndex((n) => n.id === nodeId);
            if (nodeIndex === -1) return;

            const updatedNode = newNodes[nodeIndex];
            newNodes[nodeIndex] = applyNodeFieldUpdates(
              updatedNode as unknown as Record<string, unknown>,
              collaborationUpdates.filter((update) => update.id === nodeId),
            ) as unknown as AllNodeType;

            updateNodeInternals(nodeId);
          });

          return newNodes;
        },
        { collaborationUpdates },
      );
    },
    [setNodes, updateNodeInternals],
  );

  return updateAllNodes;
};

export default useUpdateAllNodes;

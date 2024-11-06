import { APIClassType } from "@/types/api";
import { cloneDeep } from "lodash";
import { Edge } from "reactflow";

export function processNodeAdvancedFields(
  resData: APIClassType,
  edges: Edge[],
  nodeId: string,
) {
  let newNode = cloneDeep(resData);

  const edgesWithNode = edges.filter(
    (edge) => edge.source !== nodeId || edge.target !== nodeId,
  );

  if (edgesWithNode.length === 0) return newNode;

  for (const edge of edgesWithNode) {
    const field = edge?.data?.targetHandle?.fieldName;

    if (field) {
      const fieldTemplate = newNode.template[field];
      if (fieldTemplate?.advanced === true) {
        newNode.template[field].advanced = false;
      }
    }
  }

  return newNode;
}

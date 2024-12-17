import { APIClassType } from "@/types/api";
import { Edge } from "@xyflow/react";
import { cloneDeep } from "lodash";

export function processNodeAdvancedFields(
  resData: APIClassType,
  edges: Edge[],
  nodeId: string,
) {
  let newNode = cloneDeep(resData);

  const relevantEdges = edges.filter(
    (edge) => edge.source !== nodeId || edge.target !== nodeId,
  );

  if (relevantEdges.length === 0) {
    return newNode;
  }

  for (const edge of relevantEdges) {
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

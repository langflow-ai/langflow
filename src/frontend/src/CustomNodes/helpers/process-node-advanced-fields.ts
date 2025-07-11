import type { APIClassType } from "@/types/api";
import type { EdgeType } from "@/types/flow";
import { cloneDeep } from "lodash";

export function processNodeAdvancedFields(
  resData: APIClassType,
  edges: EdgeType[],
  nodeId: string,
) {
  const newNode = cloneDeep(resData);

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

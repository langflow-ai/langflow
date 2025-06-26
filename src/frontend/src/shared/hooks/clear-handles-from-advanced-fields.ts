import useFlowStore from "@/stores/flowStore";
import { APIClassType } from "@/types/api";

export const clearHandlesFromAdvancedFields = (
  componentId: string,
  data: APIClassType,
): void => {
  if (!componentId || !data?.template) {
    return;
  }

  try {
    const flowStore = useFlowStore.getState();
    const { edges, deleteEdge } = flowStore;

    const connectedEdges = edges.filter((edge) => edge.target === componentId);

    if (connectedEdges.length === 0) {
      return;
    }

    const edgeIdsToDelete: string[] = [];

    for (const edge of connectedEdges) {
      const fieldName = edge.data?.targetHandle?.fieldName;

      if (fieldName && isAdvancedField(data, fieldName)) {
        edgeIdsToDelete.push(edge.id);
      }
    }

    edgeIdsToDelete.forEach(deleteEdge);
  } catch (error) {
    console.error("Error clearing handles from advanced fields:", error);
  }
};

const isAdvancedField = (data: APIClassType, fieldName: string): boolean => {
  const field = data.template[fieldName];
  return field && "advanced" in field && field.advanced === true;
};

import type { VertexBuildTypeAPI } from "@/types/api";
import { useEffect } from "react";
import type { FlowPoolType } from "../../types/zustand/flow";

const useUpdateValidationStatus = (
  dataId: string,
  flowPool: FlowPoolType,
  setValidationStatus: (value: any) => void,
  getValidationStatus: (data) => VertexBuildTypeAPI | null,
) => {
  useEffect(() => {
    const relevantData =
      flowPool[dataId] && flowPool[dataId]?.length > 0
        ? flowPool[dataId][flowPool[dataId].length - 1]
        : null;
    if (relevantData) {
      // Extract validation information from relevantData and update the validationStatus state
      setValidationStatus(relevantData);
    } else {
      setValidationStatus(null);
    }
    getValidationStatus(relevantData);
  }, [flowPool[dataId], dataId, setValidationStatus]);
};

export default useUpdateValidationStatus;

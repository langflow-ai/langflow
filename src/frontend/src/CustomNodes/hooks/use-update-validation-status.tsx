import { useEffect } from "react";
import { FlowPoolType } from "../../types/zustand/flow";

const useUpdateValidationStatus = (
  dataId: string,
  flowPool: FlowPoolType,
  setValidationStatus: (value: any) => void,
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
  }, [flowPool[dataId], dataId, setValidationStatus]);
};

export default useUpdateValidationStatus;

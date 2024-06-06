import { useEffect } from "react";

const useSelectedFlowsComponentsCards = (
  entireFormValues,
  setSelectedFlowsComponentsCards
) => {
  useEffect(() => {
    if (!entireFormValues || Object.keys(entireFormValues).length === 0) return;
    const selectedFlows: string[] = Object.keys(entireFormValues).filter(
      (key) => {
        if (entireFormValues[key] === true) {
          return true;
        }
        return false;
      }
    );

    setSelectedFlowsComponentsCards(selectedFlows);
  }, [entireFormValues]);
};

export default useSelectedFlowsComponentsCards;

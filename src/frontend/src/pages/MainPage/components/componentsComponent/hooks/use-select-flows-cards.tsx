import { useEffect } from "react";

const useSelectedFlowsComponentsCards = (
  entireFormValues,
  setSelectedFlowsComponentsCards,
  selectedFlowsComponentsCards
) => {
  useEffect(() => {
    if (!entireFormValues || Object.keys(entireFormValues).length === 0) return;

    const selectedFlows = Object.keys(entireFormValues).filter(
      (key) => entireFormValues[key] === true
    );

    setSelectedFlowsComponentsCards(selectedFlows);
  }, [entireFormValues]);

  return selectedFlowsComponentsCards;
};

export default useSelectedFlowsComponentsCards;

import { useEffect } from "react";

const useSelectedFlows = (
  entireFormValues,
  setSelectedFlowsComponentsCards,
) => {
  useEffect(() => {
    if (!entireFormValues || Object.keys(entireFormValues).length === 0) return;

    const selectedFlows = Object.keys(entireFormValues).filter((key) => {
      return entireFormValues[key] === true;
    });

    setSelectedFlowsComponentsCards(selectedFlows);
  }, [entireFormValues, setSelectedFlowsComponentsCards]);
};

export default useSelectedFlows;

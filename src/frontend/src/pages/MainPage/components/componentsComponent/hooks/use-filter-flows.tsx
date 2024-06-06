import cloneDeep from "lodash/cloneDeep"; // Assuming you're using lodash for cloneDeep
import { useEffect } from "react";

const useFilterFlows = (
  flowsFromFolder,
  searchFlowsComponents,
  setAllFlows
) => {
  useEffect(() => {
    if (!flowsFromFolder) return;

    const newFlows = cloneDeep(flowsFromFolder);
    const filteredFlows = newFlows.filter(
      (f) =>
        f.name.toLowerCase().includes(searchFlowsComponents.toLowerCase()) ||
        f.description
          .toLowerCase()
          .includes(searchFlowsComponents.toLowerCase())
    );

    if (searchFlowsComponents === "") {
      setAllFlows(flowsFromFolder);
    } else {
      setAllFlows(filteredFlows);
    }
  }, [searchFlowsComponents, flowsFromFolder, setAllFlows]);
};

export default useFilterFlows;

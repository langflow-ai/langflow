import cloneDeep from "lodash/cloneDeep"; // Assuming you're using lodash for cloneDeep
import { useEffect } from "react";

const useFilterFlows = (
  flowsFromFolder,
  searchFlowsComponents,
  setAllFlows
) => {
  useEffect(() => {
    const newFlows = cloneDeep(flowsFromFolder!);
    const filteredFlows = newFlows?.filter(
      (f) =>
        f.name.toLowerCase().includes(searchFlowsComponents.toLowerCase()) ||
        f.description
          .toLowerCase()
          .includes(searchFlowsComponents.toLowerCase())
    );

    if (searchFlowsComponents === "") {
      setAllFlows(flowsFromFolder!);
    }

    setAllFlows(filteredFlows);
  }, [searchFlowsComponents]);
};

export default useFilterFlows;

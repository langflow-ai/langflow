import cloneDeep from "lodash/cloneDeep";
import { useEffect } from "react";
import { FlowType } from "../../../types/flow";

const useFilteredFlows = (
  flowsFromFolder: FlowType[],
  searchFlowsComponents: string,
  setAllFlows: (value: any[]) => void,
) => {
  useEffect(() => {
    const newFlows = cloneDeep(flowsFromFolder || []);
    const filteredFlows = newFlows.filter(
      (f) =>
        f.name.toLowerCase().includes(searchFlowsComponents.toLowerCase()) ||
        f.description
          .toLowerCase()
          .includes(searchFlowsComponents.toLowerCase()),
    );

    if (searchFlowsComponents === "") {
      setAllFlows(flowsFromFolder);
    } else {
      setAllFlows(filteredFlows);
    }
  }, [flowsFromFolder, searchFlowsComponents, setAllFlows]);
};

export default useFilteredFlows;

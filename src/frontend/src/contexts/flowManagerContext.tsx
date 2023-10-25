import { createContext, useState } from "react";
import { NodeType } from "../types/flow";
import { FlowManagerContextType, FlowPoolType } from "../types/contexts/flowManager";
import { cloneDeep, flow } from "lodash";

const initialValue: FlowManagerContextType = {
    flowPool: {},
    updateFlowPoolNodes: (nodes: NodeType[]) => { },
    addDataToFlowPool: (data: any, nodeId: string) => { },
};

export const flowManagerContext = createContext(initialValue);

export default function FlowManagerProvider({ children }) {
    const [flowPool, setFlowPool] = useState<FlowPoolType>({});

    function updateFlowPoolNodes(nodes: NodeType[]) {
        //this function will update the removing the old ones
        const nodeIdsSet = new Set(nodes.map(node => node.id));
        setFlowPool((oldFlowPool) => {
            let newFlowPool = cloneDeep({ ...oldFlowPool });
            Object.keys(newFlowPool).forEach(nodeId => {
                if (!nodeIdsSet.has(nodeId)) {
                    delete flowPool[nodeId];
                }
            })
        })
    }

    function addDataToFlowPool(data: any, nodeId: string) {
        flowPool[nodeId] = data;
    }

    return (
        <flowManagerContext.Provider value={{flowPool,addDataToFlowPool,updateFlowPoolNodes}}>
            {children}
        </flowManagerContext.Provider>
    );
}
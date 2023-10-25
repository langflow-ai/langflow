import { createContext, useState } from "react";
import { FlowType, NodeDataType, NodeType } from "../types/flow";
import { FlowManagerContextType, FlowPoolType } from "../types/contexts/flowManager";
import { cloneDeep, flow } from "lodash";
import { isInputNode, isOutputNode } from "../utils/reactflowUtils";

const initialValue: FlowManagerContextType = {
    flowPool: {},
    updateFlowPoolNodes: (nodes: NodeType[]) => { },
    addDataToFlowPool: (data: any, nodeId: string) => { },
    checkInputandOutput: (flow:FlowType)=>false
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

    function checkInputandOutput(flow:FlowType):boolean{
        let has_input= false;
        let has_output = false;
        flow.data?.nodes.forEach(node=>{
            const nodeData: NodeDataType = node.data as NodeDataType;
            if(isInputNode(nodeData)){
                has_input = true;
            }
            if(isOutputNode(nodeData)){
                has_output = true;
            }
        })
        return has_input && has_output;
    }

    return (
        <flowManagerContext.Provider value={{flowPool,addDataToFlowPool,updateFlowPoolNodes,checkInputandOutput}}>
            {children}
        </flowManagerContext.Provider>
    );
}
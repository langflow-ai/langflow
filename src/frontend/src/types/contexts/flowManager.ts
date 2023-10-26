import { FlowType, NodeType } from "../flow";

export type FlowPoolType = {
    //TODO improve the flowPool type
    [key: string]: any;
}

export type FlowManagerContextType = {
    flowPool: FlowPoolType;
    updateFlowPoolNodes: (nodes:NodeType[]) => void,
    addDataToFlowPool: (data:any,nodeId:string) => void,
    checkInputandOutput: (flow:FlowType) => boolean,
    getInputTypes: (flow:FlowType) => string[],
    getOutputTypes: (flow:FlowType) => string[],
}
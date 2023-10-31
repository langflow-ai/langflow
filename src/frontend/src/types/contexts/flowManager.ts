import { ReactFlowInstance } from "reactflow";
import { FlowType, NodeType } from "../flow";

export type FlowPoolType = {
    //TODO improve the flowPool type
    [key: string]: any;
}

export type FlowManagerContextType = {
    deleteEdge: (idx: string | Array<string>) => void;
    deleteNode: (idx: string | Array<string>) => void;
    reactFlowInstance: ReactFlowInstance | null;
    setReactFlowInstance: (newState: ReactFlowInstance) => void;
    flowPool: FlowPoolType;
    updateFlowPoolNodes: (nodes:NodeType[]) => void,
    addDataToFlowPool: (data:any,nodeId:string) => void,
    checkInputandOutput: (flow:FlowType) => boolean,
    getInputTypes: (flow:FlowType) => string[],
    getOutputTypes: (flow:FlowType) => string[],
    getInputIds: (flow: FlowType) => string[],
    getOutputIds: (flow: FlowType) => string[],
}
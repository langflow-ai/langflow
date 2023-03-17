import { ReactFlowInstance } from 'reactflow';
import { FlowType } from "../flow";

export type ChatType = {flow:FlowType,reactFlowInstance:ReactFlowInstance}
export type ChatMessageType = { message: string; isSend: boolean, thought?:string }
import { ReactFlowInstance } from "reactflow";
import { FlowType } from "../flow";

export type ChatType = { flow: FlowType; reactFlowInstance: ReactFlowInstance };
export type ChatMessageType = {
  message: string;
  isSend: boolean;
  thought?: string;
  files?: Array<{ data: string; type: string; data_type: string }>;
};

import { ChatMessageType } from "./../chat/index";
import { APIClassType } from "../api/index";
import { ReactFlowJsonObject, XYPosition } from "reactflow";

export type FlowType = {
  name: string;
  id: string;
  data: ReactFlowJsonObject;
  description: string;
};
export type NodeType = {
  id: string;
  type?: string;
  position: XYPosition;
  data: NodeDataType;
};
export type NodeDataType = {
  type: string;
  node?: APIClassType;
  id: string;
  value: any;
};

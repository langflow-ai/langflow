import { ReactFlowJsonObject, XYPosition } from "reactflow";
import { APIClassType } from "../api/index";

export type FlowType = {
  name: string;
  id: string;
  data: ReactFlowJsonObject;
  description: string;
  style?: FlowStyleType;
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
// FlowStyleType is the type of the style object that is used to style the
// Flow card with an emoji and a color.
export type FlowStyleType = {
  emoji: string;
  color: string;
  flow_id: string;
};

export type TweaksType = Array<
  {
    [key: string]: {
      output_key?: string;
    };
  } & FlowStyleType
>;

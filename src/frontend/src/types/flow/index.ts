import type { Edge, Node, ReactFlowJsonObject } from "@xyflow/react";
import type { BuildStatus } from "../../constants/enums";
import type { APIClassType, OutputFieldType } from "../api/index";

export type PaginatedFlowsType = {
  items: FlowType[];
  total: number;
  size: number;
  page: number;
  pages: number;
};

export type FlowType = {
  name: string;
  id: string;
  data: ReactFlowJsonObject<AllNodeType, EdgeType> | null;
  description: string;
  endpoint_name?: string | null;
  style?: FlowStyleType;
  is_component?: boolean;
  last_tested_version?: string;
  updated_at?: string;
  date_created?: string;
  parent?: string;
  folder?: string;
  user_id?: string;
  icon?: string;
  gradient?: string;
  tags?: string[];
  icon_bg_color?: string;
  folder_id?: string;
  webhook?: boolean;
  locked?: boolean | null;
  public?: boolean;
  access_type?: "PUBLIC" | "PRIVATE" | "PROTECTED";
  mcp_enabled?: boolean;
};

export type GenericNodeType = Node<NodeDataType, "genericNode">;
export type NoteNodeType = Node<NoteDataType, "noteNode">;

export type AllNodeType = GenericNodeType | NoteNodeType;
export type SetNodeType<T = "genericNode" | "noteNode"> =
  T extends "genericNode" ? GenericNodeType : NoteNodeType;

export type noteClassType = Pick<
  APIClassType,
  "description" | "display_name" | "documentation" | "tool_mode" | "frozen"
> & {
  template: {
    backgroundColor?: string;
    [key: string]: any;
  };
  outputs?: OutputFieldType[];
};

export type NoteDataType = {
  showNode?: boolean;
  type: string;
  node: noteClassType;
  id: string;
};
export type NodeDataType = {
  showNode?: boolean;
  type: string;
  node: APIClassType;
  id: string;
  output_types?: string[];
  selected_output_type?: string;
  buildStatus?: BuildStatus;
  selected_output?: string;
};

export type EdgeType = Edge<EdgeDataType, "default">;

export type EdgeDataType = {
  sourceHandle: sourceHandleType;
  targetHandle: targetHandleType;
};

// Utility functions for computing effective alias from JSON data
export function getEffectiveAlias(nodeData: NodeDataType): string {
  return nodeData.node.alias || nodeData.node.display_name;
}

export function getEffectiveAliasFromNode(node: GenericNodeType): string {
  return node.data.node.alias || node.data.node.display_name;
}

export function getEffectiveAliasFromAnyNode(node: AllNodeType): string {
  if (node.type === "genericNode") {
    return getEffectiveAliasFromNode(node);
  }
  // For note nodes or other types, fallback to a reasonable display
  return node.data?.node?.display_name || "Unknown";
}

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

// right side
export type sourceHandleType = {
  baseClasses?: string[];
  dataType: string;
  id: string;
  output_types: string[];
  conditionalPath?: string | null;
  name: string;
};
//left side
export type targetHandleType = {
  inputTypes?: string[];
  output_types?: string[];
  type: string;
  fieldName: string;
  name?: string;
  id: string;
  proxy?: { field: string; id: string };
};

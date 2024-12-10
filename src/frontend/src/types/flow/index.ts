import { ReactFlowJsonObject, XYPosition } from "reactflow";
import { BuildStatus } from "../../constants/enums";
import { APIClassType } from "../api/index";

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
  data: ReactFlowJsonObject | null;
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
};

export type NodeType = {
  id: string;
  type?: string;
  position: XYPosition;
  data: NodeDataType;
  selected?: boolean;
};

export interface noteClassType
  extends Pick<APIClassType, "description" | "display_name" | "documentation"> {
  template: {
    backgroundColor: string;
    [key: string]: any;
  };
}

export interface noteDataType
  extends Pick<NodeDataType, "showNode" | "type" | "id"> {
  showNode?: boolean;
  type: string;
  node?: noteClassType;
  id: string;
}
export type NodeDataType = {
  showNode?: boolean;
  type: string;
  node?: APIClassType;
  id: string;
  output_types?: string[];
  selected_output_type?: string;
  buildStatus?: BuildStatus;
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

// right side
export type sourceHandleType = {
  dataType: string;
  id: string;
  output_types: string[];
  conditionalPath?: string | null;
  name: string;
};
//left side
export type targetHandleType = {
  inputTypes?: string[];
  type: string;
  fieldName: string;
  id: string;
  proxy?: { field: string; id: string };
};

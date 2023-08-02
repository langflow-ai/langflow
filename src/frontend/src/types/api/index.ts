import { Edge, Node, Viewport } from "reactflow";
//kind and class are just representative names to represent the actual structure of the object received by the API

export type APIObjectType = { kind: APIKindType; [key: string]: APIKindType };
export type APIKindType = { class: APIClassType; [key: string]: APIClassType };
export type APITemplateType = {
  variable: TemplateVariableType;
  [key: string]: TemplateVariableType;
};
export type APIClassType = {
  base_classes: Array<string>;
  description: string;
  template: APITemplateType;
  display_name: string;
  input_types?: Array<string>;
  output_types?: Array<string>;
  beta?: boolean;
  documentation: string;
  error?: string;
  [key: string]: Array<string> | string | APITemplateType | boolean;
};

export type TemplateVariableType = {
  type: string;
  required: boolean;
  placeholder?: string;
  list: boolean;
  show: boolean;
  multiline?: boolean;
  value?: any;
  input_types?: Array<string>;
  [key: string]: any;
};
export type sendAllProps = {
  nodes: Node[];
  edges: Edge[];
  name: string;
  description: string;
  viewport: Viewport;
  inputs: any;

  chatHistory: { message: string | object; isSend: boolean }[];
};
export type errorsTypeAPI = {
  function: { errors: Array<string> };
  imports: { errors: Array<string> };
};
export type PromptTypeAPI = {
  input_variables: Array<string>;
  frontend_node: APIClassType;
};

export type BuildStatusTypeAPI = {
  built: boolean;
};

export type InitTypeAPI = {
  flowId: string;
};

export type UploadFileTypeAPI = {
  file_path: string;
  flowId: string;
};

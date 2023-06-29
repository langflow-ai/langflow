import { ReactFlowInstance } from "reactflow";
import { APIClassType } from "../api";

const types: { [char: string]: string } = {};
const template: { [char: string]: APIClassType } = {};
const data: { [char: string]: string } = {};

export type typesContextType = {
  reactFlowInstance: ReactFlowInstance | null;
  setReactFlowInstance: any;
  deleteNode: (idx: string) => void;
  types: typeof types;
  setTypes: (newState: {}) => void;
  templates: typeof template;
  setTemplates: (newState: {}) => void;
  data: typeof data;
  setData: (newState: {}) => void;
};

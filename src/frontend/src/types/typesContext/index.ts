import { ReactFlowInstance } from "reactflow";

const types: { [char: string]: string } = {};
const template: { [char: string]: string } = {};
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

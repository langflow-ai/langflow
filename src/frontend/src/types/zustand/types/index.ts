import { APIClassType, APIDataType } from "../../api";

export type TypesStoreType = {
  types: { [char: string]: string };
  setTypes: (newState: {}) => void;
  templates: { [char: string]: APIClassType };
  setTemplates: (newState: {}) => void;
  data: APIDataType;
  setData: (newState: {}) => void;
  ComponentFields: Set<string>;
  setComponentFields: (fields: Set<string>) => void;
  addComponentField: (field: string) => void;
};

import type {
  APIClassType,
  APIDataType,
  ComponentDisplayNamesType,
} from "../../api";

export type TypesStoreType = {
  activeScopeKey: string | null;
  activateScope: (scopeKey: string) => void;
  clearScopedTypes: (scopeKey: string) => boolean;
  setScopedTypes: (
    scopeKey: string,
    data: APIDataType,
    componentDisplayNames: ComponentDisplayNamesType,
  ) => boolean;
  types: { [char: string]: string };
  setTypes: (newState: {}) => void;
  templates: { [char: string]: APIClassType };
  setTemplates: (newState: {}) => void;
  data: APIDataType;
  setData: (newState: {}) => void;
  ComponentFields: Set<string>;
  setComponentFields: (fields: Set<string>) => void;
  addComponentField: (field: string) => void;
  componentDisplayNames: ComponentDisplayNamesType;
  setComponentDisplayNames: (data: ComponentDisplayNamesType) => void;
};

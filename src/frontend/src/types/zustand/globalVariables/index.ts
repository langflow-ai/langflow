export type GlobalVariablesStore = {
  globalVariablesEntries: Array<string>;
  setGlobalVariablesEntries: (entries: Array<string>) => void;
  unavailableFields: { [name: string]: string };
  setUnavailableFields: (fields: { [name: string]: string }) => void;
};

export type GlobalVariablesStore = {
  globalVariablesEntries: Array<string>;
  globalVariables: { [key: string]: string };
  setGlobalVariables: (variables: { [key: string]: string }) => void;
  addGlobalVariable: (key: string, value: string) => void;
  removeGlobalVariable: (key: string) => void;
};

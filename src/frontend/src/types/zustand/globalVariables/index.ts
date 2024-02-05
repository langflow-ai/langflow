export type GlobalVariablesStore = {
  globalVariablesEntries: Array<string>;
  globalVariables: { [key: string]: string };
  setGlobalVariables: (variables: { [key: string]: string }) => void;
};

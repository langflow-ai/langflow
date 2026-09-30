export type { GlobalVariable } from "@/types/global_variables";

export interface UnavailableFields {
  [key: string]: string;
}

export interface GlobalVariableHandlers {
  handleVariableDelete: (variableName: string) => void;
  handleVariableSelect: (selectedValue: string) => void;
  handleInputChange: (inputValue: string, skipSnapshot?: boolean) => void;
}

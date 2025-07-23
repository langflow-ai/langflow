export interface GlobalVariable {
  name: string;
  // Add other properties as needed
}

export interface UnavailableFields {
  [key: string]: string;
}

export interface GlobalVariableHandlers {
  handleVariableDelete: (variableName: string) => void;
  handleVariableSelect: (selectedValue: string) => void;
  handleInputChange: (inputValue: string, skipSnapshot?: boolean) => void;
} 
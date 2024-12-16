import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { APIClassType, InputFieldType, TableOptionsTypeAPI } from "@/types/api";
import { RangeSpecType } from "@/types/components";
import { ColumnField } from "@/types/utils/functions";

// Base type for RefreshParameterComponent children
export type BaseInputProps<valueType = any> = {
  id: string;
  value: valueType;
  editNode: boolean;
  handleOnNewValue: handleOnNewValueType;
  disabled: boolean;
  nodeClass?: APIClassType;
  handleNodeClass?: (value: any, code?: string, type?: string) => void;
  readonly?: boolean;
  placeholder?: string;
  isToolMode?: boolean;
};

// Generic type for composing input props
export type InputProps<
  valueType = any,
  T = {},
  U extends object = object,
> = BaseInputProps<valueType> & T & { placeholder?: string };

export type TableComponentType = {
  description: string;
  tableTitle: string;
  columns?: ColumnField[];
  table_options?: TableOptionsTypeAPI;
  trigger_text?: string;
  trigger_icon?: string;
};

export type FloatComponentType = {
  rangeSpec: RangeSpecType;
};

export type IntComponentType = {
  rangeSpec: RangeSpecType;
};
export type ToggleComponentType = {
  size?: "small" | "medium" | "large";
  showToogle?: boolean;
};

export type FileComponentType = {
  fileTypes: Array<string>;
};

export type PromptAreaComponentType = {
  field_name?: string;
};

export type LinkComponentType = {
  icon?: string;
  text?: string;
};

export type KeyPairListComponentType = {
  value: any;
  isList?: boolean;
};

export type StrRenderComponentType = {
  templateData: Partial<InputFieldType>;
  name: string;
  display_name: string;
};

export type InputListComponentType = {
  componentName?: string;
  id?: string;
};

export type DropDownComponentType = {
  combobox?: boolean;
  options: string[];
  name: string;
};

export type TextAreaComponentType = {
  password?: boolean;
  updateVisibility?: () => void;
};

export type InputGlobalComponentType = {
  load_from_db: boolean | undefined;
  password: boolean | undefined;
  display_name: string;
};
export type MultiselectComponentType = {
  options: string[];
  combobox?: boolean;
};

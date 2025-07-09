import type { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import type {
  APIClassType,
  APITemplateType,
  InputFieldType,
  TableOptionsTypeAPI,
} from "@/types/api";
import type { RangeSpecType } from "@/types/components";
import type { ColumnField } from "@/types/utils/functions";

// Base type for RefreshParameterComponent children
export type BaseInputProps<valueType = any> = {
  id: string;
  value: valueType;
  editNode: boolean;
  handleOnNewValue: handleOnNewValueType;
  disabled: boolean;
  nodeClass?: APIClassType;
  helperText?: string;
  handleNodeClass?: (value: any, code?: string, type?: string) => void;
  readonly?: boolean;
  placeholder?: string;
  isToolMode?: boolean;
  tooltip?: string;
  metadata?: any;
  nodeId?: string;
  nodeInformationMetadata?: NodeInfoType;
  hasRefreshButton?: boolean;
  helperMetadata?: any;
  options?: any[];
  searchCategory?: string[];
  buttonMetadata?: { variant?: string; icon?: string };
  connectionLink?: string;
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
  table_icon?: string;
};

export type ToolsComponentType = {
  description: string;
  title: string;
  icon?: string;
  button_description?: string;
  isAction?: boolean;
  template?: APITemplateType;
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
  file_path?: string | string[];
  isList?: boolean;
  tempFile?: boolean;
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
  nodeId: string;
  nodeClass: APIClassType;
  handleNodeClass: (value: any, code?: string, type?: string) => void;
};

export type InputListComponentType = {
  componentName?: string;
  id?: string;
  listAddLabel?: string;
};

export type DropDownComponentType = {
  combobox?: boolean;
  options: string[];
  name: string;
  dialogInputs?: any;
  optionsMetaData?: any[];
  nodeId: string;
  nodeClass: APIClassType;
  handleNodeClass: (value: any, code?: string, type?: string) => void;
  toggle?: boolean;
  toggleValue?: boolean;
  toggleDisable?: boolean;
};

export type TextAreaComponentType = {
  password?: boolean;
  updateVisibility?: () => void;
};

export type QueryComponentType = {
  display_name: string;
  info: string;
  separator?: string;
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

export type TabComponentType = {
  options: string[];
};

export type NodeInfoType = {
  flowId: string;
  nodeType: string;
  flowName: string;
  isAuth: boolean;
  variableName: string;
};

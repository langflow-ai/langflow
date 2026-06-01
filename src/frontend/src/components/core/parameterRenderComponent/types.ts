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
// biome-ignore lint/suspicious/noExplicitAny: legacy
export type BaseInputProps<valueType = any> = {
  id: string;
  value: valueType;
  editNode: boolean;
  handleOnNewValue: handleOnNewValueType;
  disabled: boolean;
  nodeClass?: APIClassType;
  helperText?: string;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  handleNodeClass?: (value: any, code?: string, type?: string) => void;
  readonly?: boolean;
  placeholder?: string;
  isToolMode?: boolean;
  tooltip?: string;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  metadata?: any;
  nodeId?: string;
  nodeInformationMetadata?: NodeInfoType;
  hasRefreshButton?: boolean;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  helperMetadata?: any;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  options?: any[];
  searchCategory?: string[];
  buttonMetadata?: { variant?: string; icon?: string };
  connectionLink?: string;
  showParameter?: boolean;
  inspectionPanel?: boolean;
};

// Generic type for composing input props
export type InputProps<
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  valueType = any,
  T = {},
  _U extends object = object,
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
  hideButton?: boolean;
  open?: boolean;
  setOpen?: (open: boolean) => void;
};

export type FloatComponentType = {
  rangeSpec: RangeSpecType;
};

export type IntComponentType = {
  rangeSpec: RangeSpecType;
  name?: string;
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
  isDoubleBrackets?: boolean;
};

export type LinkComponentType = {
  icon?: string;
  text?: string;
};

export type KeyPairListComponentType = {
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  value: any;
  isList?: boolean;
};

export type StrRenderComponentType = {
  templateData: Partial<InputFieldType>;
  name: string;
  display_name: string;
  nodeId: string;
  nodeClass: APIClassType;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
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
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  dialogInputs?: any;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  externalOptions?: any;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  optionsMetaData?: any[];
  nodeId: string;
  nodeClass: APIClassType;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
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
  hideOnSelection?: boolean;
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

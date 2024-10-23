import { handleOnNewValueType } from "@/CustomNodes/hooks/use-handle-new-value";
import { ReactElement, ReactNode } from "react";
import { ReactFlowJsonObject } from "reactflow";
import { InputOutput } from "../../constants/enums";
import {
  APIClassType,
  APITemplateType,
  InputFieldType,
  OutputFieldProxyType,
} from "../api";
import { ChatMessageType } from "../chat";
import { FlowStyleType, FlowType, NodeDataType, NodeType } from "../flow/index";
import { ColumnField } from "../utils/functions";
import { sourceHandleType, targetHandleType } from "./../flow/index";
export type InputComponentType = {
  name?: string;
  autoFocus?: boolean;
  onBlur?: (event: React.FocusEvent<HTMLInputElement>) => void;
  value?: string;
  disabled?: boolean;
  onChange?: (value: string, snapshot?: boolean) => void;
  password: boolean;
  required?: boolean;
  isForm?: boolean;
  editNode?: boolean;
  onChangePass?: (value: boolean | boolean) => void;
  showPass?: boolean;
  placeholder?: string;
  className?: string;
  id?: string;
  blurOnEnter?: boolean;
  optionsIcon?: string;
  optionsPlaceholder?: string;
  options?: string[];
  optionsButton?: ReactElement;
  optionButton?: (option: string) => ReactElement;
  selectedOption?: string;
  setSelectedOption?: (value: string) => void;
  selectedOptions?: string[];
  setSelectedOptions?: (value: string[]) => void;
  objectOptions?: Array<{ name: string; id: string }>;
  isObjectOption?: boolean;
  onChangeFolderName?: (e: any) => void;
};
export type DropDownComponent = {
  disabled?: boolean;
  isLoading?: boolean;
  value: string;
  combobox?: boolean;
  options: string[];
  onSelect: (value: string, dbValue?: boolean, snapshot?: boolean) => void;
  editNode?: boolean;
  id?: string;
  children?: ReactNode;
};
export type ParameterComponentType = {
  selected?: boolean;
  data: NodeDataType;
  title: string;
  conditionPath?: string | null;
  key: string;
  id: sourceHandleType | targetHandleType;
  colors: string[];
  left: boolean;
  type: string | undefined;
  required?: boolean;
  name?: string;
  tooltipTitle: string | undefined;
  optionalHandle?: Array<String> | null;
  info?: string;
  proxy?: { field: string; id: string };
  showNode?: boolean;
  index: number;
  onCloseModal?: (close: boolean) => void;
  outputName?: string;
  outputProxy?: OutputFieldProxyType;
};

export type NodeOutputFieldComponentType = {
  selected: boolean;
  data: NodeDataType;
  title: string;
  id: sourceHandleType;
  colors: string[];
  tooltipTitle: string | undefined;
  showNode: boolean;
  index: number;
  type: string | undefined;
  outputName?: string;
  outputProxy?: OutputFieldProxyType;
};

export type NodeInputFieldComponentType = {
  id: targetHandleType;
  data: NodeDataType;
  tooltipTitle: string | undefined;
  title: string;
  colors: string[];
  type: string | undefined;
  name: string;
  required: boolean;
  optionalHandle: Array<String> | undefined | null;
  info: string;
  proxy: { field: string; id: string } | undefined;
  showNode: boolean;
};

export type IOJSONInputComponentType = {
  value: any;
  onChange: (value) => void;
  left?: boolean;
  output?: boolean;
};
export type outputComponentType = {
  types: string[];
  selected: string;
  nodeId: string;
  frozen?: boolean;
  idx: number;
  name: string;
  proxy?: OutputFieldProxyType;
};

export type DisclosureComponentType = {
  children: ReactNode;
  defaultOpen: boolean;
  isChild?: boolean;
  button: {
    title: string;
    Icon: React.ElementType;
    buttons?: {
      Icon: ReactElement;
      title: string;
      onClick: (event?: React.MouseEvent) => void;
    }[];
    beta?: boolean;
  };
  testId?: string;
};

export type RangeSpecType = {
  min: number;
  max: number;
  step: number;
};

export type IntComponentType = {
  value: number;
  disabled?: boolean;
  rangeSpec: RangeSpecType;
  onChange: (value: number, dbValue?: boolean, skipSnapshot?: boolean) => void;
  editNode?: boolean;
  id?: string;
};

export type FloatComponentType = {
  value: string;
  disabled?: boolean;
  onChange: (
    value: string | number,
    dbValue?: boolean,
    skipSnapshot?: boolean,
  ) => void;
  rangeSpec: RangeSpecType;
  editNode?: boolean;
  id?: string;
};

export type SliderComponentType = {
  value: string;
  disabled?: boolean;
  rangeSpec: RangeSpecType;
  editNode?: boolean;
  id?: string;
  minLabel?: string;
  maxLabel?: string;
  minLabelIcon?: string;
  maxLabelIcon?: string;
  sliderButtons?: boolean;
  sliderButtonsOptions?: {
    label: string;
    id: number;
  }[];
  sliderInput?: boolean;
};

export type FilePreviewType = {
  loading: boolean;
  file: File;
  error: boolean;
  id: string;
  path?: string;
};

export type TooltipComponentType = {
  children: ReactElement;
  title: string | ReactElement;
  placement?:
    | "bottom-end"
    | "bottom-start"
    | "bottom"
    | "left-end"
    | "left-start"
    | "left"
    | "right-end"
    | "right-start"
    | "right"
    | "top-end"
    | "top-start"
    | "top";
};

export type ProgressBarType = {
  children?: ReactElement;
  value?: number;
  max?: number;
};

export type AccordionComponentType = {
  children?: ReactElement;
  open?: string[];
  trigger?: string | ReactElement;
  disabled?: boolean;
  keyValue?: string;
  openDisc?: boolean;
  sideBar?: boolean;
  options?: { title: string; icon: string }[];
};
export type Side = "top" | "right" | "bottom" | "left";

export type ShadTooltipProps = {
  delayDuration?: number;
  side?: Side;
  content: ReactNode;
  children: ReactNode;
  style?: string;
};
export type ShadToolTipType = {
  open?: boolean;
  setOpen?: (open: boolean) => void;
  content?: ReactNode | null;
  side?: "top" | "right" | "bottom" | "left";
  asChild?: boolean;
  children?: ReactElement;
  delayDuration?: number;
  styleClasses?: string;
};

export type TextHighlightType = {
  value?: string;
  side?: "top" | "right" | "bottom" | "left";
  asChild?: boolean;
  children?: ReactElement;
  delayDuration?: number;
};

export interface IVarHighlightType {
  name: string;
}

export type IconComponentProps = {
  name: string;
  className?: string;
  iconColor?: string;
  onClick?: () => void;
  stroke?: string;
  strokeWidth?: number;
  id?: string;
  skipFallback?: boolean;
};

export type InputProps = {
  name: string | null;
  description: string | null;
  endpointName?: string | null;
  maxLength?: number;
  setName?: (name: string) => void;
  setDescription?: (description: string) => void;
  setEndpointName?: (endpointName: string) => void;
  invalidNameList?: string[];
};

export type TooltipProps = {
  selector: string;
  content?: string;
  disabled?: boolean;
  htmlContent?: React.ReactNode;
  className?: string; // This should use !impornant to override the default styles eg: '!bg-white'
  position?: "top" | "right" | "bottom" | "left";
  clickable?: boolean;
  children: React.ReactNode;
  delayShow?: number;
};

export type LoadingComponentProps = {
  remSize: number;
};

export type ContentProps = {
  children: ReactNode;
};
export type HeaderProps = { children: ReactNode; description: string };
export type TriggerProps = {
  children: ReactNode;
  tooltipContent?: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
};

export interface languageMap {
  [key: string]: string | undefined;
}

export type signUpInputStateType = {
  password: string;
  cnfPassword: string;
  username: string;
};

export type inputHandlerEventType = {
  target: {
    value: string | boolean;
    name: string;
  };
};
export type PaginatorComponentType = {
  pageSize: number;
  pageIndex: number;
  rowsCount?: number[];
  totalRowsCount: number;
  paginate: (pageIndex: number, pageSize: number) => void;
  storeComponent?: boolean;
  pages?: number;
};

export type ConfirmationModalType = {
  onCancel?: () => void;
  title: string;
  titleHeader?: string;
  destructive?: boolean;
  destructiveCancel?: boolean;
  modalContentTitle?: string;
  loading?: boolean;
  cancelText?: string;
  confirmationText?: string;
  children:
    | [React.ReactElement<ContentProps>, React.ReactElement<TriggerProps>]
    | React.ReactElement<ContentProps>;
  icon?: string;
  data?: any;
  index?: number;
  onConfirm?: (index, data) => void;
  open?: boolean;
  onClose?: () => void;
  size?:
    | "x-small"
    | "smaller"
    | "small"
    | "medium"
    | "large"
    | "large-h-full"
    | "small-h-full"
    | "medium-h-full";
  onEscapeKeyDown?: (e: KeyboardEvent) => void;
};

export type UserManagementType = {
  title: string;
  titleHeader: string;
  cancelText: string;
  confirmationText: string;
  children: ReactElement;
  icon: string;
  data?: any;
  index?: number;
  asChild?: boolean;
  onConfirm: (index, data) => void;
};

export type loginInputStateType = {
  username: string;
  password: string;
};

export type patchUserInputStateType = {
  password: string;
  cnfPassword: string;
  profilePicture: string;
  apikey: string;
  gradient?: any;
};

export type UserInputType = {
  username: string;
  password: string;
  is_active?: boolean;
  is_superuser?: boolean;
  id?: string;
  create_at?: string;
  updated_at?: string;
};

export type ApiKeyType = {
  children: ReactElement;
  data?: any;
  onCloseModal: () => void;
};

export type StoreApiKeyType = {
  children: ReactElement;
  disabled?: boolean;
};
export type groupedObjType = {
  family: string;
  type: string;
  display_name?: string;
};

export type nodeGroupedObjType = {
  displayName: string;
  node: string[] | string;
};

type test = {
  [char: string]: string;
};

export type tweakType = Array<{
  [key: string]: {
    [char: string]: string;
  } & FlowStyleType;
}>;

export type uniqueTweakType = {
  [key: string]: {
    [char: string]: string;
  } & FlowStyleType;
};

export type apiModalTweakType = {
  current: Array<{
    [key: string]: {
      [char: string]: string | number;
    };
  }>;
};

export type nodeToolbarType = {
  data: {
    id: string;
    type: string;
    node: {
      base_classes: string[];
      description: string;
      display_name: string;
      documentation: string;
      edited: boolean;
      template: APITemplateType;
    };
    value: void;
  };
  deleteNode: (idx: string) => void;
  openPopUp: (element: JSX.Element) => JSX.Element;
};

export type chatTriggerPropType = {
  open: boolean;
  isBuilt: boolean;
  canOpen: boolean;
  setOpen: (can: boolean) => void;
};

export type headerFlowsType = {
  data: ReactFlowJsonObject | null;
  description: string;
  id: string;
  name: string;
  style?: FlowStyleType;
};

export type ChatInputType = {
  isDragging: boolean;
  files: FilePreviewType[];
  setFiles: (
    files: FilePreviewType[] | ((prev: FilePreviewType[]) => FilePreviewType[]),
  ) => void;
  chatValue: string;
  inputRef: {
    current: any;
  };
  lockChat: boolean;
  noInput: boolean;
  sendMessage: ({
    repeat,
    files,
  }: {
    repeat: number;
    files?: string[];
  }) => void;
  setChatValue: (value: string) => void;
};

export type editNodeToggleType = {
  advanced?: boolean;
  info?: string;
  list: boolean;
  multiline?: boolean;
  name?: string;
  password?: boolean;
  placeholder?: string;
  required: boolean;
  show: boolean;
  type: string;
};

export interface Props {
  language: string;
  value: string;
}

export type fileCardPropsType = {
  fileName: string;
  path: string;
  fileType: string;
  showFile?: boolean;
};

export type nodeToolbarPropsType = {
  data: NodeDataType;
  deleteNode: (idx: string) => void;
  setShowNode: (boolean: any) => void;
  numberOfOutputHandles: number;
  showNode: boolean;
  name?: string;
  openAdvancedModal?: boolean;
  onCloseAdvancedModal?: (close: boolean) => void;
  isOutdated: boolean;
  updateNode: () => void;
};

export type parsedDataType = {
  id: string;
  params: string;
  progress: number;
  valid: boolean;
};

export type SanitizedHTMLWrapperType = {
  content: string;
  suppressWarning?: boolean;
};

export type iconsType = {
  [key: string]: React.ElementType;
};

export type modalHeaderType = {
  children: ReactNode;
  description: string | JSX.Element | null;
};

export type codeAreaModalPropsType = {
  setValue: (value: string) => void;
  setOpenModal?: (bool: boolean) => void;
  value: string;
  nodeClass: APIClassType | undefined;
  setNodeClass: (Class: APIClassType, type: string) => void | undefined;
  children: ReactNode;
  dynamic?: boolean;
  readonly?: boolean;
  open?: boolean;
  setOpen?: (open: boolean) => void;
};

export type chatMessagePropsType = {
  chat: ChatMessageType;
  lockChat: boolean;
  lastMessage: boolean;
  setLockChat: (lock: boolean) => void;
  updateChat: (
    chat: ChatMessageType,
    message: string,
    stream_url?: string,
  ) => void;
};

export type genericModalPropsType = {
  field_name?: string;
  setValue: (value: string) => void;
  value: string;
  buttonText: string;
  modalTitle: string;
  type: number;
  disabled?: boolean;
  nodeClass?: APIClassType;
  setNodeClass?: (Class: APIClassType, type?: string) => void;
  children: ReactNode;
  id?: string;
  readonly?: boolean;
  password?: boolean;
  changeVisibility?: () => void;
};

export type PromptModalType = {
  field_name?: string;
  setValue: (value: string) => void;
  value: string;
  disabled?: boolean;
  nodeClass?: APIClassType;
  setNodeClass?: (Class: APIClassType, type?: string) => void;
  children: ReactNode;
  id?: string;
  readonly?: boolean;
};

export type textModalPropsType = {
  setValue: (value: string) => void;
  value: string;
  disabled?: boolean;
  children: ReactNode;
  readonly?: boolean;
  password?: boolean;
  changeVisibility?: () => void;
};

export type newFlowModalPropsType = {
  open: boolean;
  setOpen: (open: boolean) => void;
};

export type IOModalPropsType = {
  children: JSX.Element;
  open: boolean;
  setOpen: (open: boolean) => void;
  disable?: boolean;
  isPlayground?: boolean;
  cleanOnClose?: boolean;
};

export type buttonBoxPropsType = {
  onClick: () => void;
  title: string;
  description: string;
  icon: ReactNode;
  bgColor: string;
  textColor: string;
  deactivate?: boolean;
  size: "small" | "medium" | "big";
};

export type FlowSettingsPropsType = {
  open: boolean;
  setOpen: (open: boolean) => void;
};

export type groupDataType = {
  [char: string]: string;
};

export type cardComponentPropsType = {
  data: FlowType;
  onDelete?: () => void;
  button?: JSX.Element;
};

export type tabsArrayType = {
  code: string;
  image: string;
  language: string;
  mode: string;
  name: string;
  description?: string;
  hasTweaks?: boolean;
};

export type codeTabsPropsType = {
  open?: boolean;
  tabs: Array<tabsArrayType>;
  activeTab: string;
  setActiveTab: (value: string) => void;
  isMessage?: boolean;
  tweaksNodes?: Array<NodeType>;
  activeTweaks?: boolean;
  setActiveTweaks?: (value: boolean) => void;
};

export type crashComponentPropsType = {
  error: {
    message: string;
    stack: string;
  };
  resetErrorBoundary: (args) => void;
};

export type Log = {
  message: string;
};

export type validationStatusType = {
  id: string;
  data: object | any;
  outputs: Log[];
  progress?: number;
  valid: boolean;
  duration?: string;
};

export type ApiKey = {
  id: string;
  api_key: string;
  name: string;
  created_at: string;
  last_used_at: string;
  total_uses: number;
};
export type fetchErrorComponentType = {
  message: string;
  description: string;
  openModal?: boolean;
  setRetry: () => void;
  isLoadingHealth: boolean;
};

export type dropdownButtonPropsType = {
  firstButtonName: string;
  onFirstBtnClick: () => void;
  options: Array<{ name: string; onBtnClick: () => void }>;
  plusButton?: boolean;
  dropdownOptions?: boolean;
  isFetchingFolders?: boolean;
};

export type IOFieldViewProps = {
  type: InputOutput;
  fieldType: string;
  fieldId: string;
  left?: boolean;
};

export type UndrawCardComponentProps = { flow: FlowType };

export type chatViewProps = {
  sendMessage: ({
    repeat,
    files,
  }: {
    repeat: number;
    files?: string[];
  }) => void;
  chatValue: string;
  setChatValue: (value: string) => void;
  lockChat: boolean;
  setLockChat: (lock: boolean) => void;
  visibleSession?: string;
  focusChat?: string;
};

export type IOFileInputProps = {
  field: InputFieldType;
  updateValue: (e: any, type: string) => void;
};

export type toolbarSelectItemProps = {
  value: string;
  icon: string;
  style?: string;
  dataTestId: string;
  ping?: boolean;
  shortcut: string;
};

export type clearChatPropsType = {
  lockChat: boolean;
  setLockChat: (lock: boolean) => void;
  setChatHistory: (chatHistory: ChatMessageType) => void;
  method: string;
};

export type handleSelectPropsType = {
  event: string;
  lockChat: boolean;
  setLockChat: (lock: boolean) => void;
  setChatHistory: (chatHistory: ChatMessageType) => void;
};

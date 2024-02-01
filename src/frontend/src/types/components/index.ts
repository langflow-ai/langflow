import { ReactElement, ReactNode } from "react";
import { ReactFlowJsonObject, XYPosition } from "reactflow";
import { APIClassType, APITemplateType, TemplateVariableType } from "../api";
import { ChatMessageType } from "../chat";
import { FlowStyleType, FlowType, NodeDataType, NodeType } from "../flow/index";
import { sourceHandleType, targetHandleType } from "./../flow/index";
export type InputComponentType = {
  autoFocus?: boolean;
  onBlur?: (event: React.FocusEvent<HTMLInputElement>) => void;
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
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
};
export type ToggleComponentType = {
  enabled: boolean;
  setEnabled: (state: boolean) => void;
  disabled: boolean | undefined;
  size: "small" | "medium" | "large";
  id?: string;
};
export type DropDownComponentType = {
  value: string;
  options: string[];
  onSelect: (value: string) => void;
  editNode?: boolean;
  apiModal?: boolean;
  numberOfOptions?: number;
  id?: string;
};
export type ParameterComponentType = {
  data: NodeDataType;
  title: string;
  id: sourceHandleType | targetHandleType;
  color: string;
  left: boolean;
  type: string | undefined;
  required?: boolean;
  name?: string;
  tooltipTitle: string | undefined;
  optionalHandle?: Array<String> | null;
  info?: string;
  proxy?: { field: string; id: string };
  showNode?: boolean;
  index?: string;
  onCloseModal?: (close: boolean) => void;
};
export type InputListComponentType = {
  value: string[];
  onChange: (value: string[]) => void;
  disabled: boolean;
  editNode?: boolean;
};

export type KeyPairListComponentType = {
  value: any;
  onChange: (value: Object[]) => void;
  disabled: boolean;
  editNode?: boolean;
  duplicateKey?: boolean;
  editNodeModal?: boolean;
};

export type DictComponentType = {
  value: any;
  onChange: (value) => void;
  disabled: boolean;
  editNode?: boolean;
  id?: string;
};

export type TextAreaComponentType = {
  field_name?: string;
  nodeClass?: APIClassType;
  setNodeClass?: (value: APIClassType) => void;
  disabled: boolean;
  onChange: (value: string[] | string) => void;
  value: string;
  editNode?: boolean;
  id?: string;
  readonly?: boolean;
};

export type PromptAreaComponentType = {
  field_name?: string;
  nodeClass?: APIClassType;
  setNodeClass?: (value: APIClassType, code?: string) => void;
  disabled: boolean;
  onChange: (value: string[] | string) => void;
  value: string;
  readonly?: boolean;
  editNode?: boolean;
  id?: string;
};

export type CodeAreaComponentType = {
  disabled: boolean;
  onChange: (value: string[] | string) => void;
  value: string;
  editNode?: boolean;
  nodeClass?: APIClassType;
  setNodeClass?: (value: APIClassType, code?: string) => void;
  dynamic?: boolean;
  id?: string;
  readonly?: boolean;
};

export type FileComponentType = {
  disabled: boolean;
  onChange: (value: string[] | string) => void;
  value: string;
  fileTypes: Array<string>;
  onFileChange: (value: string) => void;
  editNode?: boolean;
};

export type DisclosureComponentType = {
  children: ReactNode;
  openDisc: boolean;
  button: {
    title: string;
    Icon: React.ElementType;
    buttons?: {
      Icon: ReactElement;
      title: string;
      onClick: (event?: React.MouseEvent) => void;
    }[];
  };
};

export type RangeSpecType = {
  min: number;
  max: number;
  step: number;
};

export type IntComponentType = {
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  editNode?: boolean;
  id?: string;
};

export type FloatComponentType = {
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  rangeSpec: RangeSpecType;
  editNode?: boolean;
  id?: string;
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

export type RadialProgressType = {
  value?: number;
  color?: string;
};

export type AccordionComponentType = {
  children?: ReactElement;
  open?: string[];
  trigger?: string | ReactElement;
  keyValue?: string;
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
};

export type InputProps = {
  name: string | null;
  description: string | null;
  maxLength?: number;
  setName?: (name: string) => void;
  setDescription?: (description: string) => void;
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
    value: string;
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
};

export type ConfirmationModalType = {
  onCancel?: () => void;
  title: string;
  titleHeader?: string;
  destructive?: boolean;
  modalContentTitle?: string;
  cancelText: string;
  confirmationText: string;
  children:
    | [React.ReactElement<ContentProps>, React.ReactElement<TriggerProps>]
    | React.ReactElement<ContentProps>;
  icon: string;
  data?: any;
  index?: number;
  onConfirm: (index, data) => void;
  open?: boolean;
  onClose?: (close: boolean) => void;
  size?:
    | "x-small"
    | "smaller"
    | "small"
    | "medium"
    | "large"
    | "large-h-full"
    | "small-h-full"
    | "medium-h-full";
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
  gradient: string;
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
  title: string;
  cancelText: string;
  confirmationText: string;
  children: ReactElement;
  icon: string;
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

export type chatInputType = {
  chatValue: string;
  inputRef: {
    current: any;
  };
  lockChat: boolean;
  noInput: boolean;
  sendMessage: () => void;
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
  content: string;
  fileType: string;
};

export type nodeToolbarPropsType = {
  data: NodeDataType;
  deleteNode: (idx: string) => void;
  position: XYPosition;
  setShowNode: (boolean: any) => void;
  numberOfHandles: number;
  showNode: boolean;
};

export type parsedDataType = {
  id: string;
  params: string;
  progress: number;
  valid: boolean;
};

export type SanitizedHTMLWrapperType = {
  className: string;
  content: string;
  onClick: () => void;
  suppressWarning?: boolean;
};

export type iconsType = {
  [key: string]: React.ElementType;
};

export type modalHeaderType = {
  children: ReactNode;
  description: string | null;
};

export type codeAreaModalPropsType = {
  setValue: (value: string) => void;
  value: string;
  nodeClass: APIClassType | undefined;
  setNodeClass: (Class: APIClassType, code?: string) => void | undefined;
  children: ReactNode;
  dynamic?: boolean;
  readonly?: boolean;
};

export type chatMessagePropsType = {
  chat: ChatMessageType;
  lockChat: boolean;
  lastMessage: boolean;
};

export type formModalPropsType = {
  open: boolean;
  setOpen: Function;
  flow: FlowType;
};

export type genericModalPropsType = {
  field_name?: string;
  setValue: (value: string) => void;
  value: string;
  buttonText: string;
  modalTitle: string;
  type: number;
  nodeClass?: APIClassType;
  setNodeClass?: (Class: APIClassType, code?: string) => void;
  children: ReactNode;
  id?: string;
  readonly?: boolean;
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

type tabsArrayType = {
  code: string;
  image: string;
  language: string;
  mode: string;
  name: string;
  description?: string;
};

type getValueNodeType = {
  id: string;
  node: NodeType;
  type: string;
  value: null;
};

type codeTabsFuncTempType = {
  [key: string]: string | boolean;
};

export type codeTabsPropsType = {
  flow?: FlowType;
  tabs: Array<tabsArrayType>;
  activeTab: string;
  setActiveTab: (value: string) => void;
  isMessage?: boolean;
  tweaks?: {
    tweak?: { current: tweakType };
    tweaksList?: { current: Array<string> };
    buildContent?: (value: string) => ReactNode;
    getValue?: (
      value: string,
      node: NodeType,
      template: TemplateVariableType
    ) => string;
    buildTweakObject?: (
      tw: string,
      changes: string | string[] | boolean | number | Object[] | Object,
      template: TemplateVariableType
    ) => string | void;
  };
};

export type crashComponentPropsType = {
  error: {
    message: string;
    stack: string;
  };
  resetErrorBoundary: (args) => void;
};

export type validationStatusType = {
  id: string;
  params: string;
  progress: number;
  valid: boolean;
  duration: string;
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
};

export type dropdownButtonPropsType = {
  firstButtonName: string;
  onFirstBtnClick: () => void;
  options: Array<{ name: string; onBtnClick: () => void }>;
};

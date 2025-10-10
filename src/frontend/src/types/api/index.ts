import type {
  UseMutationOptions,
  UseMutationResult,
  UseQueryOptions,
  UseQueryResult,
} from "@tanstack/react-query";
import type { ChatInputType, ChatOutputType } from "../chat";
import type { FlowType } from "../flow";
//kind and class are just representative names to represent the actual structure of the object received by the API
export type APIDataType = { [key: string]: APIKindType };
export type APIObjectType = { [key: string]: APIKindType };
export type APIKindType = { [key: string]: APIClassType };
export type APITemplateType = {
  [key: string]: InputFieldType;
};

export type APICodeValidateType = {
  imports: { errors: Array<string> };
  function: { errors: Array<string> };
};

export type CustomFieldsType = {
  [key: string]: Array<string>;
};

export type CustomComponentRequest = {
  data: APIClassType;
  type: string;
};

export type APIClassType = {
  base_classes?: Array<string>;
  description: string;
  template: APITemplateType;
  display_name: string;
  icon?: string;
  edited?: boolean;
  is_input?: boolean;
  is_output?: boolean;
  conditional_paths?: Array<string>;
  input_types?: Array<string>;
  output_types?: Array<string>;
  custom_fields?: CustomFieldsType;
  beta?: boolean;
  legacy?: boolean;
  replacement?: string[];
  documentation: string;
  error?: string;
  official?: boolean;
  outputs?: Array<OutputFieldType>;
  frozen?: boolean;
  lf_version?: string;
  flow?: FlowType;
  field_order?: string[];
  tool_mode?: boolean;
  type?: string;
  last_updated?: string;
  [key: string]:
    | Array<string>
    | string
    | APITemplateType
    | boolean
    | FlowType
    | CustomFieldsType
    | boolean
    | undefined
    | Array<{ types: Array<string>; selected?: string }>;
};

export type InputFieldType = {
  type: string;
  required: boolean;
  placeholder?: string;
  list: boolean;
  show: boolean;
  readonly: boolean;
  password?: boolean;
  multiline?: boolean;
  value?: any;
  dynamic?: boolean;
  proxy?: { id: string; field: string };
  input_types?: Array<string>;
  display_name?: string;
  name?: string;
  real_time_refresh?: boolean;
  refresh_button?: boolean;
  refresh_button_text?: string;
  combobox?: boolean;
  info?: string;
  options?: string[];
  active_tab?: number;
  [key: string]: any;
  icon?: string;
  text?: string;
  temp_file?: boolean;
  separator?: string;
};

export type OutputFieldProxyType = {
  id: string;
  name: string;
  nodeDisplayName: string;
};

export type OutputFieldType = {
  types: Array<string>;
  selected?: string;
  name: string;
  group_outputs?: boolean;
  method?: string;
  display_name: string;
  hidden?: boolean;
  proxy?: OutputFieldProxyType;
  allows_loop?: boolean;
  options?: { [key: string]: any };
};
export type errorsTypeAPI = {
  function: { errors: Array<string> };
  imports: { errors: Array<string> };
};
export type PromptTypeAPI = {
  input_variables: Array<string>;
  frontend_node: APIClassType;
};

export type BuildStatusTypeAPI = {
  built: boolean;
};

export type InitTypeAPI = {
  flowId: string;
};

export type UploadFileTypeAPI = {
  file_path: string;
  flowId: string;
};

export type ProfilePicturesTypeAPI = {
  files: string[];
};

export type LoginType = {
  grant_type?: string;
  username: string;
  password: string;
  scrope?: string;
  client_id?: string;
  client_secret?: string;
};

export type LoginAuthType = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
};

export type changeUser = {
  username?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  password?: string;
  profile_image?: string;
  optins?: {
    github_starred?: boolean;
    discord_clicked?: boolean;
    dialog_dismissed?: boolean;
    mcp_dialog_dismissed?: boolean;
  };
};

export type resetPasswordType = {
  password?: string;
  profile_image?: string;
};

export type Users = {
  id: string;
  username: string;
  is_active: boolean;
  is_superuser: boolean;
  profile_image: string;
  create_at: Date;
  updated_at: Date;
  optins?: {
    github_starred?: boolean;
    discord_clicked?: boolean;
    dialog_dismissed?: boolean;
    mcp_dialog_dismissed?: boolean;
  };
};

export type Component = {
  name: string;
  description: string;
  data: Object;
  tags: [string];
};

export type VerticesOrderTypeAPI = {
  ids: Array<string>;
  vertices_to_run: Array<string>;
  run_id: string;
};

export type VertexBuildTypeAPI = {
  id: string;
  inactivated_vertices: Array<string> | null;
  next_vertices_ids: Array<string>;
  top_level_vertices: Array<string>;
  run_id?: string;
  valid: boolean;
  data: VertexDataTypeAPI;
  timestamp: string;
  params: any;
  messages: ChatOutputType[] | ChatInputType[];
  artifacts: any | ChatOutputType | ChatInputType;
};

export type ErrorLogType = {
  errorMessage: string;
  stackTrace: string;
};

export type OutputLogType = {
  message: any | ErrorLogType;
  type: string;
};
export type LogsLogType = {
  name: string;
  message: any | ErrorLogType;
  type: string;
};

// data is the object received by the API
// it has results, artifacts, timedelta, duration
export type VertexDataTypeAPI = {
  results: { [key: string]: string };
  outputs: { [key: string]: OutputLogType };
  logs: { [key: string]: LogsLogType };
  messages: ChatOutputType[] | ChatInputType[];
  inactive?: boolean;
  timedelta?: number;
  duration?: string;
  artifacts?: any | ChatOutputType | ChatInputType;
  message?: ChatOutputType | ChatInputType;
};

export type CodeErrorDataTypeAPI = {
  error: string | undefined;
  traceback: string | undefined;
};

// the error above is inside this error.response.data.detail.error
// which comes from a request to the API
// to type the error we need to know the structure of the object

// error that has a response, that has a data, that has a detail, that has an error
export type ResponseErrorTypeAPI = {
  response: { data: { detail: CodeErrorDataTypeAPI } };
};
export type ResponseErrorDetailAPI = {
  response: { data: { detail: string } };
};
export type useQueryFunctionType<
  T = undefined,
  R = any,
  O = {},
> = T extends undefined
  ? (
      options?: Omit<UseQueryOptions, "queryFn" | "queryKey"> & O,
    ) => UseQueryResult<R>
  : (
      params: T,
      options?: Omit<UseQueryOptions, "queryFn" | "queryKey"> & O,
    ) => UseQueryResult<R>;

export type QueryFunctionType = (
  queryKey: UseQueryOptions["queryKey"],
  queryFn: UseQueryOptions["queryFn"],
  options?: Omit<UseQueryOptions, "queryKey" | "queryFn">,
) => UseQueryResult<any>;

export type MutationFunctionType = (
  mutationKey: UseMutationOptions["mutationKey"],
  mutationFn: UseMutationOptions<any, any, any>["mutationFn"],
  options?: Omit<UseMutationOptions<any, any>, "mutationFn" | "mutationKey">,
) => UseMutationResult<any, any, any, any>;

export type useMutationFunctionType<
  Params,
  Variables = any,
  Data = any,
  Error = any,
> = Params extends undefined
  ? (
      options?: Omit<
        UseMutationOptions<Data, Error>,
        "mutationFn" | "mutationKey"
      >,
    ) => UseMutationResult<Data, Error, Variables>
  : (
      params: Params,
      options?: Omit<
        UseMutationOptions<Data, Error>,
        "mutationFn" | "mutationKey"
      >,
    ) => UseMutationResult<Data, Error, Variables>;

export type FieldValidatorType =
  | "no_spaces"
  | "lowercase"
  | "uppercase"
  | "email"
  | "url"
  | "alphanumeric"
  | "numeric"
  | "alpha"
  | "phone"
  | "slug"
  | "username"
  | "password";

export type FieldParserType =
  | "mcp_name_case"
  | "snake_case"
  | "camel_case"
  | "pascal_case"
  | "kebab_case"
  | "lowercase"
  | "uppercase"
  | "no_blank"
  | "valid_csv"
  | "space_case"
  | "commands"
  | "sanitize_mcp_name";

export type TableOptionsTypeAPI = {
  block_add?: boolean;
  block_delete?: boolean;
  block_edit?: boolean;
  block_sort?: boolean;
  block_filter?: boolean;
  block_hide?: boolean | string[];
  block_select?: boolean;
  hide_options?: boolean;
  field_validators?: Array<
    FieldValidatorType | { [key: string]: FieldValidatorType }
  >;
  field_parsers?: Array<FieldParserType | { [key: string]: FieldParserType }>;
  description?: string;
};

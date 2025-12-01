// Prompt Library Types

export interface ApprovalWorkflowStage {
  name: string;
  role: string;
}

export interface ApprovalWorkflow {
  name: string;
  num_of_stages: number;
  stages: ApprovalWorkflowStage[];
}

export interface MessageChainItem {
  role: "system" | "user";
  content: string;
  order: number;
}

export interface VariableDefinition {
  name: string;
  description?: string;
  type?: string;
  required?: boolean;
  default_value?: any;
}

export interface LLMConfig {
  provider: string;
  model: string;
  temperature?: number;
  max_tokens?: number;
}

export interface StructuredOutputRef {
  schema_id: string;
  strict?: boolean;
}

export interface PromptTemplate {
  prompt_id: string;
  name: string;
  description?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  created_by: string;
  application_id?: string;
  usecase_id?: string;
  approval_workflow?: ApprovalWorkflow;
}

export interface PromptVersion {
  id: string;
  prompt_id: string;
  version: number;
  message_chain: MessageChainItem[];
  variables: VariableDefinition[];
  config?: LLMConfig;
  structured_output?: StructuredOutputRef;
  change_description?: string;
  created_at: string;
  created_by: string;
  status: "DRAFT" | "PENDING_APPROVAL" | "PUBLISHED" | "REJECTED";
  updated_at: string;
  latest_feedback?: string;
  is_latest?: boolean;
}

export interface CreatePromptRequest {
  name: string;
  description?: string;
  tags?: string[];
  application_id?: string;
  usecase_id?: string;
  approval_workflow?: ApprovalWorkflow;
  message_chain?: MessageChainItem[];
}

export interface CreateVersionRequest {
  message_chain: MessageChainItem[];
  variables: VariableDefinition[];
  config?: LLMConfig;
  structured_output?: StructuredOutputRef;
  change_description: string;
}

export interface UpdateVersionRequest {
  message_chain: MessageChainItem[];
  variables: VariableDefinition[];
  config?: LLMConfig;
  structured_output?: StructuredOutputRef;
  change_description: string;
}

export interface ApiResponse<T> {
  data: T;
  message: string;
  error?: string;
}

export interface PromptsListResponse {
  prompts: PromptTemplate[];
  total: number;
  skip: number;
  limit: number;
}

export interface VersionsListResponse {
  versions: PromptVersion[];
  total: number;
  prompt_id: string;
}

export type ModelInfo = {
  name: string;
  display_name: string;
};

export type ProviderInfo = {
  name: string;
  configured: boolean;
  default_model: string | null;
  models: ModelInfo[];
};

export type AssistantConfigResponse = {
  configured: boolean;
  configured_providers: string[];
  providers: ProviderInfo[];
  default_provider: string | null;
  default_model: string | null;
};

export type AssistantMessageType =
  | "input"
  | "output"
  | "error"
  | "system"
  | "validated"
  | "validation_error"
  | "progress";

// All possible step types for progress events
export type ProgressStep =
  | "generating"           // LLM is generating response
  | "generation_complete"  // LLM finished generating
  | "extracting_code"      // Extracting Python code from response
  | "validating"           // Validating component code
  | "validated"            // Validation succeeded
  | "validation_failed"    // Validation failed
  | "retrying";            // About to retry with error context

export type ProgressMetadata = {
  step: ProgressStep;
  icon: string;
  color: string;
  spin?: boolean;
  attempt?: number;
  maxAttempts?: number;
  error?: string;
  componentName?: string;
  componentCode?: string;
};

export type AssistantMessageMetadata = {
  className?: string;
  validated?: boolean;
  validationAttempts?: number;
  componentCode?: string;
  progress?: ProgressMetadata;
};

export type AssistantMessage = {
  id: string;
  type: AssistantMessageType;
  content: string;
  timestamp: Date;
  metadata?: AssistantMessageMetadata;
};

export type SubmitResult = {
  content: string;
  validated?: boolean;
  className?: string;
  validationError?: string;
  validationAttempts?: number;
  componentCode?: string;
};

export type ProgressState = {
  step: ProgressStep;
  attempt: number;
  maxAttempts: number;
  message?: string;        // Human-readable status message
  error?: string;          // Error message (for validation_failed/retrying)
  componentName?: string;  // Component class name (for validation_failed)
  componentCode?: string;  // Component code (for validation_failed)
};

export type ProgressInfo = ProgressState | null;

export type ModelOption = {
  value: string;
  label: string;
  provider: string;
};

export type AssistantTerminalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (
    input: string,
    provider?: string,
    modelName?: string,
    onProgress?: (progress: ProgressState) => void,
  ) => Promise<SubmitResult>;
  onAddToCanvas: (code: string) => Promise<void>;
  isLoading?: boolean;
  maxRetries: number;
  onMaxRetriesChange: (value: number) => void;
  isConfigured?: boolean;
  isConfigLoading?: boolean;
  onConfigureClick?: () => void;
  configData?: AssistantConfigResponse;
};

export type AssistantPromptResponse = {
  result?: string;
  text?: string;
  logs?: string;
  success?: boolean;
  exception_message?: string;
  validated?: boolean;
  class_name?: string;
  validation_error?: string;
  validation_attempts?: number;
  component_code?: string;
};

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

export type AssistantMessageType = "input" | "output" | "error" | "system" | "validated" | "validation_error";

export type AssistantMessageMetadata = {
  className?: string;
  validated?: boolean;
  validationAttempts?: number;
  componentCode?: string;
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
  step: "generating" | "validating";
  attempt: number;
  maxAttempts: number;
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
  onSaveToSidebar: (code: string, className: string) => Promise<void>;
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

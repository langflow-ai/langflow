export type TerminalMessage = {
  id: string;
  type: "input" | "output" | "error" | "system" | "validated" | "validation_error";
  content: string;
  timestamp: Date;
  metadata?: {
    className?: string;
    validated?: boolean;
    validationAttempts?: number;
    componentCode?: string;
  };
};

export type SubmitResult = {
  content: string;
  validated?: boolean;
  className?: string;
  validationError?: string;
  validationAttempts?: number;
  componentCode?: string;
};

export type ForgeTerminalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (input: string) => Promise<SubmitResult>;
  onAddToCanvas: (code: string) => Promise<void>;
  onSaveToSidebar: (code: string, className: string) => Promise<void>;
  isLoading?: boolean;
  maxRetries: number;
  onMaxRetriesChange: (value: number) => void;
};

export type ForgePromptResponse = {
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

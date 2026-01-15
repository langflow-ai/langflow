import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { nanoid } from "nanoid";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/utils/utils";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";
import { useAssistantStore, type AssistantMessageData } from "@/stores/assistantStore";
import type { SubmitResult, AssistantMessage, AssistantTerminalProps, AssistantConfigResponse } from "./types";

const TERMINAL_MIN_HEIGHT = 200;
const TERMINAL_MAX_HEIGHT = 600;
const TERMINAL_DEFAULT_HEIGHT = 300;
const TERMINAL_CONFIG_HEIGHT = 280;
const RESIZE_HANDLE_HEIGHT = 8;
const HISTORY_STORAGE_KEY = "assistant-terminal-history";
const MAX_HISTORY_SIZE = 50;
const TEXTAREA_MAX_HEIGHT = 150;
const SCROLL_BOTTOM_THRESHOLD = 10;

const getHistory = (): string[] => {
  try {
    const stored = sessionStorage.getItem(HISTORY_STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
};

const saveToHistory = (input: string) => {
  const history = getHistory();
  if (history[history.length - 1] !== input) {
    const newHistory = [...history, input].slice(-MAX_HISTORY_SIZE);
    sessionStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(newHistory));
  }
};

const MIN_RETRIES = 0;
const MAX_RETRIES_LIMIT = 5;

const RATE_LIMIT_PATTERNS = ["rate limit", "rate_limit", "429", "too many requests"];
const PROVIDER_ERROR_PATTERNS = ["api key", "api_key", "authentication", "unauthorized", "model provider", "not configured"];
const QUOTA_ERROR_PATTERNS = ["quota", "billing", "insufficient"];

type ErrorCategory = "rate_limit" | "quota" | "provider" | "generic";

const categorizeError = (errorMessage: string, statusCode?: number): ErrorCategory => {
  const errorLower = errorMessage.toLowerCase();

  if (RATE_LIMIT_PATTERNS.some(pattern => errorLower.includes(pattern))) {
    return "rate_limit";
  }
  if (QUOTA_ERROR_PATTERNS.some(pattern => errorLower.includes(pattern))) {
    return "quota";
  }
  if (PROVIDER_ERROR_PATTERNS.some(pattern => errorLower.includes(pattern))) {
    return "provider";
  }
  if (statusCode === 400 && errorLower.includes("required")) {
    return "provider";
  }
  return "generic";
};

type CommandResult = {
  handled: boolean;
  message?: string;
  type?: AssistantMessage["type"];
  action?: "clear";
};

type CommandContext = {
  maxRetries: number;
  onMaxRetriesChange: (value: number) => void;
};

const HELP_TEXT = `Available commands:
  MAX_RETRIES=<0-5>  Set component validation retry attempts (only applies when generating components)
  HELP or ?          Show this help message
  CLEAR              Clear terminal history

Ask questions about Langflow or describe a component to generate.`;

const parseCommand = (input: string, context: CommandContext): CommandResult => {
  const trimmed = input.trim();
  const upper = trimmed.toUpperCase();

  if (upper === "HELP" || upper === "?") {
    return { handled: true, message: HELP_TEXT, type: "system" };
  }

  if (upper === "CLEAR") {
    return { handled: true, action: "clear" };
  }

  const maxRetriesMatch = trimmed.match(/^MAX_RETRIES\s*=\s*(\d+)$/i);
  if (maxRetriesMatch) {
    const value = parseInt(maxRetriesMatch[1], 10);
    if (value < MIN_RETRIES || value > MAX_RETRIES_LIMIT) {
      return {
        handled: true,
        message: `Invalid value. MAX_RETRIES must be between ${MIN_RETRIES} and ${MAX_RETRIES_LIMIT}.`,
        type: "error",
      };
    }
    context.onMaxRetriesChange(value);
    return {
      handled: true,
      message: `MAX_RETRIES set to ${value}`,
      type: "system",
    };
  }

  return { handled: false };
};

type ModelOption = {
  value: string;
  label: string;
  provider: string;
};

const TerminalHeader = ({
  onClose,
  onClear,
  configData,
  selectedModel,
  onModelChange,
}: {
  onClose: () => void;
  onClear: () => void;
  configData?: AssistantConfigResponse;
  selectedModel: string | null;
  onModelChange: (value: string) => void;
}) => {
  // Build model options from config data
  const modelOptions = useMemo((): ModelOption[] => {
    if (!configData?.providers) return [];

    const options: ModelOption[] = [];
    for (const provider of configData.providers) {
      if (provider.configured) {
        for (const model of provider.models) {
          options.push({
            value: `${provider.name}:${model.name}`,
            label: model.display_name,
            provider: provider.name,
          });
        }
      }
    }
    return options;
  }, [configData]);

  const selectedOption = modelOptions.find(opt => opt.value === selectedModel);
  const hasMultipleProviders = new Set(modelOptions.map(m => m.provider)).size > 1;

  return (
    <div className="flex items-center justify-between border-b border-border bg-background px-4 py-2">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent
            name="Sparkles"
            className="h-4 w-4 text-accent-emerald-foreground"
          />
          <span className="font-mono text-sm font-medium text-foreground">
            Assistant
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Select value={selectedModel ?? ""} onValueChange={onModelChange} disabled={modelOptions.length === 0}>
          <SelectTrigger className="h-7 w-auto min-w-[140px] border-border bg-muted text-xs text-foreground hover:bg-accent focus:ring-0 focus:ring-offset-0 disabled:opacity-50">
            <div className="flex items-center gap-1.5">
              <ForwardedIconComponent name="Bot" className="h-3 w-3 text-muted-foreground" />
              <SelectValue placeholder="Select model">
                {selectedOption ? (
                  <span>
                    {hasMultipleProviders && <span className="text-muted-foreground">{selectedOption.provider} / </span>}
                    {selectedOption.label}
                  </span>
                ) : modelOptions.length === 0 ? (
                  "No models"
                ) : (
                  "Select model"
                )}
              </SelectValue>
            </div>
          </SelectTrigger>
          <SelectContent className="border-border bg-muted max-h-[300px]">
            {configData?.providers && configData.providers.length > 0 ? (
              configData.providers.map((provider) => (
                <SelectGroup key={provider.name}>
                  <SelectLabel className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                    {provider.name}
                  </SelectLabel>
                  {provider.models.map((model) => (
                    <SelectItem
                      key={`${provider.name}:${model.name}`}
                      value={`${provider.name}:${model.name}`}
                      className="text-xs text-foreground cursor-pointer"
                    >
                      {model.display_name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              ))
            ) : (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">
                Configure a model provider
              </div>
            )}
          </SelectContent>
        </Select>
        <Button
          variant="ghost"
          size="iconSm"
          onClick={onClear}
          className="text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ForwardedIconComponent name="Trash2" className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="iconSm"
          onClick={onClose}
          className="text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};

const downloadComponentFile = (code: string, className: string) => {
  const blob = new Blob([code], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${className}.py`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const ComponentResultLine = ({
  className,
  code,
  onAddToCanvas,
  onSaveToSidebar,
}: {
  className: string;
  code: string;
  onAddToCanvas: (code: string) => Promise<void>;
  onSaveToSidebar: (code: string, className: string) => Promise<void>;
}) => {
  const [isAddingToCanvas, setIsAddingToCanvas] = useState(false);
  const [isSavingToSidebar, setIsSavingToSidebar] = useState(false);
  const [isCodeExpanded, setIsCodeExpanded] = useState(false);

  const handleDownload = () => {
    downloadComponentFile(code, className);
  };

  const handleAddToCanvas = async () => {
    setIsAddingToCanvas(true);
    try {
      await onAddToCanvas(code);
    } finally {
      setIsAddingToCanvas(false);
    }
  };

  const handleSaveToSidebar = async () => {
    setIsSavingToSidebar(true);
    try {
      await onSaveToSidebar(code, className);
    } finally {
      setIsSavingToSidebar(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 py-2">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setIsCodeExpanded(!isCodeExpanded)}
          className="flex items-center gap-1.5 hover:text-foreground transition-colors"
        >
          <ForwardedIconComponent
            name="ChevronRight"
            className={cn(
              "h-4 w-4 text-muted-foreground transition-transform",
              isCodeExpanded && "rotate-90"
            )}
          />
          <span className="font-mono text-sm text-accent-emerald-foreground">
            {className}.py
          </span>
        </button>

        <div className="flex items-center gap-0.5">
          <Button
            variant="ghost"
            size="iconSm"
            onClick={handleDownload}
            className="text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Download"
          >
            <ForwardedIconComponent name="Download" className="h-3.5 w-3.5" />
          </Button>

          <Button
            variant="ghost"
            size="iconSm"
            onClick={handleSaveToSidebar}
            disabled={isSavingToSidebar}
            className="text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
            title="Save to Sidebar"
          >
            <ForwardedIconComponent
              name={isSavingToSidebar ? "Loader2" : "SaveAll"}
              className={cn("h-3.5 w-3.5", isSavingToSidebar && "animate-spin")}
            />
          </Button>

          <Button
            variant="ghost"
            size="iconSm"
            onClick={handleAddToCanvas}
            disabled={isAddingToCanvas}
            className="ml-1 bg-accent-emerald-foreground/15 text-accent-emerald-foreground hover:bg-accent-emerald-foreground/25 disabled:opacity-50"
            title="Add to Canvas"
          >
            <ForwardedIconComponent
              name={isAddingToCanvas ? "Loader2" : "Plus"}
              className={cn("h-3.5 w-3.5", isAddingToCanvas && "animate-spin")}
            />
          </Button>
        </div>
      </div>

      {isCodeExpanded && (
        <div className="mt-1">
          <SimplifiedCodeTabComponent language="python" code={code} />
        </div>
      )}
    </div>
  );
};

const MessageLine = ({
  message,
  onAddToCanvas,
  onSaveToSidebar,
}: {
  message: AssistantMessage;
  onAddToCanvas: (code: string) => Promise<void>;
  onSaveToSidebar: (code: string, className: string) => Promise<void>;
}) => {
  const getMessageStyle = () => {
    switch (message.type) {
      case "input":
        return "text-accent-emerald-foreground";
      case "output":
        return "text-foreground";
      case "error":
        return "text-destructive";
      case "system":
        return "text-muted-foreground italic";
      case "validated":
        return "text-accent-emerald-foreground";
      case "validation_error":
        return "text-accent-amber-foreground";
      default:
        return "text-foreground";
    }
  };

  const getPrefix = () => {
    switch (message.type) {
      case "input":
        return "> ";
      case "error":
        return "! ";
      case "system":
        return "# ";
      default:
        return "";
    }
  };

  if (
    message.type === "validated" &&
    message.metadata?.componentCode &&
    message.metadata?.className
  ) {
    return (
      <ComponentResultLine
        className={message.metadata.className}
        code={message.metadata.componentCode}
        onAddToCanvas={onAddToCanvas}
        onSaveToSidebar={onSaveToSidebar}
      />
    );
  }

  const useMarkdown = message.type === "output";

  return (
    <div className="flex flex-col gap-1">
      {message.type === "validation_error" && (
        <div className="flex items-center gap-1.5 py-1">
          <ForwardedIconComponent
            name="XCircle"
            className="h-4 w-4 text-destructive"
          />
          <span className="text-sm text-destructive">Validation failed</span>
        </div>
      )}
      {useMarkdown ? (
        <div className="font-mono text-sm text-foreground whitespace-pre-wrap">
          <span className="select-none text-muted-foreground">← </span>
          {message.content}
        </div>
      ) : (
        <div
          className={cn("font-mono text-sm whitespace-pre-wrap", getMessageStyle())}
        >
          <span className="select-none opacity-70">{getPrefix()}</span>
          {message.content}
        </div>
      )}
    </div>
  );
};

type ProgressInfo = {
  step: "generating" | "validating";
  attempt: number;
  maxAttempts: number;
} | null;

const LoadingIndicator = ({
  progress,
}: {
  progress?: ProgressInfo;
}) => {
  const getStatusText = () => {
    if (!progress) return "Generating...";
    const { step, attempt, maxAttempts } = progress;
    if (step === "generating") {
      return "Generating...";
    }
    return `Validating... attempt ${attempt}/${maxAttempts}`;
  };

  return (
    <div className="flex items-center gap-2 py-2 font-mono text-sm text-muted-foreground">
      <ForwardedIconComponent
        name="Loader2"
        className="h-3.5 w-3.5 animate-spin"
      />
      <span>{getStatusText()}</span>
    </div>
  );
};

const ConfigLoading = () => (
  <div className="flex flex-col items-center justify-center h-full py-4">
    <div className="flex flex-col items-center gap-3">
      <ForwardedIconComponent
        name="Loader2"
        className="h-8 w-8 text-muted-foreground animate-spin"
      />
      <span className="text-sm text-muted-foreground">Checking configuration...</span>
    </div>
  </div>
);

const ConfigurationRequired = ({
  onConfigureClick,
}: {
  onConfigureClick?: () => void;
}) => (
  <div className="flex flex-col items-center justify-center h-full">
    <div className="flex flex-col items-center gap-2 text-center">
      <ForwardedIconComponent
        name="Bot"
        className="h-6 w-6 text-accent-amber-foreground"
      />
      <p className="text-sm text-foreground">
        Configure a model provider to use the Assistant
      </p>
      {onConfigureClick && (
        <Button
          size="sm"
          onClick={onConfigureClick}
          className="bg-accent-emerald-foreground hover:bg-accent-emerald-hover text-background gap-1.5 h-7 text-xs"
        >
          <ForwardedIconComponent name="Settings" className="h-3 w-3" />
          Model Providers
        </Button>
      )}
    </div>
  </div>
);

const AssistantTerminal = ({
  isOpen,
  onClose,
  onSubmit,
  onAddToCanvas,
  onSaveToSidebar,
  isLoading = false,
  maxRetries,
  onMaxRetriesChange,
  isConfigured,
  isConfigLoading,
  onConfigureClick,
  configData,
}: AssistantTerminalProps) => {
  // Use messages from Zustand store for persistence across screen switches
  const messages = useAssistantStore((state) => state.messages);
  const setMessages = useAssistantStore((state) => state.setMessages);
  const storeAddMessage = useAssistantStore((state) => state.addMessage);

  const getWelcomeMessages = useCallback(
    (): AssistantMessageData[] => [
      {
        id: nanoid(),
        type: "system",
        content: "Welcome to Assistant. Ask about Langflow documentation or describe a custom component to generate. Type HELP for commands.",
        timestamp: new Date(),
      },
      {
        id: nanoid(),
        type: "system",
        content: `MAX_RETRIES=${maxRetries} (for component generation)`,
        timestamp: new Date(),
      },
    ],
    [maxRetries],
  );

  // Initialize messages with welcome messages if empty
  useEffect(() => {
    if (messages.length === 0) {
      setMessages(getWelcomeMessages());
    }
  }, [messages.length, setMessages, getWelcomeMessages]);
  const [inputValue, setInputValue] = useState("");
  const [height, setHeight] = useState(TERMINAL_DEFAULT_HEIGHT);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [progress, setProgress] = useState<ProgressInfo>(null);

  // Model selection from store (persisted in localStorage)
  const selectedModel = useAssistantStore((state) => state.selectedModel);
  const setSelectedModel = useAssistantStore((state) => state.setSelectedModel);

  // Initialize selected model from localStorage or use default from configData
  useEffect(() => {
    if (!configData?.providers?.length) return;

    // If no stored model or stored model is not available, use default
    const isStoredModelAvailable = selectedModel && configData.providers.some(
      (p) => p.models.some((m) => `${p.name}:${m.name}` === selectedModel)
    );

    if (!isStoredModelAvailable && configData.default_provider && configData.default_model) {
      setSelectedModel(`${configData.default_provider}:${configData.default_model}`);
    }
  }, [configData, selectedModel, setSelectedModel]);

  // Extract provider and model name from selected value
  const getProviderAndModel = useCallback(() => {
    if (!selectedModel) return { provider: undefined, modelName: undefined };
    const parts = selectedModel.split(":");
    return { provider: parts[0], modelName: parts[1] };
  }, [selectedModel]);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const prevIsOpenRef = useRef<boolean>(false);

  // Use store for scroll position persistence across screen changes
  const scrollPosition = useAssistantStore((state) => state.scrollPosition);
  const setScrollPosition = useAssistantStore((state) => state.setScrollPosition);

  const scrollToBottom = useCallback(() => {
    const container = messagesContainerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
      setScrollPosition(-1); // -1 means "at bottom"
    }
  }, [setScrollPosition]);

  // Track scroll position changes
  const handleScroll = useCallback(() => {
    const container = messagesContainerRef.current;
    if (container) {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < SCROLL_BOTTOM_THRESHOLD;
      setScrollPosition(isAtBottom ? -1 : scrollTop);
    }
  }, [setScrollPosition]);

  // Restore scroll position when terminal opens or messages are available
  useLayoutEffect(() => {
    const justOpened = isOpen && !prevIsOpenRef.current;
    prevIsOpenRef.current = isOpen;

    if (!isOpen || messages.length === 0) return;

    const container = messagesContainerRef.current;
    if (!container) return;

    const doRestore = () => {
      if (!messagesContainerRef.current) return;
      const target = scrollPosition === -1
        ? messagesContainerRef.current.scrollHeight
        : scrollPosition;
      messagesContainerRef.current.scrollTop = target;
    };

    // If terminal just opened, restore with multiple retries
    if (justOpened) {
      doRestore();
      requestAnimationFrame(doRestore);
      setTimeout(doRestore, 10);
      setTimeout(doRestore, 50);
      setTimeout(doRestore, 100);
    }
  }, [isOpen, messages.length, scrollPosition]);

  // Scroll to bottom when new messages arrive (only if was at bottom)
  useLayoutEffect(() => {
    if (scrollPosition === -1 && isOpen) {
      scrollToBottom();
    }
  }, [messages.length, isLoading, scrollPosition, scrollToBottom, isOpen]);

  // Focus textarea when opened
  useEffect(() => {
    if (isOpen) {
      textareaRef.current?.focus();
    }
  }, [isOpen]);

  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, TEXTAREA_MAX_HEIGHT)}px`;
    }
  }, []);

  useEffect(() => {
    adjustTextareaHeight();
  }, [inputValue, adjustTextareaHeight]);

  const addMessage = useCallback(
    (type: AssistantMessage["type"], content: string) => {
      const newMessage: AssistantMessageData = {
        id: nanoid(),
        type,
        content,
        timestamp: new Date(),
      };
      storeAddMessage(newMessage);
    },
    [storeAddMessage],
  );

  const addMessageWithMetadata = useCallback(
    (
      type: AssistantMessage["type"],
      content: string,
      metadata?: AssistantMessage["metadata"],
    ) => {
      const newMessage: AssistantMessageData = {
        id: nanoid(),
        type,
        content,
        timestamp: new Date(),
        metadata,
      };
      storeAddMessage(newMessage);
    },
    [storeAddMessage],
  );

  const handleClear = useCallback(() => {
    setMessages([
      {
        id: nanoid(),
        type: "system",
        content: "Terminal cleared. Type HELP for commands.",
        timestamp: new Date(),
      },
      {
        id: nanoid(),
        type: "system",
        content: `MAX_RETRIES=${maxRetries} (for component generation)`,
        timestamp: new Date(),
      },
    ]);
    setScrollPosition(-1);
  }, [maxRetries, setMessages, setScrollPosition]);

  const handleSubmit = useCallback(async () => {
    const trimmedInput = inputValue.trim();
    if (!trimmedInput || isLoading) return;

    saveToHistory(trimmedInput);
    setHistoryIndex(-1);
    addMessage("input", trimmedInput);
    setInputValue("");

    const commandResult = parseCommand(trimmedInput, {
      maxRetries,
      onMaxRetriesChange,
    });

    if (commandResult.handled) {
      if (commandResult.action === "clear") {
        handleClear();
      } else if (commandResult.message) {
        addMessage(commandResult.type || "system", commandResult.message);
      }
      return;
    }

    try {
      const { provider, modelName } = getProviderAndModel();

      const handleProgress = (p: { step: "generating" | "validating"; attempt: number; maxAttempts: number }) => {
        setProgress(p);
      };

      const response: SubmitResult = await onSubmit(trimmedInput, provider, modelName, handleProgress);
      setProgress(null);

      if (response.validated === true) {
        addMessageWithMetadata("validated", response.content, {
          validated: true,
          className: response.className,
          validationAttempts: response.validationAttempts,
          componentCode: response.componentCode,
        });
      } else if (response.validated === false) {
        const codePreview = response.componentCode
          ? response.componentCode.split("\n").slice(0, 5).join("\n") + "..."
          : "No code extracted";

        addMessageWithMetadata("validation_error", `Component generation failed after ${response.validationAttempts || 1} attempt(s)`, {
          validated: false,
          validationAttempts: response.validationAttempts,
          componentCode: response.componentCode,
        });
        if (response.validationError) {
          addMessage("error", `Validation error: ${response.validationError}`);
        }
        addMessage("system", `Code preview:\n${codePreview}`);
      } else {
        addMessage("output", response.content);
      }
    } catch (error: unknown) {
      setProgress(null);
      let errorMessage = "An error occurred";

      const axiosError = error as { response?: { data?: { detail?: string }; status?: number } };
      if (axiosError?.response?.data?.detail) {
        errorMessage = axiosError.response.data.detail;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }

      const errorCategory = categorizeError(errorMessage, axiosError?.response?.status);

      switch (errorCategory) {
        case "rate_limit":
          addMessage("error", "Rate limit exceeded. Please wait a moment and try again.");
          break;
        case "quota":
          addMessage("error", "API quota exceeded. Please check your account billing.");
          break;
        case "provider":
          addMessage("error", "Model provider configuration issue.");
          addMessage("system", "Go to Settings → Model Providers to configure.");
          break;
        default:
          addMessage("error", errorMessage);
      }
    }
  }, [inputValue, isLoading, onSubmit, addMessage, addMessageWithMetadata, maxRetries, onMaxRetriesChange, handleClear, getProviderAndModel]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
        return;
      }

      const history = getHistory();
      if (history.length === 0) return;

      const textarea = e.currentTarget;
      const isAtStart = textarea.selectionStart === 0 && textarea.selectionEnd === 0;
      const isAtEnd = textarea.selectionStart === textarea.value.length;

      if (e.key === "ArrowUp" && isAtStart) {
        e.preventDefault();
        const newIndex = historyIndex === -1
          ? history.length - 1
          : Math.max(0, historyIndex - 1);
        setHistoryIndex(newIndex);
        setInputValue(history[newIndex]);
      } else if (e.key === "ArrowDown" && isAtEnd) {
        e.preventDefault();
        if (historyIndex === -1) return;
        const newIndex = historyIndex + 1;
        if (newIndex >= history.length) {
          setHistoryIndex(-1);
          setInputValue("");
        } else {
          setHistoryIndex(newIndex);
          setInputValue(history[newIndex]);
        }
      }
    },
    [handleSubmit, historyIndex],
  );

  const handleResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startY = e.clientY;
      const startHeight = height;

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const deltaY = startY - moveEvent.clientY;
        const newHeight = Math.min(
          Math.max(startHeight + deltaY, TERMINAL_MIN_HEIGHT),
          TERMINAL_MAX_HEIGHT,
        );
        setHeight(newHeight);
      };

      const handleMouseUp = () => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    },
    [height],
  );

  if (!isOpen) return null;

  const terminalHeight = isConfigured === false ? TERMINAL_CONFIG_HEIGHT : height;

  return (
    <div
      ref={terminalRef}
      className="absolute bottom-0 left-0 right-0 z-40 flex flex-col overflow-hidden rounded-t-lg border border-b-0 border-border bg-background shadow-2xl"
      style={{ height: terminalHeight }}
    >
      {isConfigured !== false && (
        <div
          role="separator"
          aria-orientation="horizontal"
          aria-valuenow={height}
          aria-valuemin={TERMINAL_MIN_HEIGHT}
          aria-valuemax={TERMINAL_MAX_HEIGHT}
          tabIndex={0}
          className={cn(
            "absolute -top-1 left-0 right-0 cursor-ns-resize",
            "flex items-center justify-center",
            "hover:bg-accent transition-colors",
          )}
          style={{ height: RESIZE_HANDLE_HEIGHT }}
          onMouseDown={handleResizeStart}
        >
          <div className="h-1 w-12 rounded-full bg-muted-foreground" />
        </div>
      )}

      <TerminalHeader
        onClose={onClose}
        onClear={handleClear}
        configData={configData}
        selectedModel={selectedModel}
        onModelChange={setSelectedModel}
      />

      {isConfigLoading ? (
        <ConfigLoading />
      ) : isConfigured === false ? (
        <ConfigurationRequired onConfigureClick={onConfigureClick} />
      ) : (
        <>
          <div
            ref={messagesContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto px-4 py-3"
            style={{ overflowAnchor: "none" }}
          >
            <div className="flex flex-col gap-1">
              {messages.map((message) => (
                <MessageLine
                  key={message.id}
                  message={message}
                  onAddToCanvas={onAddToCanvas}
                  onSaveToSidebar={onSaveToSidebar}
                />
              ))}
              {isLoading && <LoadingIndicator progress={progress} />}
            </div>
          </div>

          <div className="border-t border-border bg-background/80 px-4 py-3">
            <div className="flex items-start gap-2">
              <span className="font-mono text-sm text-accent-emerald-foreground select-none pt-0.5">
                &gt;
              </span>
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                placeholder="Ask a question or describe a component..."
                rows={1}
                className={cn(
                  "flex-1 bg-transparent font-mono text-sm text-foreground resize-none",
                  "placeholder:text-muted-foreground focus:outline-none",
                  "disabled:cursor-not-allowed disabled:opacity-50",
                )}
              />
              <Button
                variant="ghost"
                size="iconSm"
                onClick={handleSubmit}
                disabled={!inputValue.trim() || isLoading}
                className="text-accent-emerald-foreground hover:bg-muted hover:text-accent-emerald-hover disabled:opacity-30"
              >
                <ForwardedIconComponent
                  name={isLoading ? "Loader2" : "Send"}
                  className={cn("h-4 w-4", isLoading && "animate-spin")}
                />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default AssistantTerminal;

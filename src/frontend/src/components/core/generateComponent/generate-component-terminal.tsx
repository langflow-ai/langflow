import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { nanoid } from "nanoid";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import CodeAreaModal from "@/modals/codeAreaModal";
import { cn } from "@/utils/utils";
import type { SubmitResult, TerminalMessage, GenerateComponentTerminalProps } from "./types";

const TERMINAL_MIN_HEIGHT = 200;
const TERMINAL_MAX_HEIGHT = 600;
const TERMINAL_DEFAULT_HEIGHT = 300;
const RESIZE_HANDLE_HEIGHT = 8;
const HISTORY_STORAGE_KEY = "generate-component-terminal-history";
const MAX_HISTORY_SIZE = 50;
const TEXTAREA_MAX_HEIGHT = 150;

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

const MODEL_NAME = "Claude Sonnet 4.5";
const MIN_RETRIES = 0;
const MAX_RETRIES_LIMIT = 5;

type CommandResult = {
  handled: boolean;
  message?: string;
  type?: TerminalMessage["type"];
  action?: "clear";
};

type CommandContext = {
  maxRetries: number;
  onMaxRetriesChange: (value: number) => void;
};

const HELP_TEXT = `Available commands:
  MAX_RETRIES=<0-5>  Set validation retry attempts
  HELP or ?          Show this help message
  CLEAR              Clear terminal history

Type any other text to generate a component.`;

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

const TerminalHeader = ({
  onClose,
  onClear,
}: {
  onClose: () => void;
  onClear: () => void;
}) => (
  <div className="flex items-center justify-between border-b border-zinc-700 bg-zinc-900 px-4 py-2">
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <ForwardedIconComponent
          name="Terminal"
          className="h-4 w-4 text-emerald-400"
        />
        <span className="font-mono text-sm font-medium text-zinc-200">
          Generate component
        </span>
      </div>
      <span className="text-xs text-zinc-500">|</span>
      <span className="flex items-center gap-1.5 text-xs text-zinc-400">
        <ForwardedIconComponent name="Bot" className="h-3 w-3" />
        {MODEL_NAME}
      </span>
    </div>
    <div className="flex items-center gap-1">
      <Button
        variant="ghost"
        size="iconSm"
        onClick={onClear}
        className="text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
      >
        <ForwardedIconComponent name="Trash2" className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="iconSm"
        onClick={onClose}
        className="text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
      >
        <ForwardedIconComponent name="X" className="h-4 w-4" />
      </Button>
    </div>
  </div>
);

const ValidationBadge = ({
  validated,
  className,
}: {
  validated: boolean;
  className?: string;
}) => (
  <span
    className={cn(
      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
      validated
        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
        : "bg-red-500/20 text-red-400 border border-red-500/30",
    )}
  >
    <ForwardedIconComponent
      name={validated ? "CheckCircle" : "XCircle"}
      className="h-3 w-3"
    />
    {validated ? `Valid${className ? `: ${className}` : ""}` : "Invalid"}
  </span>
);

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
  validationAttempts,
  onAddToCanvas,
  onSaveToSidebar,
}: {
  className: string;
  code: string;
  validationAttempts?: number;
  onAddToCanvas: (code: string) => Promise<void>;
  onSaveToSidebar: (code: string, className: string) => Promise<void>;
}) => {
  const [isCodeModalOpen, setIsCodeModalOpen] = useState(false);
  const [isAddingToCanvas, setIsAddingToCanvas] = useState(false);
  const [isSavingToSidebar, setIsSavingToSidebar] = useState(false);

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
      <div className="flex items-center gap-2">
        <ValidationBadge validated={true} className={className} />
        {validationAttempts && validationAttempts > 1 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400 border border-amber-500/20">
            <ForwardedIconComponent name="RotateCw" className="h-3 w-3" />
            {validationAttempts} attempts
          </span>
        )}
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm text-emerald-400">
            {className}.py
          </span>

          <div className="flex items-center gap-0.5">
            <Button
              variant="ghost"
              size="iconSm"
              onClick={() => setIsCodeModalOpen(true)}
              className="text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
              title="View Code"
            >
              <ForwardedIconComponent name="Code" className="h-3.5 w-3.5" />
            </Button>

            <Button
              variant="ghost"
              size="iconSm"
              onClick={handleDownload}
              className="text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
              title="Download"
            >
              <ForwardedIconComponent name="Download" className="h-3.5 w-3.5" />
            </Button>

            <Button
              variant="ghost"
              size="iconSm"
              onClick={handleSaveToSidebar}
              disabled={isSavingToSidebar}
              className="text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 disabled:opacity-50"
              title="Save to Sidebar"
            >
              <ForwardedIconComponent
                name={isSavingToSidebar ? "Loader2" : "SaveAll"}
                className={cn("h-3.5 w-3.5", isSavingToSidebar && "animate-spin")}
              />
            </Button>
          </div>
        </div>

        <Button
          size="sm"
          onClick={handleAddToCanvas}
          disabled={isAddingToCanvas}
          className="bg-emerald-600 hover:bg-emerald-500 text-white gap-1.5 px-3 h-7 disabled:opacity-50"
        >
          <ForwardedIconComponent
            name={isAddingToCanvas ? "Loader2" : "Plus"}
            className={cn("h-3.5 w-3.5", isAddingToCanvas && "animate-spin")}
          />
          <span className="text-xs font-medium">Add to Canvas</span>
        </Button>
      </div>

      <CodeAreaModal
        value={code}
        setValue={() => {}}
        nodeClass={undefined}
        setNodeClass={() => {}}
        readonly={true}
        open={isCodeModalOpen}
        setOpen={setIsCodeModalOpen}
      >
        <span />
      </CodeAreaModal>
    </div>
  );
};

const MessageLine = ({
  message,
  onAddToCanvas,
  onSaveToSidebar,
}: {
  message: TerminalMessage;
  onAddToCanvas: (code: string) => Promise<void>;
  onSaveToSidebar: (code: string, className: string) => Promise<void>;
}) => {
  const getMessageStyle = () => {
    switch (message.type) {
      case "input":
        return "text-emerald-400";
      case "output":
        return "text-zinc-300";
      case "error":
        return "text-red-400";
      case "system":
        return "text-zinc-500 italic";
      case "validated":
        return "text-emerald-300";
      case "validation_error":
        return "text-amber-400";
      default:
        return "text-zinc-300";
    }
  };

  const getPrefix = () => {
    switch (message.type) {
      case "input":
        return "> ";
      case "output":
        return "";
      case "error":
        return "! ";
      case "system":
        return "# ";
      case "validated":
        return "";
      case "validation_error":
        return "";
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
        validationAttempts={message.metadata.validationAttempts}
        onAddToCanvas={onAddToCanvas}
        onSaveToSidebar={onSaveToSidebar}
      />
    );
  }

  const showValidationBadge =
    message.type === "validated" || message.type === "validation_error";

  return (
    <div className="flex flex-col gap-1">
      {showValidationBadge && (
        <div className="flex items-center gap-2 py-1">
          <ValidationBadge
            validated={message.type === "validated"}
            className={message.metadata?.className}
          />
          {message.metadata?.validationAttempts &&
            message.metadata.validationAttempts > 1 && (
              <span className="text-xs text-zinc-500">
                (after {message.metadata.validationAttempts} attempts)
              </span>
            )}
        </div>
      )}
      <div
        className={cn("font-mono text-sm whitespace-pre-wrap", getMessageStyle())}
      >
        <span className="select-none opacity-70">{getPrefix()}</span>
        {message.content}
      </div>
    </div>
  );
};

const LoadingIndicator = () => (
  <div className="flex flex-col gap-1.5 py-2">
    <div className="flex items-center gap-2 font-mono text-sm text-zinc-400">
      <ForwardedIconComponent
        name="Loader2"
        className="h-3.5 w-3.5 animate-spin text-emerald-400"
      />
      <span>Generating component...</span>
    </div>
    <div className="ml-5.5 flex items-center gap-2 font-mono text-xs text-zinc-500">
      <span>Code will be validated automatically.</span>
    </div>
  </div>
);

const GenerateComponentTerminal = ({
  isOpen,
  onClose,
  onSubmit,
  onAddToCanvas,
  onSaveToSidebar,
  isLoading = false,
  maxRetries,
  onMaxRetriesChange,
}: GenerateComponentTerminalProps) => {
  const getWelcomeMessages = useCallback(
    (): TerminalMessage[] => [
      {
        id: nanoid(),
        type: "system",
        content: "Welcome to Generate component. Type HELP for commands.",
        timestamp: new Date(),
      },
      {
        id: nanoid(),
        type: "system",
        content: `MAX_RETRIES=${maxRetries}`,
        timestamp: new Date(),
      },
    ],
    [maxRetries],
  );

  const [messages, setMessages] = useState<TerminalMessage[]>(getWelcomeMessages);
  const [inputValue, setInputValue] = useState("");
  const [height, setHeight] = useState(TERMINAL_DEFAULT_HEIGHT);
  const [historyIndex, setHistoryIndex] = useState(-1);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    const container = messagesContainerRef.current;
    if (container) {
      requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
      });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      textareaRef.current?.focus();
    }
  }, [isOpen, scrollToBottom]);

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
    (type: TerminalMessage["type"], content: string) => {
      const newMessage: TerminalMessage = {
        id: nanoid(),
        type,
        content,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, newMessage]);
    },
    [],
  );

  const addMessageWithMetadata = useCallback(
    (
      type: TerminalMessage["type"],
      content: string,
      metadata?: TerminalMessage["metadata"],
    ) => {
      const newMessage: TerminalMessage = {
        id: nanoid(),
        type,
        content,
        timestamp: new Date(),
        metadata,
      };
      setMessages((prev) => [...prev, newMessage]);
    },
    [],
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
        content: `MAX_RETRIES=${maxRetries}`,
        timestamp: new Date(),
      },
    ]);
  }, [maxRetries]);

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
      const response: SubmitResult = await onSubmit(trimmedInput);

      if (response.validated === true) {
        addMessageWithMetadata("validated", response.content, {
          validated: true,
          className: response.className,
          validationAttempts: response.validationAttempts,
          componentCode: response.componentCode,
        });
      } else if (response.validated === false) {
        addMessageWithMetadata("validation_error", response.content, {
          validated: false,
          validationAttempts: response.validationAttempts,
        });
        if (response.validationError) {
          addMessage("error", `Validation error: ${response.validationError}`);
        }
      } else {
        addMessage("output", response.content);
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "An error occurred";
      addMessage("error", errorMessage);
    }
  }, [inputValue, isLoading, onSubmit, addMessage, addMessageWithMetadata, maxRetries, onMaxRetriesChange, handleClear]);

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

  return (
    <div
      ref={terminalRef}
      className="absolute bottom-0 left-0 right-0 z-40 flex flex-col overflow-hidden rounded-t-lg border border-b-0 border-zinc-700 bg-zinc-900 shadow-2xl"
      style={{ height }}
    >
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
          "hover:bg-zinc-700/50 transition-colors",
        )}
        style={{ height: RESIZE_HANDLE_HEIGHT }}
        onMouseDown={handleResizeStart}
      >
        <div className="h-1 w-12 rounded-full bg-zinc-600" />
      </div>

      <TerminalHeader onClose={onClose} onClear={handleClear} />

      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto px-4 py-3"
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
          {isLoading && <LoadingIndicator />}
        </div>
      </div>

      <div className="border-t border-zinc-700 bg-zinc-900/80 px-4 py-3">
        <div className="flex items-start gap-2">
          <span className="font-mono text-sm text-emerald-400 select-none pt-0.5">
            &gt;
          </span>
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Type your prompt..."
            rows={1}
            className={cn(
              "flex-1 bg-transparent font-mono text-sm text-zinc-200 resize-none",
              "placeholder:text-zinc-600 focus:outline-none",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          />
          <Button
            variant="ghost"
            size="iconSm"
            onClick={handleSubmit}
            disabled={!inputValue.trim() || isLoading}
            className="text-emerald-400 hover:bg-zinc-800 hover:text-emerald-300 disabled:opacity-30"
          >
            <ForwardedIconComponent
              name={isLoading ? "Loader2" : "Send"}
              className={cn("h-4 w-4", isLoading && "animate-spin")}
            />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default GenerateComponentTerminal;

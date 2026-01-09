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
import type { SubmitResult, TerminalMessage, ForgeTerminalProps } from "./types";

const TERMINAL_MIN_HEIGHT = 200;
const TERMINAL_MAX_HEIGHT = 600;
const TERMINAL_DEFAULT_HEIGHT = 300;
const RESIZE_HANDLE_HEIGHT = 8;
const HISTORY_STORAGE_KEY = "component-forge-terminal-history";
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

const TerminalHeader = ({
  onClose,
  onClear,
}: {
  onClose: () => void;
  onClear: () => void;
}) => (
  <div className="flex items-center justify-between border-b border-zinc-700 bg-zinc-900 px-4 py-2">
    <div className="flex items-center gap-2">
      <ForwardedIconComponent
        name="Terminal"
        className="h-4 w-4 text-emerald-400"
      />
      <span className="font-mono text-sm font-medium text-zinc-200">
        Component Forge
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
  onAddToCanvas: (code: string, className: string) => Promise<void>;
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
      await onAddToCanvas(code, className);
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
          <span className="text-xs text-zinc-500">
            (after {validationAttempts} attempts)
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="font-mono text-sm text-emerald-400">
          {className}.py
        </span>

        <div className="flex items-center">
          <Button
            variant="ghost"
            size="iconSm"
            onClick={() => setIsCodeModalOpen(true)}
            className="text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            title="View Code"
          >
            <ForwardedIconComponent name="Code" className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="iconSm"
            onClick={handleDownload}
            className="text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            title="Download"
          >
            <ForwardedIconComponent name="Download" className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="iconSm"
            onClick={handleSaveToSidebar}
            disabled={isSavingToSidebar}
            className="text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50"
            title="Save to Sidebar"
          >
            <ForwardedIconComponent
              name={isSavingToSidebar ? "Loader2" : "SaveAll"}
              className={cn("h-4 w-4", isSavingToSidebar && "animate-spin")}
            />
          </Button>

          <Button
            variant="ghost"
            size="iconSm"
            onClick={handleAddToCanvas}
            disabled={isAddingToCanvas}
            className="text-emerald-400 hover:bg-zinc-800 hover:text-emerald-300 disabled:opacity-50"
            title="Add to Canvas"
          >
            <ForwardedIconComponent
              name={isAddingToCanvas ? "Loader2" : "Plus"}
              className={cn("h-4 w-4", isAddingToCanvas && "animate-spin")}
            />
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
    </div>
  );
};

const MessageLine = ({
  message,
  onAddToCanvas,
  onSaveToSidebar,
}: {
  message: TerminalMessage;
  onAddToCanvas: (code: string, className: string) => Promise<void>;
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

  // Show ComponentResultLine for validated components with code
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
  <div className="flex items-center gap-2 font-mono text-sm text-zinc-500">
    <span className="select-none opacity-70">&gt; </span>
    <div className="flex gap-1">
      <span className="animate-pulse">.</span>
      <span className="animate-pulse delay-100">.</span>
      <span className="animate-pulse delay-200">.</span>
    </div>
  </div>
);

const ForgeTerminal = ({
  isOpen,
  onClose,
  onSubmit,
  onAddToCanvas,
  onSaveToSidebar,
  isLoading = false,
}: ForgeTerminalProps) => {
  const [messages, setMessages] = useState<TerminalMessage[]>([
    {
      id: nanoid(),
      type: "system",
      content: "Welcome to Component Forge. Type your prompt and press Enter.",
      timestamp: new Date(),
    },
  ]);
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

  const handleSubmit = useCallback(async () => {
    const trimmedInput = inputValue.trim();
    if (!trimmedInput || isLoading) return;

    saveToHistory(trimmedInput);
    setHistoryIndex(-1);
    addMessage("input", trimmedInput);
    setInputValue("");

    try {
      const response: SubmitResult = await onSubmit(trimmedInput);

      // Determine message type based on validation status
      if (response.validated === true) {
        // Successfully validated component
        addMessageWithMetadata("validated", response.content, {
          validated: true,
          className: response.className,
          validationAttempts: response.validationAttempts,
          componentCode: response.componentCode,
        });
      } else if (response.validated === false) {
        // Validation failed after retries
        addMessageWithMetadata("validation_error", response.content, {
          validated: false,
          validationAttempts: response.validationAttempts,
        });
        if (response.validationError) {
          addMessage("error", `Validation error: ${response.validationError}`);
        }
      } else {
        // No validation info (regular response)
        addMessage("output", response.content);
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "An error occurred";
      addMessage("error", errorMessage);
    }
  }, [inputValue, isLoading, onSubmit, addMessage, addMessageWithMetadata]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
        return;
      }

      const history = getHistory();
      if (history.length === 0) return;

      // Only navigate history when cursor is at the start/end of input
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

  const handleClear = useCallback(() => {
    setMessages([
      {
        id: nanoid(),
        type: "system",
        content: "Terminal cleared.",
        timestamp: new Date(),
      },
    ]);
  }, []);

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
      className="absolute bottom-0 left-0 right-0 z-50 flex flex-col overflow-hidden rounded-t-lg border border-b-0 border-zinc-700 bg-zinc-900 shadow-2xl"
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

export default ForgeTerminal;

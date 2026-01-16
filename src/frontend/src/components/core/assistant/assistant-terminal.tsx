import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { nanoid } from "nanoid";
import { Button } from "@/components/ui/button";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { useAssistantStore, type AssistantMessageData } from "@/stores/assistantStore";

import {
  TERMINAL_MIN_HEIGHT,
  TERMINAL_MAX_HEIGHT,
  TERMINAL_DEFAULT_HEIGHT,
  TERMINAL_CONFIG_HEIGHT,
  RESIZE_HANDLE_HEIGHT,
  TEXTAREA_MAX_HEIGHT,
  SCROLL_BOTTOM_THRESHOLD,
} from "./assistant.constants";
import type {
  AssistantTerminalProps,
  AssistantMessage,
  ProgressInfo,
} from "./assistant.types";
import { getHistory, saveToHistory } from "./helpers/history";
import { categorizeError } from "./helpers/error-categorizer";
import { parseCommand } from "./helpers/command-parser";
import { getStepConfig } from "./helpers/step-config";
import { TerminalHeader } from "./components/terminal-header";
import { MessageLine } from "./components/message-line";
import { LoadingIndicator } from "./components/loading-indicator";
import { ConfigLoading, ConfigurationRequired } from "./components/configuration-required";

const AssistantTerminal = ({
  isOpen,
  onClose,
  onSubmit,
  onAddToCanvas,
  isLoading = false,
  maxRetries,
  onMaxRetriesChange,
  isConfigured,
  isConfigLoading,
  onConfigureClick,
  configData,
}: AssistantTerminalProps) => {
  const messages = useAssistantStore((state) => state.messages);
  const setMessages = useAssistantStore((state) => state.setMessages);
  const storeAddMessage = useAssistantStore((state) => state.addMessage);
  const scrollPosition = useAssistantStore((state) => state.scrollPosition);
  const setScrollPosition = useAssistantStore((state) => state.setScrollPosition);
  const selectedModel = useAssistantStore((state) => state.selectedModel);
  const setSelectedModel = useAssistantStore((state) => state.setSelectedModel);
  const resetSessionId = useAssistantStore((state) => state.resetSessionId);

  const [inputValue, setInputValue] = useState("");
  const [height, setHeight] = useState(TERMINAL_DEFAULT_HEIGHT);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [progress, setProgress] = useState<ProgressInfo>(null);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const prevIsOpenRef = useRef<boolean>(false);

  const getWelcomeMessages = useCallback(
    (): AssistantMessageData[] => [
      {
        id: nanoid(),
        type: "system",
        content:
          "Welcome to Assistant. Ask about Langflow documentation or describe a custom component to generate. Type HELP for commands.",
        timestamp: new Date(),
      },
    ],
    [],
  );

  useEffect(() => {
    if (messages.length === 0) {
      setMessages(getWelcomeMessages());
    }
  }, [messages.length, setMessages, getWelcomeMessages]);

  useEffect(() => {
    if (!configData?.providers?.length) return;

    const isStoredModelAvailable =
      selectedModel &&
      configData.providers.some((p) =>
        p.models.some((m) => `${p.name}:${m.name}` === selectedModel),
      );

    if (
      !isStoredModelAvailable &&
      configData.default_provider &&
      configData.default_model
    ) {
      setSelectedModel(
        `${configData.default_provider}:${configData.default_model}`,
      );
    }
  }, [configData, selectedModel, setSelectedModel]);

  const getProviderAndModel = useCallback(() => {
    if (!selectedModel) return { provider: undefined, modelName: undefined };
    const parts = selectedModel.split(":");
    return { provider: parts[0], modelName: parts[1] };
  }, [selectedModel]);

  const scrollToBottom = useCallback(() => {
    const container = messagesContainerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
      setScrollPosition(-1);
    }
  }, [setScrollPosition]);

  const handleScroll = useCallback(() => {
    const container = messagesContainerRef.current;
    if (container) {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isAtBottom =
        scrollHeight - scrollTop - clientHeight < SCROLL_BOTTOM_THRESHOLD;
      setScrollPosition(isAtBottom ? -1 : scrollTop);
    }
  }, [setScrollPosition]);

  useLayoutEffect(() => {
    const justOpened = isOpen && !prevIsOpenRef.current;
    prevIsOpenRef.current = isOpen;

    if (!isOpen || messages.length === 0) return;

    const container = messagesContainerRef.current;
    if (!container) return;

    const doRestore = () => {
      if (!messagesContainerRef.current) return;
      const target =
        scrollPosition === -1
          ? messagesContainerRef.current.scrollHeight
          : scrollPosition;
      messagesContainerRef.current.scrollTop = target;
    };

    if (justOpened) {
      doRestore();
      requestAnimationFrame(doRestore);
      setTimeout(doRestore, 10);
      setTimeout(doRestore, 50);
      setTimeout(doRestore, 100);
    }
  }, [isOpen, messages.length, scrollPosition]);

  useLayoutEffect(() => {
    if (scrollPosition === -1 && isOpen) {
      scrollToBottom();
    }
  }, [messages.length, isLoading, scrollPosition, scrollToBottom, isOpen]);

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
    ]);
    setScrollPosition(-1);
    resetSessionId();
  }, [setMessages, setScrollPosition, resetSessionId]);

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

      const handleProgress = (p: {
        step: "generating" | "validating" | "generation_complete" | "extracting_code" | "validated" | "validation_failed" | "retrying";
        attempt: number;
        maxAttempts: number;
        message?: string;
        error?: string;
        componentName?: string;
        componentCode?: string;
      }) => {
        setProgress(p);

        // Skip extracting_code step - not shown in UI
        if (p.step === "extracting_code") return;

        // Add progress message to chat history
        const config = getStepConfig(p.step, p.attempt, p.maxAttempts, p.error);
        addMessageWithMetadata("progress", config.text, {
          progress: {
            step: p.step,
            icon: config.icon,
            color: config.color,
            spin: false, // Don't spin for persisted messages
            attempt: p.attempt,
            maxAttempts: p.maxAttempts,
            error: p.error,
            componentName: p.componentName,
            componentCode: p.componentCode,
          },
        });
      };

      const response = await onSubmit(
        trimmedInput,
        provider,
        modelName,
        handleProgress,
      );
      setProgress(null);

      if (response.validated === true) {
        addMessageWithMetadata("validated", response.content, {
          validated: true,
          className: response.className,
          validationAttempts: response.validationAttempts,
          componentCode: response.componentCode,
        });
      } else if (response.validated === false) {
        // Error already shown via progress steps (validation_failed)
        // No additional message needed
      } else {
        addMessage("output", response.content);
      }
    } catch (error: unknown) {
      setProgress(null);
      let errorMessage = "An error occurred";

      const axiosError = error as {
        response?: { data?: { detail?: string }; status?: number };
      };
      if (axiosError?.response?.data?.detail) {
        errorMessage = axiosError.response.data.detail;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }

      const errorCategory = categorizeError(
        errorMessage,
        axiosError?.response?.status,
      );

      switch (errorCategory) {
        case "rate_limit":
          addMessage(
            "error",
            "Rate limit exceeded. Please wait a moment and try again.",
          );
          break;
        case "quota":
          addMessage(
            "error",
            "API quota exceeded. Please check your account billing.",
          );
          break;
        case "provider":
          addMessage("error", "Model provider configuration issue.");
          addMessage("system", "Go to Settings → Model Providers to configure.");
          break;
        default:
          addMessage("error", errorMessage);
      }
    }
  }, [
    inputValue,
    isLoading,
    onSubmit,
    addMessage,
    addMessageWithMetadata,
    maxRetries,
    onMaxRetriesChange,
    handleClear,
    getProviderAndModel,
  ]);

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
      const isAtStart =
        textarea.selectionStart === 0 && textarea.selectionEnd === 0;
      const isAtEnd = textarea.selectionStart === textarea.value.length;

      if (e.key === "ArrowUp" && isAtStart) {
        e.preventDefault();
        const newIndex =
          historyIndex === -1
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

  const terminalHeight =
    isConfigured === false ? TERMINAL_CONFIG_HEIGHT : height;

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
            "transition-colors hover:bg-accent",
          )}
          style={{ height: RESIZE_HANDLE_HEIGHT }}
          onMouseDown={handleResizeStart}
        >
          <div className="h-1 w-12 rounded-full bg-muted-foreground" />
        </div>
      )}

      <TerminalHeader
        onClose={onClose}
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
          <div className="relative flex-1 overflow-hidden">
            <Button
              variant="ghost"
              size="iconSm"
              onClick={handleClear}
              className="absolute right-4 top-2 z-10 text-muted-foreground hover:bg-muted hover:text-foreground"
              title="Clear chat"
            >
              <ForwardedIconComponent name="Trash2" className="h-3.5 w-3.5" />
            </Button>
            <div
              ref={messagesContainerRef}
              onScroll={handleScroll}
              className="h-full overflow-y-auto px-4 py-3"
              style={{ overflowAnchor: "none" }}
            >
              <div className="flex flex-col gap-1">
                {messages.map((message) => (
                  <MessageLine
                    key={message.id}
                    message={message}
                    onAddToCanvas={onAddToCanvas}
                  />
                ))}
                {(isLoading || progress) && <LoadingIndicator />}
              </div>
            </div>
          </div>

          <div className="border-t border-border bg-background/80 px-4 py-3">
            <div className="flex items-start gap-2">
              <span className="select-none pt-0.5 font-mono text-sm text-accent-emerald-foreground">
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
                  "flex-1 resize-none bg-transparent font-mono text-sm text-foreground",
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

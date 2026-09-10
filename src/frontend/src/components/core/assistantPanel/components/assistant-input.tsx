import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { AgenticStepType } from "@/controllers/API/queries/agentic";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";
import { getAssistantPlaceholder } from "../assistant-panel.constants";
import type { AssistantModel } from "../assistant-panel.types";
import { getRandomPlaceholderMessage } from "../helpers/messages";
import { useAssistantSelectedModel } from "../hooks/use-assistant-selected-model";
import { useAutoGrowTextarea } from "../hooks/use-auto-grow-textarea";
import { useComponentMentions } from "../hooks/use-component-mentions";
import { useEnabledModels } from "../hooks/use-enabled-models";
import { useInputHistory } from "../hooks/use-input-history";
import { AssistantMentionPopover } from "./assistant-mention-popover";
import { ModelSelector } from "./model-selector";

// During these steps the message area shows the thinking animation, so the
// input keeps a static intent-specific placeholder instead of rotating text.
const GENERATING_STEPS: AgenticStepType[] = [
  "generating",
  "generating_component",
  "generating_plan",
  "generating_flow",
  "orchestrating",
  "generating_document",
];

// Intent-specific placeholder per generating step (no random rotation while
// the LLM produces a component or flow).
const GENERATING_PLACEHOLDER: Partial<Record<AgenticStepType, string>> = {
  generating: "Generating response...",
  generating_component: "Generating component...",
  generating_plan: "Generating plan...",
  generating_flow: "Generating flow...",
  orchestrating: "Orchestrating...",
  generating_document: "Generating document...",
};

// Hook for rotating placeholder messages during post-generation processing
function useAnimatedPlaceholder(
  shouldAnimate: boolean,
  intervalMs = 2000,
): string {
  const [currentMessage, setCurrentMessage] = useState(() =>
    getRandomPlaceholderMessage(),
  );

  useEffect(() => {
    if (!shouldAnimate) {
      return;
    }

    // Set initial message when animation starts
    setCurrentMessage(getRandomPlaceholderMessage());

    // Rotate messages at interval
    const interval = setInterval(() => {
      setCurrentMessage(getRandomPlaceholderMessage());
    }, intervalMs);

    return () => clearInterval(interval);
  }, [shouldAnimate, intervalMs]);

  return currentMessage;
}

const COMPOSER_MAX_HEIGHT_PX = 144; // 9rem — keeps the conversation above the composer readable

interface AssistantInputProps {
  onSend: (message: string, model: AssistantModel | null) => void;
  onStop?: () => void;
  disabled?: boolean;
  isProcessing?: boolean;
  currentStep?: AgenticStepType | null;
  placeholder?: string;
  compact?: boolean;
  autoFocus?: boolean;
  draftMessage?: string;
  onDraftChange?: (draft: string) => void;
  /**
   * Set when the user dismissed a plan and is composing the refinement.
   * Swaps the idle placeholder for a directed cue ("Tell me what to
   * change…"). Has no effect while a generating step is active — the
   * intent-specific generating placeholder takes precedence.
   */
  isRefiningPlan?: boolean;
  /** Notifies the panel when the @-mention popover opens/closes so it can make
   * room for the upward-opening list in the compact (no-messages) layout. */
  onMentionOpenChange?: (open: boolean) => void;
}

const REFINING_PLAN_PLACEHOLDER = "Tell me what to change…";

export function AssistantInput({
  onSend,
  onStop,
  disabled = false,
  isProcessing = false,
  currentStep = null,
  placeholder,
  compact = false,
  autoFocus = false,
  draftMessage = "",
  onDraftChange,
  isRefiningPlan = false,
  onMentionOpenChange,
}: AssistantInputProps) {
  const { t } = useTranslation();
  // Server-owned cap (LANGFLOW_ASSISTANT_MAX_MESSAGE_LENGTH), mirrored through /config so the
  // composer and the assistant API agree on one number.
  const maxMessageLength = useUtilityStore(
    (state) => state.assistantMaxMessageLength,
  );
  const [message, setMessage] = useState(draftMessage);
  const [idlePlaceholder] = useState(getAssistantPlaceholder);

  // Show animated placeholder only during post-generation steps (when thinking animation is done)
  const isPostGenerationStep =
    isProcessing &&
    currentStep !== null &&
    !GENERATING_STEPS.includes(currentStep);
  const animatedPlaceholder = useAnimatedPlaceholder(isPostGenerationStep);
  const [selectedModel, setSelectedModel] = useAssistantSelectedModel();
  const { isCatalogReady, isModelEnabled } = useEnabledModels();
  const limitHintId = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const inputHistory = useInputHistory();
  useAutoGrowTextarea(textareaRef, message, COMPOSER_MAX_HEIGHT_PX);

  // Auto-focus textarea when requested
  useEffect(() => {
    if (autoFocus && textareaRef.current && !disabled && !isProcessing) {
      textareaRef.current.focus();
    }
  }, [autoFocus, disabled, isProcessing]);

  const updateMessage = (value: string) => {
    setMessage(value);
    onDraftChange?.(value);
  };

  const mentions = useComponentMentions({
    value: message,
    setValue: updateMessage,
    textareaRef,
  });

  useEffect(() => {
    onMentionOpenChange?.(mentions.isOpen);
  }, [mentions.isOpen, onMentionOpenChange]);

  const handleSend = () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || disabled || isProcessing) return;
    if (trimmedMessage.length > maxMessageLength) return;
    if (!isCatalogReady || !isModelEnabled(selectedModel)) return;
    inputHistory.push(trimmedMessage);
    onSend(trimmedMessage, selectedModel);
    updateMessage("");
  };

  /**
   * Up/Down trigger history recall only when the cursor is on the edge of
   * the textarea (first line for Up, last line for Down). This keeps the
   * default cursor-movement behavior usable in multiline drafts — pressing
   * Up while editing a second line still moves the cursor up between
   * lines, not into history.
   */
  function isCursorOnFirstLine(textarea: HTMLTextAreaElement): boolean {
    const value = textarea.value;
    const firstNewline = value.indexOf("\n");
    if (firstNewline === -1) return true;
    return textarea.selectionStart <= firstNewline;
  }

  function isCursorOnLastLine(textarea: HTMLTextAreaElement): boolean {
    const value = textarea.value;
    const lastNewline = value.lastIndexOf("\n");
    if (lastNewline === -1) return true;
    return textarea.selectionStart > lastNewline;
  }

  function applyRecall(recalled: string | null) {
    if (recalled === null) return;
    updateMessage(recalled);
    // Defer cursor positioning to after React updates the value.
    requestAnimationFrame(() => {
      const textarea = textareaRef.current;
      if (textarea) {
        textarea.setSelectionRange(recalled.length, recalled.length);
      }
    });
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentions.handleKeyDown(e)) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
      return;
    }
    if (e.key === "Escape") {
      textareaRef.current?.blur();
      return;
    }
    const textarea = e.currentTarget;
    if (e.key === "ArrowUp" && isCursorOnFirstLine(textarea)) {
      const recalled = inputHistory.recall("up", message);
      if (recalled !== null) {
        e.preventDefault();
        applyRecall(recalled);
      }
      return;
    }
    if (e.key === "ArrowDown" && isCursorOnLastLine(textarea)) {
      const recalled = inputHistory.recall("down", message);
      if (recalled !== null) {
        e.preventDefault();
        applyRecall(recalled);
      }
    }
  };

  const messageLength = message.length;
  // The cap is hard, but never silent: the counter is always on screen and hitting the limit
  // names the environment variable that raises it.
  const isAtLimit = messageLength >= maxMessageLength;
  // Gate on selectedModel too: a fast click during the model selector's
  // auto-select window would fire with a null model and drop the message.
  const canSend =
    message.trim().length > 0 &&
    !disabled &&
    isCatalogReady &&
    isModelEnabled(selectedModel);

  return (
    <div className="relative px-2 pb-2">
      {/* Glow effect below input — uses the assistant brand tokens so the glow
          color survives a theme swap and a brand re-skin in one place. */}
      <div
        className="pointer-events-none absolute -bottom-2 left-1/2 h-16 w-3/4 -translate-x-1/2 rounded-full opacity-60 blur-2xl"
        style={{
          background:
            "linear-gradient(90deg, hsl(var(--accent-assistant-purple) / 0.4) 0%, hsl(var(--accent-assistant-brand) / 0.5) 50%, hsl(var(--accent-assistant-purple) / 0.4) 100%)",
        }}
      />
      <div
        className={cn(
          "relative flex cursor-text flex-col rounded-md border border-control bg-background pb-2.5 transition-colors focus-within:border-muted-foreground shadow-[0_0_15px_hsl(var(--accent-assistant-purple)/0.12),0_0_30px_hsl(var(--accent-assistant-brand)/0.08)]",
          compact ? "gap-1" : "gap-4",
          // With the limit hint on screen the column gap would stack on top of the hint's own
          // padding, spacing it away from the footer far wider than from the text above it.
          isAtLimit && "gap-0",
        )}
        onClick={() => textareaRef.current?.focus()}
      >
        {mentions.isOpen && (
          <AssistantMentionPopover
            items={mentions.items}
            activeIndex={mentions.activeIndex}
            onHover={mentions.setActiveIndex}
            onSelect={mentions.confirm}
          />
        )}
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={message}
            maxLength={maxMessageLength}
            aria-describedby={isAtLimit ? limitHintId : undefined}
            onChange={(e) => {
              updateMessage(e.target.value);
              mentions.handleValueChange(
                e.target.value,
                e.target.selectionStart ?? e.target.value.length,
              );
            }}
            data-testid="assistant-input-textarea"
            onKeyDown={handleKeyDown}
            placeholder={
              isProcessing
                ? isPostGenerationStep
                  ? ""
                  : (currentStep && GENERATING_PLACEHOLDER[currentStep]) ||
                    t("assistant.workingOnIt")
                : isRefiningPlan
                  ? REFINING_PLAN_PLACEHOLDER
                  : (placeholder ?? idlePlaceholder)
            }
            disabled={disabled || isProcessing}
            className={cn(
              "resize-none overflow-y-auto border-0 bg-transparent px-4 pt-3 text-sm focus-visible:ring-0 disabled:bg-transparent disabled:cursor-not-allowed",
              // Hard stop for the auto-grow above: past this the draft scrolls inside the
              // composer so the conversation stays readable.
              "max-h-[9rem]",
              compact ? "min-h-0" : "min-h-[60px]",
              isProcessing && !isPostGenerationStep && "placeholder:opacity-50",
            )}
            rows={compact ? 1 : 2}
          />
          {isPostGenerationStep && !message && (
            <div className="pointer-events-none absolute left-4 top-3 flex items-center gap-2 text-sm text-muted-foreground">
              <ForwardedIconComponent
                name="Loader2"
                className="h-4 w-4 animate-spin"
              />
              <span className="animate-pulse">{animatedPlaceholder}</span>
            </div>
          )}
          {/* Inside the textarea wrapper on purpose: as a direct child of the composer's
              flex column it would also inherit the column gap, spacing the hint far wider
              than the welcome screen's. */}
          {isAtLimit && (
            <div
              id={limitHintId}
              role="status"
              data-testid="assistant-input-limit-hint"
              className="px-4 py-1 text-xs text-destructive"
            >
              {t("assistant.messageLimitReached")}
            </div>
          )}
        </div>
        <div className="flex items-center justify-between px-3">
          <div className="flex items-center gap-4">
            <ModelSelector
              selectedModel={selectedModel}
              onModelChange={setSelectedModel}
            />
          </div>
          <div className="flex items-center gap-2">
            <span
              data-testid="assistant-input-char-count"
              className={cn(
                "text-xs tabular-nums",
                isAtLimit ? "text-destructive" : "text-muted-foreground",
              )}
            >
              {messageLength}/{maxMessageLength}
            </span>
            {isProcessing ? (
              <button
                type="button"
                onClick={onStop}
                title={t("assistant.stopGeneration")}
                data-testid="assistant-stop-button"
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted-foreground/15 text-muted-foreground transition-colors hover:bg-muted-foreground/25"
              >
                <ForwardedIconComponent
                  name="Square"
                  className="h-3 w-3 fill-current"
                />
              </button>
            ) : (
              <Button
                size="icon"
                data-testid="assistant-send-button"
                className="h-8 w-8 rounded-lg"
                onClick={handleSend}
                disabled={!canSend}
                title={t("assistant.sendMessage")}
              >
                <ForwardedIconComponent name="ArrowUp" className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

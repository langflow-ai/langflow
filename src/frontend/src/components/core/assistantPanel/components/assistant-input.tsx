import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { AgenticStepType } from "@/controllers/API/queries/agentic";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/utils/utils";
import { ASSISTANT_PLACEHOLDER } from "../assistant-panel.constants";
import type { AssistantModel } from "../assistant-panel.types";
import { getRandomPlaceholderMessage } from "../helpers/messages";
import { ModelSelector } from "./model-selector";

// Steps where the "thinking" animation is showing in the message area
const GENERATING_STEPS: AgenticStepType[] = ["generating", "generating_component"];

// Hook for rotating placeholder messages during post-generation processing
function useAnimatedPlaceholder(shouldAnimate: boolean, intervalMs = 2000): string {
  const [currentMessage, setCurrentMessage] = useState(() => getRandomPlaceholderMessage());

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

const ASSISTANT_MODEL_STORAGE_KEY = "langflow-assistant-selected-model";

interface AssistantInputProps {
  onSend: (message: string, model: AssistantModel | null) => void;
  onStop?: () => void;
  disabled?: boolean;
  isProcessing?: boolean;
  currentStep?: AgenticStepType | null;
  placeholder?: string;
}

export function AssistantInput({
  onSend,
  onStop,
  disabled = false,
  isProcessing = false,
  currentStep = null,
  placeholder,
}: AssistantInputProps) {
  const [message, setMessage] = useState("");

  // Show animated placeholder only during post-generation steps (when thinking animation is done)
  const isPostGenerationStep = isProcessing && currentStep !== null && !GENERATING_STEPS.includes(currentStep);
  const animatedPlaceholder = useAnimatedPlaceholder(isPostGenerationStep);
  const [selectedModel, setSelectedModel] = useState<AssistantModel | null>(() => {
    // Load from localStorage on init
    try {
      const saved = localStorage.getItem(ASSISTANT_MODEL_STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      // localStorage may be unavailable (private browsing) or corrupted
      return null;
    }
  });
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Save to localStorage when model changes
  useEffect(() => {
    if (selectedModel) {
      localStorage.setItem(ASSISTANT_MODEL_STORAGE_KEY, JSON.stringify(selectedModel));
    }
  }, [selectedModel]);

  const handleSend = () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || disabled) return;
    onSend(trimmedMessage, selectedModel);
    setMessage("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = message.trim().length > 0 && !disabled;

  return (
    <div className="px-2 pb-2.5">
      <div className="flex flex-col gap-4 rounded-md border border-border bg-background pb-2.5 transition-colors focus-within:border-muted-foreground">
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isPostGenerationStep ? "" : (placeholder ?? ASSISTANT_PLACEHOLDER)}
            disabled={disabled || isProcessing}
            className={cn(
              "min-h-[60px] resize-none border-0 bg-transparent px-4 pt-3 text-sm focus-visible:ring-0 disabled:bg-transparent disabled:cursor-not-allowed",
              isProcessing && !isPostGenerationStep && "placeholder:opacity-50"
            )}
            rows={2}
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
        </div>
        <div className="flex items-center justify-between px-3">
          <div className="flex items-center gap-4">
            <ModelSelector
              selectedModel={selectedModel}
              onModelChange={setSelectedModel}
            />
          </div>
          {isProcessing ? (
            <button
              type="button"
              onClick={onStop}
              title="Stop generation"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted-foreground/15 text-muted-foreground transition-colors hover:bg-muted-foreground/25"
            >
              <ForwardedIconComponent name="Square" className="h-3 w-3 fill-current" />
            </button>
          ) : (
            <Button
              size="icon"
              className="h-8 w-8 rounded-lg"
              onClick={handleSend}
              disabled={!canSend}
              title="Send message"
            >
              <ForwardedIconComponent name="ArrowUp" className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

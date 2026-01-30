import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ASSISTANT_PLACEHOLDER } from "../assistant-panel.constants";
import type { AssistantModel } from "../assistant-panel.types";
import { ModelSelector } from "./model-selector";

const ASSISTANT_MODEL_STORAGE_KEY = "langflow-assistant-selected-model";

interface AssistantInputProps {
  onSend: (message: string, model: AssistantModel | null) => void;
  onStop?: () => void;
  disabled?: boolean;
  isProcessing?: boolean;
  placeholder?: string;
}

export function AssistantInput({
  onSend,
  onStop,
  disabled = false,
  isProcessing = false,
  placeholder,
}: AssistantInputProps) {
  const [message, setMessage] = useState("");
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
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? ASSISTANT_PLACEHOLDER}
          disabled={disabled}
          className="min-h-[60px] resize-none border-0 bg-transparent px-4 pt-3 text-sm focus-visible:ring-0 disabled:bg-transparent disabled:cursor-not-allowed disabled:opacity-100"
          rows={2}
        />
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

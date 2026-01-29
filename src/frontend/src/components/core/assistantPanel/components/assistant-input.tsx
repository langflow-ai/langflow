import { useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ASSISTANT_PLACEHOLDER } from "../assistant-panel.constants";
import type { AssistantModel } from "../assistant-panel.types";
import { ModelSelector } from "./model-selector";

interface AssistantInputProps {
  onSend: (message: string, model: AssistantModel | null) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function AssistantInput({
  onSend,
  disabled = false,
  placeholder,
}: AssistantInputProps) {
  const [message, setMessage] = useState("");
  const [selectedModel, setSelectedModel] = useState<AssistantModel | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
      <div className="flex flex-col gap-4 rounded-md border border-muted-foreground bg-background/90 pb-2.5">
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? ASSISTANT_PLACEHOLDER}
          disabled={disabled}
          className="min-h-[60px] resize-none border-0 bg-transparent px-4 pt-3 text-sm focus-visible:ring-0"
          rows={2}
        />
        <div className="flex items-center justify-between px-3">
          <div className="flex items-center gap-4">
            <ModelSelector
              selectedModel={selectedModel}
              onModelChange={setSelectedModel}
            />
          </div>
          <Button
            size="icon"
            className="h-8 w-8 rounded-lg"
            onClick={handleSend}
            disabled={!canSend}
            title="Send message"
          >
            <ForwardedIconComponent name="ArrowUp" className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

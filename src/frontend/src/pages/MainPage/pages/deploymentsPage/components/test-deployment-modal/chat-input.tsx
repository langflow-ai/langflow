import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea to fit content
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  // Reset height after send
  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="px-4 pb-4 pt-2">
      <div
        className={cn(
          "flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2",
          "focus-within:ring-1 focus-within:ring-ring",
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message"
          disabled={disabled}
          rows={1}
          className="max-h-40 flex-1 resize-none overflow-y-auto bg-transparent text-sm leading-5 text-foreground placeholder:text-muted-foreground focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
        <Button
          size="icon"
          variant="default"
          onClick={handleSend}
          disabled={!value.trim() || disabled}
          className="h-8 w-8 flex-shrink-0 self-end rounded-lg"
          aria-label="Send message"
        >
          <ForwardedIconComponent name="Send" className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

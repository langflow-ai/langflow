import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";

interface InlineEditableTextProps {
  value: string;
  onSave: (next: string) => void;
  /** Names both the field and the pencil button that opens it. */
  label: string;
  /** Shown as the button text when there is no value yet. */
  emptyLabel?: string;
  required?: boolean;
  maxLength: number;
  editing: boolean;
  setEditing: (editing: boolean) => void;
  className?: string;
  testId: string;
}

/** Text that turns into a field in place: Enter or leaving the field saves, Escape cancels. */
export default function InlineEditableText({
  value,
  onSave,
  label,
  emptyLabel,
  required = false,
  maxLength,
  editing,
  setEditing,
  className,
  testId,
}: InlineEditableTextProps) {
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);
  const editButtonRef = useRef<HTMLButtonElement>(null);
  // Escape and Enter both end editing and then blur the field; only the first one decides.
  const settled = useRef(false);

  useEffect(() => {
    if (!editing) return;
    settled.current = false;
    setDraft(value);
    requestAnimationFrame(() => inputRef.current?.select());
  }, [editing, value]);

  const finish = (save: boolean) => {
    if (settled.current) return;
    settled.current = true;
    const next = draft.trim();
    if (save && next !== value && (next || !required)) onSave(next);
    setEditing(false);
    requestAnimationFrame(() => editButtonRef.current?.focus());
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      finish(true);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      finish(false);
    }
  };

  if (editing) {
    return (
      <Input
        ref={inputRef}
        aria-label={label}
        value={draft}
        maxLength={maxLength}
        className={cn("h-8", className)}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => finish(true)}
        data-testid={`${testId}-input`}
      />
    );
  }

  if (!value && emptyLabel) {
    return (
      <button
        ref={editButtonRef}
        type="button"
        className="self-start text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        onClick={() => setEditing(true)}
        data-testid={`${testId}-edit`}
      >
        {emptyLabel}
      </button>
    );
  }

  return (
    <span className="group/inline flex min-w-0 items-center gap-1">
      <span className={cn("min-w-0 truncate", className)} data-testid={testId}>
        {value}
      </span>
      <Button
        ref={editButtonRef}
        variant="ghost"
        size="icon"
        className="h-7 w-7 shrink-0 text-muted-foreground"
        aria-label={label}
        onClick={() => setEditing(true)}
        data-testid={`${testId}-edit`}
      >
        <ForwardedIconComponent name="Pencil" className="h-3.5 w-3.5" />
      </Button>
    </span>
  );
}

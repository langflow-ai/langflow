import { useCallback, useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";

interface EditableToolNameProps {
  value: string;
  placeholder: string;
  onSave: (name: string) => void;
}

export function EditableToolName({
  value,
  placeholder,
  onSave,
}: EditableToolNameProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const confirm = useCallback(() => {
    onSave(draft);
    setEditing(false);
  }, [draft, onSave]);

  const cancel = useCallback(() => {
    setDraft(value);
    setEditing(false);
  }, [value]);

  if (editing) {
    return (
      <div className="flex items-center gap-1.5">
        <Input
          ref={inputRef}
          className="h-7 w-48 text-sm"
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={confirm}
          onKeyDown={(e) => {
            if (e.key === "Enter") confirm();
            if (e.key === "Escape") cancel();
          }}
          data-testid="tool-name-input"
        />
        <button
          type="button"
          onClick={confirm}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Confirm"
          aria-label="Confirm tool name"
        >
          <ForwardedIconComponent name="Check" className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-sm font-medium text-foreground">
        {value || placeholder}
      </span>
      <button
        type="button"
        onClick={() => {
          setDraft(value);
          setEditing(true);
        }}
        className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        title="Edit tool name"
        aria-label="Edit tool name"
        data-testid="edit-tool-name"
      >
        <ForwardedIconComponent name="Pencil" className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";

interface EditableToolNameProps {
  onSave: (name: string) => void;
  placeholder: string;
  value: string;
}

export function EditableToolName({
  onSave,
  placeholder,
  value,
}: EditableToolNameProps) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!editing) return;
    inputRef.current?.focus();
    inputRef.current?.select();
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
          data-testid="tool-name-input"
          placeholder={placeholder}
          value={draft}
          onBlur={confirm}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") confirm();
            if (event.key === "Escape") cancel();
          }}
        />
        <button
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          title={t("deployments.confirmToolName")}
          type="button"
          onClick={confirm}
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
        className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        data-testid="edit-tool-name"
        title={t("deployments.editToolName")}
        type="button"
        onClick={() => {
          setDraft(value);
          setEditing(true);
        }}
      >
        <ForwardedIconComponent name="Pencil" className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

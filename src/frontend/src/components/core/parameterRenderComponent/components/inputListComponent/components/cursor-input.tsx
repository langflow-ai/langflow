import { forwardRef, useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { handleKeyDown } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";

interface CursorInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  dataTestId?: string;
  editNode?: boolean;
  onFocus?: () => void;
  onBlur?: () => void;
}

export const CursorInput = forwardRef<HTMLInputElement, CursorInputProps>(
  (
    {
      value,
      onChange,
      disabled = false,
      placeholder,
      className,
      dataTestId,
      editNode = false,
      onFocus,
      onBlur,
    },
    ref,
  ) => {
    // Local state for input value to handle cursor position
    const [localValue, setLocalValue] = useState<string>(value);
    const [cursor, setCursor] = useState<number | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Update local value when prop changes
    useEffect(() => {
      setLocalValue(value);
    }, [value]);

    // Handle cursor position restoration
    useEffect(() => {
      if (inputRef.current && cursor !== null) {
        inputRef.current.setSelectionRange(cursor, cursor);
      }
    }, [cursor]);

    const handleChangeInput = (e: React.ChangeEvent<HTMLInputElement>) => {
      setCursor(e.target.selectionStart);
      setLocalValue(e.target.value);
      onChange(e.target.value);
    };

    const handleInputBlur = () => {
      onBlur?.();
    };

    const handleInputFocus = () => {
      onFocus?.();
    };

    return (
      <Input
        ref={ref || inputRef}
        disabled={disabled}
        type="text"
        value={localValue}
        className={cn(
          "w-full text-primary",
          editNode ? "input-edit-node" : "",
          disabled ? "disabled-state" : "",
          className,
        )}
        placeholder={placeholder}
        onChange={handleChangeInput}
        onKeyDown={(event) => handleKeyDown(event, localValue, "")}
        data-testid={dataTestId}
        onFocus={handleInputFocus}
        onBlur={handleInputBlur}
      />
    );
  },
);

CursorInput.displayName = "CursorInput";

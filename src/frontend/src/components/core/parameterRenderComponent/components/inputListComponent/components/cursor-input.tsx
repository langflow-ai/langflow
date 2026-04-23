import { forwardRef, useRef } from "react";
import { Input } from "@/components/ui/input";
import { handleKeyDown } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import { useIMEInputForOnChange } from "../../../hooks/use-ime-input";

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
    const inputRef = useRef<HTMLInputElement>(null);

    const { displayValue, inputProps, flushPendingComposition } =
      useIMEInputForOnChange<HTMLInputElement>({
        value,
        onChange,
        inputRef,
      });

    const handleInputBlur = () => {
      flushPendingComposition();
      onBlur?.();
    };

    const handleInputFocus = () => {
      onFocus?.();
    };

    const setRefs = (node: HTMLInputElement | null) => {
      inputRef.current = node;
      if (typeof ref === "function") {
        ref(node);
      } else if (ref) {
        (ref as React.MutableRefObject<HTMLInputElement | null>).current = node;
      }
    };

    return (
      <Input
        ref={setRefs}
        disabled={disabled}
        type="text"
        {...inputProps}
        className={cn(
          "w-full text-primary",
          editNode ? "input-edit-node" : "",
          disabled ? "disabled-state" : "",
          className,
        )}
        placeholder={placeholder}
        onKeyDown={(event) => handleKeyDown(event, displayValue, "")}
        data-testid={dataTestId}
        onFocus={handleInputFocus}
        onBlur={handleInputBlur}
      />
    );
  },
);

CursorInput.displayName = "CursorInput";

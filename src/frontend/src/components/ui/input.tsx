import * as React from "react";
import { cn } from "../../utils/utils";
import ForwardedIconComponent from "../common/genericIconComponent";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: string;
  inputClassName?: string;
  placeholder?: string;
  endIcon?: string;
  endIconClassName?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      inputClassName,
      icon = "",
      endIcon = "",
      endIconClassName = "",
      type,
      placeholder,
      value,
      onChange,
      ...props
    },
    ref,
  ) => {
    const [isComposing, setIsComposing] = React.useState(false);
    // Normalize non-string values to strings for display
    const normalizeValue = (val: unknown): string => {
      if (val == null) return "";
      return typeof val === "string" ? val : String(val);
    };
    const [internalValue, setInternalValue] = React.useState(
      normalizeValue(value),
    );
    const inputRef = React.useRef<HTMLInputElement>(null);
    const resolvedRef = (ref as React.RefObject<HTMLInputElement>) || inputRef;
    // Ref to prevent duplicate onChange calls during IME composition
    const skipNextOnChangeRef = React.useRef(false);

    // Update internal value when external value changes and not composing
    React.useEffect(() => {
      if (!isComposing && value !== undefined) {
        setInternalValue(normalizeValue(value));
      }
    }, [value, isComposing]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      // Skip this onChange if we just finished composition
      if (skipNextOnChangeRef.current) {
        skipNextOnChangeRef.current = false;
        setInternalValue(e.target.value);
        return;
      }
      setInternalValue(e.target.value);
      // Only call onChange if not composing (IME input in progress)
      if (!isComposing && onChange) {
        onChange(e);
      }
    };

    const handleCompositionStart = () => {
      setIsComposing(true);
    };

    const handleCompositionEnd = (
      e: React.CompositionEvent<HTMLInputElement>,
    ) => {
      setIsComposing(false);
      // Normalize to NFC and trigger onChange after composition ends
      const normalizedValue = e.currentTarget.value.normalize("NFC");
      setInternalValue(normalizedValue);
      if (onChange) {
        // Set flag to skip the next onChange from the input's native change event
        skipNextOnChangeRef.current = true;
        // Create a synthetic event with the normalized value
        const syntheticEvent = {
          ...e,
          target: {
            ...e.target,
            value: normalizedValue,
          },
          currentTarget: {
            ...e.currentTarget,
            value: normalizedValue,
          },
        } as unknown as React.ChangeEvent<HTMLInputElement>;
        onChange(syntheticEvent);
      }
    };

    return (
      <label
        className={cn(
          "relative block h-fit w-full text-sm",
          icon ? className : "",
        )}
      >
        {icon && (
          <ForwardedIconComponent
            name={icon}
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 transform text-muted-foreground"
          />
        )}
        <input
          autoComplete="off"
          type={type}
          placeholder={placeholder}
          className={cn(
            "nopan nodelete nodrag noflow primary-input !placeholder-transparent",
            icon && "pl-9",
            endIcon && "pr-9",
            icon ? inputClassName : className,
          )}
          ref={resolvedRef}
          value={value !== undefined ? internalValue : undefined}
          onChange={handleChange}
          onCompositionStart={handleCompositionStart}
          onCompositionEnd={handleCompositionEnd}
          {...props}
        />
        <span
          className={cn(
            "pointer-events-none absolute top-1/2 -translate-y-1/2 pl-px text-placeholder-foreground",
            icon ? "left-9" : "left-3",
            (value !== undefined ? internalValue : value) && "hidden",
          )}
        >
          {placeholder}
        </span>
        {endIcon && (
          <div data-testid="input-end-icon">
            <ForwardedIconComponent
              name={endIcon}
              className={cn(
                "pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 transform text-muted-foreground",
                endIconClassName,
              )}
            />
          </div>
        )}
      </label>
    );
  },
);
Input.displayName = "Input";

export { Input };

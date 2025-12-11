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
      onChange,
      value,
      defaultValue,
      ...props
    },
    ref,
  ) => {
    const [currentValue, setCurrentValue] = React.useState(
      () => String(defaultValue ?? value ?? "")
    );

    const inputRef = React.useRef<HTMLInputElement>(null);

    const mergedRef = (node: HTMLInputElement) => {
      inputRef.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) (ref as any).current = node;
    };

    const [isComposing, setIsComposing] = React.useState(false);

    const handleCompositionStart = () => setIsComposing(true);

    const handleCompositionEnd = (
      e: React.CompositionEvent<HTMLInputElement>,
    ) => {
      setIsComposing(false);
      const newValue = e.currentTarget.value;
      setCurrentValue(newValue);
      onChange?.(e as any);
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!isComposing) {
        const newValue = e.target.value;
        setCurrentValue(newValue);
        onChange?.(e);
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
          defaultValue={currentValue}
          className={cn(
            "nopan nodelete nodrag noflow primary-input !placeholder-transparent",
            icon && "pl-9",
            endIcon && "pr-9",
            icon ? inputClassName : className,
          )}
          ref={mergedRef}
          onCompositionStart={handleCompositionStart}
          onCompositionEnd={handleCompositionEnd}
          onChange={handleChange}
          {...props}
        />

        <span
          className={cn(
            "pointer-events-none absolute top-1/2 -translate-y-1/2 pl-px text-placeholder-foreground transition-all",
            icon ? "left-9" : "left-3",
            currentValue ? "hidden" : ""
          )}
        >
          {placeholder}
        </span>

        {endIcon && (
          <ForwardedIconComponent
            name={endIcon}
            className={cn(
              "pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 transform text-muted-foreground",
              endIconClassName,
            )}
          />
        )}
      </label>
    );
  },
);

Input.displayName = "Input";

export { Input };

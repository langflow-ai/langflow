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
      onCompositionStart: userOnCompositionStart,
      onCompositionEnd: userOnCompositionEnd,
      value,
      defaultValue,
      ...props
    },
    ref,
  ) => {
    // Internal state
    const [currentValue, setCurrentValue] = React.useState(() =>
      String(defaultValue ?? value ?? ""),
    );

    // Ref merge
    const inputRef = React.useRef<HTMLInputElement>(null);
    const mergedRef = (node: HTMLInputElement) => {
      inputRef.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) (ref as any).current = node;
    };

    // IME composition state
    const [isComposing, setIsComposing] = React.useState(false);

    const handleCompositionStart: React.CompositionEventHandler<
      HTMLInputElement
    > = (e) => {
      setIsComposing(true);
      userOnCompositionStart?.(e);
    };

    const handleCompositionEnd: React.CompositionEventHandler<
      HTMLInputElement
    > = (e) => {
      setIsComposing(false);

      const newValue = e.currentTarget.value;
      setCurrentValue(newValue);

      // 触发一次 onChange，确保中文输入提交
      const syntheticEvent = {
        ...e,
        target: e.currentTarget,
      } as React.ChangeEvent<HTMLInputElement>;
      onChange?.(syntheticEvent);

      userOnCompositionEnd?.(e);
    };

    const handleChange: React.ChangeEventHandler<HTMLInputElement> = (e) => {
      const newValue = e.target.value;
      setCurrentValue(newValue);

      // 仅在非拼音输入阶段触发
      if (!isComposing) {
        onChange?.(e);
      }
    };

    // Sync external value when controlled
    React.useEffect(() => {
      if (value !== undefined && !isComposing) {
        setCurrentValue(String(value));
      }
    }, [value, isComposing]);

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
          value={currentValue}
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
            currentValue ? "hidden" : "",
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

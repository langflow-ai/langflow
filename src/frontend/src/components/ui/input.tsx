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
      value, // 不用于受控模式，只用于初始化
      defaultValue,
      ...props
    },
    ref,
  ) => {
    // -----------------------
    // 非受控 value（解决无法输入 + placeholder 控制）
    // -----------------------
    const [currentValue, setCurrentValue] = React.useState(
      () => String(defaultValue ?? value ?? "")
    );

    const inputRef = React.useRef<HTMLInputElement>(null);

    // 合并 ref
    const mergedRef = (node: HTMLInputElement) => {
      inputRef.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) (ref as any).current = node;
    };

    // -----------------------
    // IME 状态处理
    // -----------------------
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

        {/* 自定义 placeholder：value 为空时显示 */}
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

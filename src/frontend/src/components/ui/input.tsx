import * as React from "react";
import { cn } from "../../utils/utils";
import ForwardedIconComponent from "../common/genericIconComponent";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: string;
  inputClassName?: string;
  placeholder?: string;
  placeholderClassName?: string;
  endIcon?: React.ReactNode;
  /** @deprecated use endIcon with JSX directly */
  endIconClassName?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      inputClassName,
      icon = "",
      endIcon,
      endIconClassName = "",
      type,
      placeholder,
      ...props
    },
    ref,
  ) => {
    // Support legacy string endIcon (icon name) for backwards compatibility
    const resolvedEndIcon =
      typeof endIcon === "string" ? (
        <ForwardedIconComponent
          name={endIcon}
          className={cn(
            "pointer-events-none h-4 w-4 text-muted-foreground",
            endIconClassName,
          )}
        />
      ) : (
        endIcon
      );

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
            resolvedEndIcon && "pr-9",
            icon ? inputClassName : className,
          )}
          ref={ref}
          {...props}
        />
        <span
          className={cn(
            "pointer-events-none absolute top-1/2 -translate-y-1/2 pl-px text-placeholder-foreground",
            icon ? "left-9" : "left-3",
            props.value && "hidden",
          )}
        >
          {placeholder}
        </span>
        {resolvedEndIcon && (
          <div
            data-testid="input-end-icon"
            className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center"
          >
            {resolvedEndIcon}
          </div>
        )}
      </label>
    );
  },
);
Input.displayName = "Input";

export { Input };

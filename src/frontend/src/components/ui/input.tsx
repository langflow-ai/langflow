import * as React from "react";
import { cn } from "../../utils/utils";
import ForwardedIconComponent from "../common/genericIconComponent";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: string;
  inputClassName?: string;
  placeholder?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    { className, inputClassName, icon = "", type, placeholder, ...props },
    ref,
  ) => {
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
            className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 transform"
          />
        )}
        <input
          autoComplete="off"
          type={type}
          placeholder={placeholder}
          className={cn(
            "nopan nodelete nodrag noflow primary-input !placeholder-transparent",
            icon && "pl-9",
            icon ? inputClassName : className,
          )}
          ref={ref}
          {...props}
        />
        <span
          className={cn(
            "text-placeholder-foreground pointer-events-none absolute top-1/2 -translate-y-1/2 pl-px",
            icon ? "left-9" : "left-3",
            props.value && "hidden",
          )}
        >
          {placeholder}
        </span>
      </label>
    );
  },
);
Input.displayName = "Input";

export { Input };

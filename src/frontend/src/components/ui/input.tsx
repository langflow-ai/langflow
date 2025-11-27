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
    ref
  ) => {
    return (
      <div
        className={cn(
          "relative block h-fit w-full text-sm text-primary-font",
          icon ? className : ""
        )}
      >
        {icon && (
          <ForwardedIconComponent
            name={icon}
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 transform text-secondary-font"
          />
        )}
        <input
          autoComplete="off"
          type={type}
          placeholder={placeholder}
          className={cn(
            "nopan nodelete nodrag noflow text-primary-font border hover:border-secondary-border focus:border-secondary-border w-full",
            icon && "pl-9",
            icon ? inputClassName : className,
            type == "search"
              ? "rounded-lg bg-transparent border-accent px-4 py-1.5 pl-9"
              : "py-2 px-3 bg-background-surface rounded-md border-primary-border min-h-[38px] text-primary-font pr-8"
          )}
          ref={ref}
          {...props}
        />
        {/* <span
          className={cn(
            "pointer-events-none absolute top-1/2 -translate-y-1/2 pl-px text-placeholder-foreground",
            icon ? "left-9" : "left-3",
            props.value && "hidden"
          )}
        >
          {placeholder}
        </span> */}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };

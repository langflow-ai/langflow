import * as React from "react";
import { cn } from "../../utils/utils";
import ForwardedIconComponent from "../common/genericIconComponent";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: string;
  inputClassName?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, inputClassName, icon = "", type, ...props }, ref) => {
    if (icon) {
      return (
        <label className={cn("relative block w-full", className)}>
          <ForwardedIconComponent
            name={icon}
            className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 transform"
          />
          <input
            autoComplete="off"
            data-testid=""
            type={type}
            className={cn(
              "nopan nodelete nodrag noflow form-input border-border bg-background placeholder:text-muted-foreground block w-full appearance-none truncate rounded-md px-3 pl-9 text-left text-sm focus:border-black focus:placeholder-transparent focus:ring-zinc-300 disabled:cursor-not-allowed disabled:opacity-50 dark:focus:border-white dark:focus:ring-zinc-800",
              inputClassName,
            )}
            ref={ref}
            {...props}
          />
        </label>
      );
    } else {
      return (
        <input
          data-testid=""
          type={type}
          className={cn(
            "nopan nodelete nodrag noflow primary-input",
            className,
          )}
          ref={ref}
          {...props}
        />
      );
    }
  },
);
Input.displayName = "Input";

export { Input };

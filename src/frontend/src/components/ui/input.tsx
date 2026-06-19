import * as React from "react";
import {
  getSuppressedAutoComplete,
  PASSWORD_MANAGER_IGNORE_PROPS,
} from "@/utils/inputAutofill";
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
  /**
   * Opt back into browser / password-manager autofill. Defaults to false so
   * Langflow inputs (node-config fields, modals) suppress autofill — otherwise
   * the browser can inject saved credentials that autosave then persists,
   * corrupting flows. Only real credential-entry forms (login / signup / admin
   * login) set this to true.
   */
  allowAutofill?: boolean;
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
      autoComplete,
      allowAutofill = false,
      ...props
    },
    ref,
  ) => {
    // Suppress browser/password-manager autofill by default; credential forms
    // opt back in via `allowAutofill`. A caller-provided `autoComplete` always
    // wins. See utils/inputAutofill.ts for the rationale.
    const autofillProps = allowAutofill
      ? autoComplete !== undefined
        ? { autoComplete }
        : {}
      : {
          autoComplete:
            autoComplete ?? getSuppressedAutoComplete(type === "password"),
          ...PASSWORD_MANAGER_IGNORE_PROPS,
        };

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
          {...autofillProps}
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

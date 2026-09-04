"use client";

import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import * as React from "react";
import { cn } from "../../utils/utils";
import IconComponent from "../common/genericIconComponent";

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      "peer h-4 w-4 shrink-0 rounded-sm border border-muted-foreground ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
      className,
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator
      className={cn("flex items-center justify-center text-current")}
    >
      <IconComponent name="Check" className="h-4 w-4 stroke-2" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

const CheckBoxDiv = ({
  className = "",
  checked,
  presentational = false,
  "aria-label": ariaLabel,
}: {
  className?: string;
  checked?: boolean;
  // When true, render a purely visual indicator (hidden from assistive tech).
  // Use this when the wrapping element already owns the checkbox/toggle
  // semantics (e.g. a toggle button), so we don't nest an interactive
  // "checkbox" role inside another interactive role (IBM aria_descendant_valid).
  presentational?: boolean;
  "aria-label"?: string;
}) => (
  // Read-only state indicator: activation is owned by the wrapping
  // trigger/tooltip, so it exposes checkbox role + state but stays
  // non-focusable itself.
  <div
    role={presentational ? undefined : "checkbox"}
    aria-hidden={presentational ? "true" : undefined}
    aria-label={presentational ? undefined : ariaLabel}
    aria-checked={presentational ? undefined : Boolean(checked)}
    aria-readonly={presentational ? undefined : "true"}
    className={cn(
      className,
      "peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background disabled:cursor-not-allowed disabled:opacity-50",
      checked ? "bg-primary text-primary-foreground" : "",
    )}
  >
    {checked && (
      <div className="flex items-center justify-center text-current">
        <IconComponent name="Check" className="h-4 w-4" />
      </div>
    )}
  </div>
);

export { Checkbox, CheckBoxDiv };

"use client";

import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import * as React from "react";
import { cn } from "../../utils/utils";
import IconComponent from "../common/genericIconComponent";

interface CheckboxProps
  extends Omit<
    React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>,
    "checked"
  > {
  checked?: boolean | "indeterminate";
  indeterminate?: boolean;
}

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  CheckboxProps
>(({ className, checked, indeterminate, ...props }, ref) => {
  const isIndeterminate = indeterminate || checked === "indeterminate";
  const isChecked = checked === true;

  return (
    <CheckboxPrimitive.Root
      ref={ref}
      className={cn(
        "peer h-4 w-4 shrink-0 rounded-sm border border-muted-foreground ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        (isChecked || isIndeterminate) &&
          "border-primary bg-primary text-primary-foreground",
        className,
      )}
      checked={isChecked || isIndeterminate}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        className={cn("flex items-center justify-center text-current")}
      >
        {isIndeterminate ? (
          <div className="h-[1.5px] w-2 rounded-sm bg-current" />
        ) : (
          <IconComponent name="Check" className="h-4 w-4 stroke-1" />
        )}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
});
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

const CheckBoxDiv = ({
  className = "",
  checked,
  indeterminate,
}: {
  className?: string;
  checked?: boolean;
  indeterminate?: boolean;
}) => (
  <div
    className={cn(
      className,
      "peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
      checked || indeterminate ? "bg-primary text-primary-foreground" : "",
    )}
  >
    {(checked || indeterminate) && (
      <div className="flex items-center justify-center text-current">
        <IconComponent
          name={indeterminate ? "Minus" : "Check"}
          className="h-4 w-4"
        />
      </div>
    )}
  </div>
);

export { Checkbox, CheckBoxDiv };

import type { ReactNode } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

interface RadioSelectItemProps {
  selected: boolean;
  onChange: () => void;
  name: string;
  value: string;
  children: ReactNode;
  "data-testid"?: string;
  className?: string;
}

interface CheckboxSelectItemProps {
  checked: boolean;
  onChange: () => void;
  value: string;
  children: ReactNode;
  "data-testid"?: string;
}

export function CheckboxSelectItem({
  checked,
  onChange,
  value,
  children,
  "data-testid": testId,
}: CheckboxSelectItemProps) {
  return (
    <label
      data-testid={testId}
      className={cn(
        "relative flex w-full cursor-pointer items-center gap-4 overflow-hidden rounded-xl border bg-muted p-3 text-left transition-colors",
        checked ? "border-primary" : "border-transparent hover:border-border",
      )}
    >
      <input
        type="checkbox"
        value={value}
        checked={checked}
        onChange={onChange}
        className="sr-only"
      />
      <span
        className={cn(
          "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded",
          checked
            ? "bg-primary text-primary-foreground"
            : "border border-muted-foreground bg-background",
        )}
      >
        {checked && (
          <ForwardedIconComponent name="Check" className="h-3.5 w-3.5" />
        )}
      </span>
      {children}
    </label>
  );
}

export function RadioSelectItem({
  selected,
  onChange,
  name,
  value,
  children,
  "data-testid": testId,
  className,
}: RadioSelectItemProps) {
  return (
    <label
      data-testid={testId}
      className={cn(
        "relative flex w-full cursor-pointer items-center gap-4 overflow-hidden rounded-xl border bg-muted p-3 text-left transition-colors",
        selected ? "border-primary" : "border-transparent hover:border-border",
        className,
      )}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={selected}
        onChange={onChange}
        className="sr-only"
      />
      <span
        className={cn(
          "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2",
          selected ? "border-primary" : "border-muted-foreground bg-background",
        )}
      >
        {selected && <span className="h-2.5 w-2.5 rounded-full bg-primary" />}
      </span>
      {children}
    </label>
  );
}

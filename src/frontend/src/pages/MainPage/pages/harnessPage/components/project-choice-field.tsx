import type { Ref } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/utils/utils";

export function ProjectChoiceField({
  name,
  label,
  options,
  value,
  disabled = false,
  placeholder,
  className,
  onChange,
  id,
  triggerRef,
}: {
  name: string;
  label: string;
  options: Record<string, string>;
  value: string;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  onChange: (value: string) => void;
  id?: string;
  triggerRef?: Ref<HTMLButtonElement>;
}) {
  return (
    <Select value={value} disabled={disabled} onValueChange={onChange}>
      <SelectTrigger
        id={id}
        ref={triggerRef}
        aria-label={label}
        data-testid={`harness-choice-${name}`}
        className={cn(
          "w-full min-w-0 text-left [&>span]:truncate [&>svg]:shrink-0",
          className,
        )}
      >
        <SelectValue placeholder={placeholder}>{options[value]}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {Object.entries(options).map(([key, text]) => (
          <SelectItem key={key} value={key}>
            {text}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

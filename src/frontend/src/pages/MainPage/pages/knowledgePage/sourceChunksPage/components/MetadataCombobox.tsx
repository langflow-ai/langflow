import { useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/utils/utils";

export interface MetadataComboboxProps {
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder: string;
  emptyMessage: string;
  testId: string;
  disabled?: boolean;
  onEnter?: () => void;
}

/**
 * Searchable combobox built on Popover + Command (cmdk). Matches the
 * shadcn `Select` visual so it sits naturally beside other dropdowns,
 * but also accepts a free-typed value via a "Use \"foo\"" fallback item.
 *
 * Presentational: holds only its own open/query state. All filter-level
 * state (selected key/value, validation, submit) lives in the parent.
 */
export const MetadataCombobox = ({
  value,
  onChange,
  options,
  placeholder,
  emptyMessage,
  testId,
  disabled,
  onEnter,
}: MetadataComboboxProps) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const trimmedQuery = query.trim();
  const normalizedOptions = useMemo(
    () => options.map((option) => option.toLowerCase()),
    [options],
  );
  const showCustom =
    trimmedQuery.length > 0 &&
    !normalizedOptions.includes(trimmedQuery.toLowerCase());

  const commit = (next: string) => {
    onChange(next);
    setQuery("");
    setOpen(false);
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setQuery("");
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className="w-full justify-between font-normal"
          data-testid={testId}
        >
          <span
            className={cn(
              "truncate text-left",
              value ? "text-foreground" : "text-muted-foreground",
            )}
          >
            {value || placeholder}
          </span>
          <ForwardedIconComponent
            name="ChevronDown"
            className="ml-2 h-4 w-4 shrink-0 opacity-50"
          />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[--radix-popover-trigger-width] p-0"
      >
        <Command shouldFilter>
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder={placeholder}
            data-testid={`${testId}-input`}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !showCustom && options.length === 0) {
                e.preventDefault();
                if (trimmedQuery) commit(trimmedQuery);
                else onEnter?.();
              }
            }}
          />
          <CommandList>
            <CommandEmpty>{emptyMessage}</CommandEmpty>
            {options.length > 0 && (
              <CommandGroup>
                {options.map((option) => (
                  <CommandItem
                    key={option}
                    value={option}
                    onSelect={() => commit(option)}
                    data-testid={`${testId}-option-${option}`}
                  >
                    <ForwardedIconComponent
                      name="Check"
                      className={cn(
                        "mr-2 h-4 w-4",
                        value === option ? "opacity-100" : "opacity-0",
                      )}
                    />
                    {option}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {showCustom && (
              <CommandGroup>
                <CommandItem
                  value={`__custom__${trimmedQuery}`}
                  onSelect={() => commit(trimmedQuery)}
                  data-testid={`${testId}-custom`}
                >
                  <ForwardedIconComponent
                    name="Plus"
                    className="mr-2 h-4 w-4"
                  />
                  Use “{trimmedQuery}”
                </CommandItem>
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};

export default MetadataCombobox;

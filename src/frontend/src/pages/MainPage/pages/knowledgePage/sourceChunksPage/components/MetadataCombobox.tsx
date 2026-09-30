import { useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
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
  /** Accessible name for the combobox trigger (WCAG 4.1.2). */
  "aria-label"?: string;
}

export const MetadataCombobox = ({
  value,
  onChange,
  options,
  placeholder,
  emptyMessage,
  testId,
  disabled,
  onEnter,
  "aria-label": ariaLabel,
}: MetadataComboboxProps) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const trimmedQuery = query.trim();
  const normalizedQuery = trimmedQuery.toLowerCase();
  const filteredOptions = useMemo(() => {
    if (!normalizedQuery) return options;
    return options.filter((option) =>
      option.toLowerCase().includes(normalizedQuery),
    );
  }, [options, normalizedQuery]);
  const showCustom =
    trimmedQuery.length > 0 &&
    !options.some((option) => option.toLowerCase() === normalizedQuery);

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
          aria-label={ariaLabel ?? placeholder}
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
        <Command shouldFilter={false} label={placeholder}>
          <div className="flex items-center border-b px-2.5">
            <ForwardedIconComponent
              name="search"
              className="mr-2 h-4 w-4 shrink-0 opacity-50"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={placeholder}
              data-testid={`${testId}-input`}
              autoComplete="off"
              className="flex h-9 w-full rounded-md bg-transparent py-3 text-[13px] outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !showCustom && options.length === 0) {
                  e.preventDefault();
                  if (trimmedQuery) commit(trimmedQuery);
                  else onEnter?.();
                }
              }}
            />
          </div>
          <CommandList>
            <CommandEmpty>{emptyMessage}</CommandEmpty>
            {filteredOptions.length > 0 && (
              <CommandGroup>
                {filteredOptions.map((option) => (
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

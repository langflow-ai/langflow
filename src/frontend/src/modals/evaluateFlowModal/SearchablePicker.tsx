import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/utils/utils";

export interface PickerOption {
  id: string;
  label: string;
  disabled?: boolean;
}

interface SearchablePickerProps {
  id: string;
  options: PickerOption[];
  value: string;
  onChange: (id: string) => void;
  placeholder: string;
  searchPlaceholder: string;
  emptyText: string;
  testId: string;
  disabled?: boolean;
}

/**
 * A searchable list as wide as its field, opened under it: users can have dozens of flows or datasets,
 * too many for a plain select.
 */
export default function SearchablePicker({
  id,
  options,
  value,
  onChange,
  placeholder,
  searchPlaceholder,
  emptyText,
  testId,
  disabled = false,
}: SearchablePickerProps) {
  const [open, setOpen] = useState(false);
  const selected = options.find((option) => option.id === value);
  const listId = `${id}-list`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="primary"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          disabled={disabled}
          data-testid={testId}
          className="h-9 w-full justify-between px-4 font-normal focus-visible:ring-1 focus-visible:ring-offset-0"
        >
          <span
            className={cn("truncate", !selected && "text-muted-foreground")}
          >
            {selected?.label ?? placeholder}
          </span>
          <ForwardedIconComponent
            name="ChevronsUpDown"
            className="h-4 w-4 shrink-0 opacity-60"
          />
        </Button>
      </PopoverTrigger>
      <PopoverContentWithoutPortal
        align="start"
        className="w-[--radix-popover-trigger-width] p-0"
      >
        <Command
          // Plain substring match: fuzzy matching surfaces unrelated names.
          filter={(itemValue, search) =>
            itemValue.toLowerCase().includes(search.trim().toLowerCase())
              ? 1
              : 0
          }
        >
          <CommandInput
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            data-testid={`${testId}-search`}
          />
          <CommandList id={listId} className="max-h-64">
            <CommandEmpty>{emptyText}</CommandEmpty>
            {options.map((option) => (
              <CommandItem
                key={option.id}
                value={`${option.label} ${option.id}`}
                disabled={option.disabled}
                onSelect={() => {
                  onChange(option.id);
                  setOpen(false);
                }}
                className="flex items-center justify-between gap-2"
              >
                <span className="truncate" title={option.label}>
                  {option.label}
                </span>
                {option.id === value && (
                  <ForwardedIconComponent
                    name="Check"
                    aria-hidden="true"
                    className="h-4 w-4 shrink-0"
                  />
                )}
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContentWithoutPortal>
    </Popover>
  );
}

"use client";

import * as React from "react";
import { Check, ChevronDown, X } from "lucide-react";
import { cn } from "../../utils/utils";
import { Badge } from "./badge";
import { Button } from "./button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "./command";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";

export interface MultiSelectProps {
  options:
    | readonly string[]
    | string[]
    | readonly { title: string; id: string }[]
    | { title: string; id: string }[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  className?: string;
}

export function MultiSelect({
  options,
  selected,
  onChange,
  placeholder = "Select items...",
  className,
}: MultiSelectProps) {
  const [open, setOpen] = React.useState(false);

  // Helper function to check if options are objects
  const isObjectOptions = (
    opts: typeof options
  ): opts is
    | readonly { title: string; id: string }[]
    | { title: string; id: string }[] => {
    return (
      opts.length > 0 &&
      typeof opts[0] === "object" &&
      "id" in opts[0] &&
      "title" in opts[0]
    );
  };

  // Helper to get value (id or string)
  const getValue = (option: string | { title: string; id: string }): string => {
    return typeof option === "string" ? option : option.id;
  };

  // Helper to get display text (title or string)
  const getDisplayText = (value: string): string => {
    if (isObjectOptions(options)) {
      const option = options.find((opt) => opt.id === value);
      return option ? option.title : value;
    }
    return value;
  };

  const handleUnselect = (item: string) => {
    onChange(selected.filter((s) => s !== item));
  };

  const handleSelect = (item: string) => {
    if (selected.includes(item)) {
      onChange(selected.filter((s) => s !== item));
    } else {
      onChange([...selected, item]);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            "w-full justify-between min-h-[38px] !py-1 h-auto rounded-md border-primary-border hover:border-secondary-border focus:border-secondary-border hover:bg-transparent",
            className
          )}
        >
          <div className="flex flex-wrap gap-1 flex-1">
            {selected.length > 0 ? (
              selected.map((item) => (
                <Badge key={item} variant="secondary">
                  {getDisplayText(item)}
                  <button
                    className="rounded-full"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        handleUnselect(item);
                      }
                    }}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                    }}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleUnselect(item);
                    }}
                  >
                    <X className="ml-1.5 text-white opacity-75" />
                  </button>
                </Badge>
              ))
            ) : (
              <span className="text-secondary-font">{placeholder}</span>
            )}
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="!w-full p-0" align="start">
        <Command>
          <CommandInput placeholder="Search..." />
          <CommandList>
            <CommandEmpty>No results found.</CommandEmpty>
            <CommandGroup>
              {options.map((option) => {
                const value = getValue(option);
                const displayText =
                  typeof option === "string" ? option : option.title;
                return (
                  <CommandItem
                    key={value}
                    onSelect={() => handleSelect(value)}
                    className={cn(
                      selected.includes(value)
                        ? "bg-accent"
                        : "hover:bg-accent-light"
                    )}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        selected.includes(value)
                          ? "text-menu opacity-100"
                          : "opacity-0"
                      )}
                    />
                    {displayText}
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

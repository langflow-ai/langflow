"use client";

import { VariantProps, cva } from "class-variance-authority";
import isEqual from "lodash.isequal";
import { CheckIcon, ChevronDown, XCircle, XIcon } from "lucide-react";
import { forwardRef, useEffect, useRef, useState } from "react";

import useMergeRefs, {
  isRefObject,
} from "../../CustomNodes/hooks/use-merge-refs";
import { cn } from "../../utils/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "../ui/command";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "../ui/popover";
import { Separator } from "../ui/separator";

const MultiselectBadgeWrapper = ({
  value,
  variant,
  className,
  onDelete,
}: {
  value: MultiselectValue;
  variant: MultiselectProps<MultiselectValue>["variant"];
  className: MultiselectProps<MultiselectValue>["className"];
  onDelete: ({ value }: { value: MultiselectValue }) => void;
}) => {
  const badgeRef = useRef<HTMLDivElement>(null);

  const handleDelete = (
    event: React.MouseEvent<HTMLDivElement, MouseEvent>,
  ) => {
    event.stopPropagation();
    onDelete({ value });
  };

  return (
    <Badge
      className={cn(
        "overflow-hidden rounded-sm p-0 font-normal",
        multiselectVariants({ variant, className }),
      )}
    >
      <div id="content" className="p-1 pr-0" ref={badgeRef}>
        {value?.label}
      </div>
      <div id="spacer" className="p-1" />
      <div
        id="delete"
        className="flex items-center justify-center px-1 hover:bg-red-300/80"
        style={{
          minHeight: `${badgeRef?.current?.clientHeight}px`,
        }}
        onClick={handleDelete}
      >
        <XCircle
          className="h-4 min-h-4 w-4 min-w-4 cursor-pointer"
          style={{
            minHeight: `${badgeRef?.current?.clientHeight}px`,
          }}
        />
      </div>
    </Badge>
  );
};

const multiselectVariants = cva("m-1 ", {
  variants: {
    variant: {
      default:
        "border-foreground/10 text-foreground bg-card hover:bg-card/80 whitespace-normal",
      secondary:
        "border-foreground/10 bg-secondary text-secondary-foreground hover:bg-secondary/80 whitespace-normal",
      destructive:
        "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80 whitespace-normal",
      inverted: "inverted",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

type MultiselectValue = {
  label: string;
  value: string;
};

interface MultiselectProps<T>
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "value">,
    VariantProps<typeof multiselectVariants> {
  options: T[];
  onValueChange: (value: T[]) => void;
  placeholder?: string;
  asChild?: boolean;
  className?: string;
  editNode?: boolean;
  values?: T[];
}

export const Multiselect = forwardRef<
  HTMLButtonElement,
  MultiselectProps<MultiselectValue>
>(
  (
    {
      options = [],
      onValueChange,
      variant,
      placeholder = "Select options",
      asChild = false,
      className,
      editNode = false,
      values,
      ...props
    },
    ref,
  ) => {
    // if elements in values are strings, create the multiselectValue object
    // otherwise, use the values as is
    const value = values?.map((v) =>
      typeof v === "string" ? { label: v, value: v } : v,
    );

    const [selectedValues, setSelectedValues] = useState<MultiselectValue[]>(
      value || [],
    );
    const [isPopoverOpen, setIsPopoverOpen] = useState(false);

    const combinedRef = useMergeRefs<HTMLButtonElement>(ref);
    useEffect(() => {
      if (!!value && value?.length > 0 && !isEqual(selectedValues, value)) {
        setSelectedValues(value);
      }
    }, [value, selectedValues]);

    const handleInputKeyDown = (
      event: React.KeyboardEvent<HTMLInputElement>,
    ) => {
      if (event.key === "Enter") {
        setIsPopoverOpen(true);
      } else if (event.key === "Backspace" && !event.currentTarget.value) {
        const newSelectedValues = [...selectedValues];
        newSelectedValues.pop();
        setSelectedValues(newSelectedValues);
        onValueChange(newSelectedValues);
      }
    };

    const toggleOption = ({ value }: { value: MultiselectValue }) => {
      const newSelectedValues = !!selectedValues.find(
        (v) => v.value === value.value,
      )
        ? selectedValues.filter((v) => v.value !== value.value)
        : [...selectedValues, value];
      setSelectedValues(newSelectedValues);
      onValueChange(newSelectedValues);
    };

    const handleClear = () => {
      setSelectedValues([]);
      onValueChange([]);
    };

    const handleTogglePopover = () => {
      setIsPopoverOpen((prev) => !prev);
    };

    const PopoverContentMultiselect = editNode
      ? PopoverContent
      : PopoverContentWithoutPortal;

    const popoverContentMultiselectMinWidth = isRefObject(combinedRef)
      ? `${combinedRef?.current?.clientWidth}px`
      : "200px";

    return (
      <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
        <PopoverTrigger asChild>
          <Button
            ref={combinedRef}
            {...props}
            onClick={handleTogglePopover}
            variant="primary"
            size="xs"
            role="combobox"
            className={cn(
              editNode
                ? "multiselect-component-outline"
                : "multiselect-component-false-outline",
              "w-full justify-between font-normal",
              editNode ? "input-edit-node" : "py-2",
              className,
            )}
          >
            {selectedValues?.length > 0 ? (
              <div className="flex w-full items-center justify-between">
                <div className="flex flex-wrap items-center">
                  {selectedValues?.map((selectedValue) => {
                    return (
                      <MultiselectBadgeWrapper
                        value={selectedValue}
                        onDelete={toggleOption}
                        variant={variant}
                        className={className}
                        key={selectedValue.value}
                      />
                    );
                  })}
                </div>
                <div className="flex items-center justify-between">
                  <XIcon
                    className="mx-2 cursor-pointer rounded-md text-sm text-muted-foreground ring-offset-background transition-colors hover:bg-secondary-foreground/5 hover:text-accent-foreground hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 dark:hover:bg-background/10"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleClear();
                    }}
                  />
                  <Separator
                    orientation="vertical"
                    className="flex h-full min-h-6"
                  />
                  <ChevronDown className="mx-2 h-4 cursor-pointer rounded-md text-sm text-muted-foreground ring-offset-background transition-colors hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50" />
                </div>
              </div>
            ) : (
              <div className="mx-auto flex w-full items-center justify-between">
                <span className="mx-3 text-sm text-muted-foreground">
                  {placeholder}
                </span>
                <ChevronDown className="mx-2 h-4 cursor-pointer text-muted-foreground hover:text-accent-foreground" />
              </div>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContentMultiselect
          id="multiselect-content"
          side="bottom"
          className={cn(
            `nocopy nowheel nopan nodelete nodrag noundo w-full p-0`,
          )}
          style={{
            minWidth: popoverContentMultiselectMinWidth,
            maxWidth: popoverContentMultiselectMinWidth,
          }}
          align="start"
          onEscapeKeyDown={() => setIsPopoverOpen(false)}
        >
          <Command>
            <CommandInput
              placeholder="Search"
              onKeyDown={handleInputKeyDown}
              className="h-9"
            />
            <CommandList>
              <CommandEmpty>No results found.</CommandEmpty>
              <CommandGroup>
                {value?.map((option) => {
                  const isSelected = !!selectedValues.find(
                    (sv) => sv.value === option.value,
                  );
                  return (
                    <CommandItem
                      key={option.value}
                      onSelect={() => toggleOption({ value: option })}
                      className="cursor-pointer"
                    >
                      <div
                        className={cn(
                          "mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
                          isSelected
                            ? "bg-primary text-primary-foreground"
                            : "opacity-50 [&_svg]:invisible",
                        )}
                      >
                        <CheckIcon className="h-4 w-4" />
                      </div>
                      <span>{option.label}</span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
              <CommandSeparator />
              <CommandGroup>
                <div className="flex items-center justify-between">
                  {selectedValues?.length > 0 && (
                    <>
                      <CommandItem
                        onSelect={handleClear}
                        className="flex-1 cursor-pointer justify-center"
                      >
                        Clear
                      </CommandItem>
                      <Separator
                        orientation="vertical"
                        className="flex h-full min-h-6"
                      />
                    </>
                  )}
                  <CommandSeparator />
                  <CommandItem
                    onSelect={() => setIsPopoverOpen(false)}
                    className="flex-1 cursor-pointer justify-center"
                  >
                    Close
                  </CommandItem>
                </div>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContentMultiselect>
      </Popover>
    );
  },
);

Multiselect.displayName = "Multiselect";

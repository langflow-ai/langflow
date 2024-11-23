import { PopoverAnchor } from "@radix-ui/react-popover";
import Fuse from "fuse.js";
import { cloneDeep } from "lodash";
import { ChangeEvent, useEffect, useRef, useState } from "react";
import { DropDownComponent } from "../../../types/components";
import { cn, formatPlaceholderName } from "../../../utils/utils";
import { default as ForwardedIconComponent } from "../../common/genericIconComponent";
import ShadTooltip from "../../common/shadTooltipComponent";
import { Button } from "../../ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from "../../ui/command";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "../../ui/popover";

export default function Dropdown({
  disabled,
  isLoading,
  value,
  options,
  combobox,
  onSelect,
  editNode = false,
  id = "",
  children,
  name,
}: DropDownComponent): JSX.Element {
  const placeholderName = name
    ? formatPlaceholderName(name)
    : "Choose an option...";

  const [open, setOpen] = useState(children ? true : false);

  const refButton = useRef<HTMLButtonElement>(null);

  const PopoverContentDropdown =
    children || editNode ? PopoverContent : PopoverContentWithoutPortal;

  const [customValue, setCustomValue] = useState("");
  const [filteredOptions, setFilteredOptions] = useState(options);

  const fuse = new Fuse(options, { keys: ["name", "value"] });

  const searchRoleByTerm = async (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    const searchValues = fuse.search(value);
    const filtered = searchValues.map((search) => search.item);
    if (!filtered.includes(value) && combobox && value) filtered.push(value);
    setFilteredOptions(value ? filtered : options);
    setCustomValue(value);
  };

  useEffect(() => {
    if (disabled && value !== "") {
      onSelect("", undefined, true);
    }
  }, [disabled]);

  useEffect(() => {
    if (open) {
      const filtered = cloneDeep(options);
      if (customValue === value && value && combobox) {
        filtered.push(customValue);
      }
      setFilteredOptions(filtered);
    }
  }, [open]);

  const renderTriggerButton = () => (
    <PopoverTrigger asChild>
      <Button
        disabled={disabled}
        variant="primary"
        size="xs"
        role="combobox"
        ref={refButton}
        aria-expanded={open}
        data-testid={id}
        className={cn(
          editNode
            ? "dropdown-component-outline input-edit-node"
            : "dropdown-component-false-outline py-2",
          "w-full justify-between font-normal",
        )}
      >
        <span className="truncate" data-testid={`value-dropdown-${id}`}>
          {value &&
          value !== "" &&
          filteredOptions.find((option) => option === value)
            ? filteredOptions.find((option) => option === value)
            : placeholderName}
        </span>
        <ForwardedIconComponent
          name="ChevronsUpDown"
          className={cn(
            "ml-2 h-4 w-4 shrink-0 text-foreground",
            disabled
              ? "hover:text-placeholder-foreground"
              : "hover:text-foreground",
          )}
        />
      </Button>
    </PopoverTrigger>
  );

  const renderSearchInput = () => (
    <div className="flex items-center border-b px-3">
      <ForwardedIconComponent
        name="search"
        className="mr-2 h-4 w-4 shrink-0 opacity-50"
      />
      <input
        onChange={searchRoleByTerm}
        placeholder="Search options..."
        className="flex h-9 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
        autoComplete="off"
      />
    </div>
  );

  const renderOptionsList = () => (
    <CommandList>
      <CommandEmpty>No values found.</CommandEmpty>
      <CommandGroup defaultChecked={false}>
        {filteredOptions?.map((option, index) => (
          <ShadTooltip key={index} delayDuration={700} content={option}>
            <div>
              <CommandItem
                value={option}
                onSelect={(currentValue) => {
                  onSelect(currentValue);
                  setOpen(false);
                }}
                className="items-center overflow-hidden truncate"
                data-testid={`${option}-${index}-option`}
              >
                {customValue === option && (
                  <span className="text-muted-foreground">Text:&nbsp;</span>
                )}
                <span className="truncate">{option}</span>
                <ForwardedIconComponent
                  name="Check"
                  className={cn(
                    "ml-auto h-4 w-4 shrink-0 text-primary",
                    value === option ? "opacity-100" : "opacity-0",
                  )}
                />
              </CommandItem>
            </div>
          </ShadTooltip>
        ))}
      </CommandGroup>
    </CommandList>
  );

  const renderPopoverContent = () => (
    <PopoverContentDropdown
      side="bottom"
      avoidCollisions={!!children}
      className="noflow nowheel nopan nodelete nodrag p-0"
      style={
        children ? {} : { minWidth: refButton?.current?.clientWidth ?? "200px" }
      }
    >
      <Command>
        {renderSearchInput()}
        {renderOptionsList()}
      </Command>
    </PopoverContentDropdown>
  );

  if (Object.keys(options).length === 0 && !combobox) {
    return isLoading ? (
      <div>
        <span className="text-sm italic">Loading...</span>
      </div>
    ) : (
      <div>
        <span className="text-sm italic">
          No parameters are available for display.
        </span>
      </div>
    );
  }

  return (
    <Popover open={open} onOpenChange={children ? () => {} : setOpen}>
      {children ? (
        <PopoverAnchor>{children}</PopoverAnchor>
      ) : (
        renderTriggerButton()
      )}
      {renderPopoverContent()}
    </Popover>
  );
}

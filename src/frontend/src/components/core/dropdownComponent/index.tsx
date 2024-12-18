import NodeDialog from "@/CustomNodes/GenericNode/components/NodeDialogComponent";
import { PopoverAnchor } from "@radix-ui/react-popover";
import Fuse from "fuse.js";
import { cloneDeep } from "lodash";
import { ChangeEvent, useEffect, useRef, useState } from "react";
import { DropDownComponent } from "../../../types/components";
import { cn, formatName, formatPlaceholderName } from "../../../utils/utils";
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
  hasDialog,
}: DropDownComponent): JSX.Element {
  const placeholderName = name
    ? formatPlaceholderName(name)
    : "Choose an option...";

  const { firstWord } = formatName(name);

  const [open, setOpen] = useState(children ? true : false);
  const [openDialog, setOpenDialog] = useState(false);

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
        <span
          className="flex items-center gap-2 truncate"
          data-testid={`value-dropdown-${id}`}
        >
          {true && <ForwardedIconComponent name={""} className="h-4 w-4" />}

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

  const renderCreateOptionDialog = () => (
    <div className="flex items-center justify-between gap-2 truncate pb-1 pl-2 text-xs font-semibold text-muted-foreground">
      {`${firstWord}${filteredOptions.length > 1 ? "s" : ""} (${filteredOptions.length})`}
      <ShadTooltip delayDuration={700} content={`New ${firstWord}`} side="left">
        <Button
          variant="ghost"
          size="iconMd"
          onClick={() => setOpenDialog(true)}
        >
          <ForwardedIconComponent name="Plus" className="text-primary" />
        </Button>
      </ShadTooltip>
      <NodeDialog
        open={openDialog}
        onClose={() => setOpenDialog(false)}
        content={<div>Content</div>}
      />
    </div>
  );

  const renderIconOptionsList = () => (
    <CommandList>
      <CommandEmpty>No values found.</CommandEmpty>
      <CommandGroup defaultChecked={false}>
        {renderCreateOptionDialog()}
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
                <div className="flex items-center gap-2">
                  <ForwardedIconComponent
                    name={option?.icon}
                    className={cn("h-4 w-4 shrink-0 text-primary")}
                  />
                  <div className="flex flex-col">
                    <span className="truncate">{option}</span>
                    <span className="flex items-center gap-1 truncate pt-1 text-muted-foreground">
                      {["GPT-4o", "510 records"].map((value, i) => (
                        <>
                          {i > 0 && (
                            <ForwardedIconComponent
                              name="Circle"
                              className="h-1 w-1 fill-muted-foreground"
                            />
                          )}
                          <span className="truncate text-xs">{value}</span>
                        </>
                      ))}
                    </span>
                  </div>
                </div>
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
        {hasDialog ? renderIconOptionsList() : renderOptionsList()}
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

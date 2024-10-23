import { Badge } from "@/components/ui/badge";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
} from "@/components/ui/popover";
import { cn } from "@/utils/utils";
import { PopoverAnchor } from "@radix-ui/react-popover";
import { X } from "lucide-react";
import React from "react";

const CustomInputPopover = ({
  id,
  refInput,
  onInputLostFocus,
  selectedOption,
  setSelectedOption,
  selectedOptions,
  setSelectedOptions,
  value,
  disabled,
  setShowOptions,
  required,
  password,
  pwdVisible,
  editNode,
  placeholder,
  onChange,
  blurOnEnter,
  options,
  optionsPlaceholder,
  optionsButton,
  handleKeyDown,
  showOptions,
  nodeStyle,
}) => {
  const PopoverContentInput = editNode
    ? PopoverContent
    : PopoverContentWithoutPortal;

  const handleRemoveOption = (optionToRemove, e) => {
    e.stopPropagation(); // Prevent the popover from opening when removing badges
    if (setSelectedOptions) {
      setSelectedOptions(
        selectedOptions.filter((option) => option !== optionToRemove),
      );
    } else if (setSelectedOption) {
      setSelectedOption("");
    }
  };

  return (
    <Popover modal open={showOptions} onOpenChange={setShowOptions}>
      <PopoverAnchor>
        <div
          className={cn(
            "primary-input border-1 flex h-full min-h-[43px] flex-wrap items-center px-3 placeholder:text-placeholder",
            editNode && "min-h-7 p-0",
            editNode && disabled && "min-h-5 border-muted p-0",
            disabled && "bg-secondary text-muted",
          )}
          onClick={() => !disabled && setShowOptions(true)}
        >
          {selectedOptions?.length > 0 ? (
            selectedOptions.map((option) => (
              <Badge
                key={option}
                variant="secondary"
                className="m-[1px] flex items-center gap-1 truncate px-1"
              >
                <div className="truncate">{option}</div>
                <X
                  className="h-3 w-3 cursor-pointer hover:text-destructive"
                  onClick={(e) => handleRemoveOption(option, e)}
                />
              </Badge>
            ))
          ) : selectedOption?.length > 0 ? (
            <Badge
              variant="secondary"
              className={cn(
                "flex items-center gap-1 truncate",
                nodeStyle &&
                  "rounded-[3px] bg-emerald-100 px-1 font-jetbrains text-emerald-700 hover:bg-emerald-200",
              )}
            >
              <div className="max-w-36 truncate">{selectedOption}</div>
              <X
                className="h-3 w-3 cursor-pointer hover:text-destructive"
                onClick={(e) => handleRemoveOption(selectedOption, e)}
              />
            </Badge>
          ) : null}

          {!selectedOption && (
            <input
              autoFocus
              id={id}
              ref={refInput}
              type={!pwdVisible && password ? "password" : "text"}
              onBlur={onInputLostFocus}
              value={value || ""}
              disabled={disabled}
              required={required}
              className={cn(
                "popover-input",
                editNode && "px-3",
                editNode && disabled && "h-fit w-fit",
                disabled &&
                  "disabled:text-muted disabled:opacity-100 placeholder:disabled:text-muted-foreground",
              )}
              placeholder={
                selectedOptions?.length > 0 || selectedOption ? "" : placeholder
              }
              onChange={(e) => onChange?.(e.target.value)}
              onKeyDown={(e) => {
                handleKeyDown?.(e);
                if (blurOnEnter && e.key === "Enter") refInput.current?.blur();
              }}
              data-testid={editNode ? id + "-edit" : id}
            />
          )}
        </div>
      </PopoverAnchor>
      <PopoverContentInput
        className="noflow nowheel nopan nodelete nodrag p-0"
        style={{ minWidth: refInput?.current?.clientWidth ?? "200px" }}
        side="bottom"
        align="start"
      >
        <Command
          filter={(value, search) => {
            if (
              value.toLowerCase().includes(search.toLowerCase()) ||
              value.includes("doNotFilter-")
            )
              return 1;
            return 0;
          }}
        >
          <CommandInput placeholder={optionsPlaceholder} />
          <CommandList>
            <CommandGroup>
              {options.map((option, id) => (
                <CommandItem
                  key={option + id}
                  value={option}
                  onSelect={(currentValue) => {
                    if (setSelectedOption) {
                      setSelectedOption(
                        currentValue === selectedOption ? "" : currentValue,
                      );
                    }
                    if (setSelectedOptions) {
                      setSelectedOptions(
                        selectedOptions?.includes(currentValue)
                          ? selectedOptions.filter(
                              (item) => item !== currentValue,
                            )
                          : [...(selectedOptions || []), currentValue],
                      );
                    }
                    !setSelectedOptions && setShowOptions(false);
                  }}
                  className="group"
                >
                  <div className="flex w-full items-center justify-between">
                    <span>{option}</span>
                    {(selectedOptions?.includes(option) ||
                      selectedOption === option) && (
                      <X className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </CommandItem>
              ))}
              {optionsButton}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContentInput>
    </Popover>
  );
};

export default CustomInputPopover;

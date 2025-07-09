import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
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
import { uniqueId } from "lodash";
import { X } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";

const OptionBadge = ({
  option,
  onRemove,
  variant = "emerald",
  className = "",
}: {
  option: string;
  variant?:
    | "default"
    | "emerald"
    | "gray"
    | "secondary"
    | "destructive"
    | "outline"
    | "secondaryStatic"
    | "pinkStatic"
    | "successStatic"
    | "errorStatic";
  className?: string;
  onRemove: (e: React.MouseEvent<HTMLButtonElement>) => void;
}) => (
  <Badge
    variant={
      variant as
        | "default"
        | "emerald"
        | "gray"
        | "secondary"
        | "destructive"
        | "outline"
        | "secondaryStatic"
        | "pinkStatic"
        | "successStatic"
        | "errorStatic"
    }
    className={cn("flex items-center gap-1 truncate", className)}
  >
    <div className="truncate">{option}</div>
    <div
      data-testid="remove-icon-badge"
      onClick={(e) =>
        onRemove(e as unknown as React.MouseEvent<HTMLButtonElement>)
      }
    >
      <X className="h-3 w-3 cursor-pointer bg-transparent hover:text-destructive" />
    </div>
  </Badge>
);

const CommandItemContent = ({
  option,
  isSelected,
  optionButton,
  nodeStyle,
  commandWidth,
}: {
  option: string;
  isSelected: boolean;
  optionButton: (option: string) => ReactNode;
  nodeStyle?: string;
  commandWidth?: string;
}) => (
  <div className="group flex w-full items-center justify-between">
    <div className="flex items-center justify-between">
      <SelectionIndicator isSelected={isSelected} />
      <ShadTooltip content={option} side="left">
        <div
          className={cn("w-full truncate pr-2", nodeStyle && "max-w-52")}
          style={{
            maxWidth: commandWidth,
          }}
        >
          <span>{option}</span>
        </div>
      </ShadTooltip>
    </div>
    {optionButton && optionButton(option)}
  </div>
);

const SelectionIndicator = ({ isSelected }: { isSelected: boolean }) => (
  <div
    className={cn(
      "relative mr-2 h-4 w-4",
      isSelected ? "opacity-100" : "opacity-0",
    )}
  >
    <div className="absolute opacity-100 transition-all group-hover:opacity-0">
      <ForwardedIconComponent
        name="Check"
        className="mr-2 h-4 w-4 text-primary"
        aria-hidden="true"
      />
    </div>
    <div className="absolute opacity-0 transition-all group-hover:opacity-100">
      <ForwardedIconComponent
        name="X"
        className="mr-2 h-4 w-4 text-status-red"
        aria-hidden="true"
      />
    </div>
  </div>
);

const getInputClassName = (
  editNode: boolean,
  disabled: boolean,
  password: boolean,
  selectedOptions: string[],
  blockAddNewGlobalVariable: boolean = false,
) => {
  return cn(
    "popover-input nodrag w-full truncate px-1 pr-4",
    editNode && "pl-2 pr-6",
    editNode && disabled && "h-fit w-fit",
    disabled &&
      "disabled:text-muted disabled:opacity-100 placeholder:disabled:text-muted-foreground",
    password && "text-clip pr-14",
    blockAddNewGlobalVariable && "text-clip pr-8",
    selectedOptions?.length > 0 && "cursor-default",
  );
};

const getAnchorClassName = (
  editNode: boolean,
  disabled: boolean,
  isFocused: boolean,
) => {
  return cn(
    "primary-input noflow nopan nodelete nodrag border-1 flex h-full min-h-[2.375rem] cursor-default flex-wrap items-center px-2",
    editNode && "min-h-7 p-0 px-1",
    editNode && disabled && "min-h-5 border-muted",
    disabled && "bg-muted text-muted",
    isFocused &&
      "border-foreground ring-1 ring-foreground hover:border-foreground",
  );
};

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
  optionButton,
  autoFocus,
  popoverWidth,
  commandWidth,
  blockAddNewGlobalVariable,
  hasRefreshButton,
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const memoizedOptions = useMemo(() => new Set<string>(options), [options]);

  const PopoverContentInput = editNode
    ? PopoverContent
    : PopoverContentWithoutPortal;

  const handleRemoveOption = (
    optionToRemove: string,
    e: React.MouseEvent<HTMLButtonElement>,
  ) => {
    e.stopPropagation();
    if (setSelectedOptions) {
      setSelectedOptions(
        selectedOptions.filter((option) => option !== optionToRemove),
      );
    } else if (setSelectedOption) {
      setSelectedOption("");
    }
  };

  const handleOptionSelect = (currentValue: string) => {
    if (setSelectedOption) {
      setSelectedOption(currentValue === selectedOption ? "" : currentValue);
    }
    if (setSelectedOptions) {
      setSelectedOptions(
        selectedOptions?.includes(currentValue)
          ? selectedOptions.filter((item) => item !== currentValue)
          : [...(selectedOptions || []), currentValue],
      );
    }
    !setSelectedOptions && setShowOptions(false);
  };

  return (
    <Popover modal open={showOptions} onOpenChange={setShowOptions}>
      <PopoverAnchor>
        <div
          data-testid={`anchor-${id}`}
          className={getAnchorClassName(editNode, disabled, isFocused)}
          onClick={() => !nodeStyle && !disabled && setShowOptions(true)}
        >
          {!disabled && selectedOptions?.length > 0 ? (
            <div className="mr-5 flex flex-wrap gap-2">
              {selectedOptions.map((option) => (
                <OptionBadge
                  key={option}
                  option={option}
                  onRemove={(e) => handleRemoveOption(option, e)}
                  className="rounded-[3px] p-1 font-mono"
                />
              ))}
            </div>
          ) : !disabled && selectedOption?.length > 0 ? (
            <ShadTooltip content={selectedOption} side="left">
              <div
                style={{
                  maxWidth: commandWidth,
                }}
              >
                <OptionBadge
                  option={selectedOption}
                  onRemove={(e) => handleRemoveOption(selectedOption, e)}
                  variant={nodeStyle ? "emerald" : "secondary"}
                  className={cn(
                    editNode && "text-xs",
                    nodeStyle
                      ? "max-w-56 rounded-[3px] px-1 font-mono"
                      : "bg-muted",
                    hasRefreshButton && "max-w-48",
                  )}
                />
              </div>
            </ShadTooltip>
          ) : null}

          {(!selectedOption?.length && !selectedOptions?.length) || disabled ? (
            <input
              autoComplete="off"
              onFocus={() => setIsFocused(true)}
              autoFocus={autoFocus}
              id={id + uniqueId()}
              ref={refInput}
              type={!pwdVisible && password ? "password" : "text"}
              onBlur={() => {
                onInputLostFocus?.();
                setIsFocused(false);
              }}
              value={disabled ? "" : value || ""}
              disabled={disabled}
              required={required}
              className={getInputClassName(
                editNode,
                disabled,
                password,
                selectedOptions,
                blockAddNewGlobalVariable,
              )}
              placeholder={
                !disabled && (selectedOptions?.length > 0 || selectedOption)
                  ? ""
                  : placeholder
              }
              onChange={(e) => onChange?.(e.target.value)}
              onKeyDown={(e) => {
                handleKeyDown?.(e);
                if (blurOnEnter && e.key === "Enter") refInput.current?.blur();
              }}
              data-testid={editNode ? id + "-edit" : id}
            />
          ) : null}
        </div>
      </PopoverAnchor>

      <PopoverContentInput
        className="noflow nowheel nopan nodelete nodrag p-0"
        style={{
          minWidth: refInput?.current?.clientWidth ?? "200px",
          width: popoverWidth ?? null,
        }}
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
              {Array.from(memoizedOptions).map((option, id) => (
                <CommandItem
                  key={option + id}
                  value={option}
                  onSelect={handleOptionSelect}
                  className="group"
                >
                  <CommandItemContent
                    option={option}
                    isSelected={
                      selectedOption === option ||
                      selectedOptions?.includes(option)
                    }
                    optionButton={optionButton}
                    nodeStyle={nodeStyle}
                    commandWidth={commandWidth}
                  />
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

import { PopoverAnchor } from "@radix-ui/react-popover";
import { useEffect } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
} from "@/components/ui/popover";
import { classNames, cn } from "@/utils/utils";
import { useIMEInputForOnChange } from "../../../../hooks/use-ime-input";

const CustomInputPopoverObject = ({
  id,
  refInput,
  onInputLostFocus,
  selectedOption,
  setSelectedOption,
  selectedOptions,
  setSelectedOptions,
  value,
  autoFocus,
  disabled,
  setShowOptions,
  required,
  editNode,
  className,
  placeholder,
  onChange,
  blurOnEnter,
  options,
  optionsPlaceholder,
  optionButton,
  optionsButton,
  handleKeyDown,
  showOptions,
  inspectionPanel,
}) => {
  const PopoverContentInput =
    editNode || inspectionPanel ? PopoverContent : PopoverContentWithoutPortal;

  const {
    displayValue,
    inputProps: imeInputProps,
    flushPendingComposition,
    cancelComposition,
  } = useIMEInputForOnChange<HTMLInputElement>({
    value,
    onChange,
    inputRef: refInput,
  });

  const isSingleSelectionMode =
    (selectedOption !== "" || !onChange) && setSelectedOption;
  const isMultiSelectionMode =
    (selectedOptions?.length !== 0 || !onChange) && setSelectedOptions;
  const isSelectionMode = isSingleSelectionMode || isMultiSelectionMode;

  // Selection-mode renders the input as readOnly with imeInputProps skipped.
  // If we toggled into selection-mode mid-composition, the IME handlers are
  // gone and `compositionend` will never reset the stuck flag — clear it now
  // so a later text-mode swap doesn't drop plain keystrokes.
  useEffect(() => {
    if (isSelectionMode) cancelComposition();
  }, [isSelectionMode, cancelComposition]);

  const selectionDisplay = isSingleSelectionMode
    ? options?.find((option) => option.id === selectedOption)?.name || ""
    : isMultiSelectionMode
      ? (selectedOptions ?? [])
          .map(
            (optionId) =>
              options?.find((option) => option.id === optionId)?.name,
          )
          .join(", ")
      : "";

  return (
    <Popover modal open={showOptions} onOpenChange={setShowOptions}>
      <PopoverAnchor>
        <Input
          id={id}
          ref={refInput}
          type="text"
          {...(isSelectionMode ? {} : imeInputProps)}
          onBlur={(event) => {
            if (!isSelectionMode) flushPendingComposition();
            onInputLostFocus?.(event);
          }}
          readOnly={Boolean(isSelectionMode) || undefined}
          value={isSelectionMode ? selectionDisplay : displayValue}
          autoFocus={autoFocus}
          disabled={disabled}
          onClick={() => {
            (((selectedOption !== "" || !onChange) && setSelectedOption) ||
              ((selectedOptions?.length !== 0 || !onChange) &&
                setSelectedOptions)) &&
              setShowOptions(true);
          }}
          required={required}
          className={classNames(className!)}
          placeholder={placeholder}
          onKeyDown={(e) => {
            handleKeyDown(e);
            if (blurOnEnter && e.key === "Enter") refInput.current?.blur();
          }}
          data-testid={id}
        />
      </PopoverAnchor>
      <PopoverContentInput
        className="noflow nowheel nopan nodelete nodrag p-0"
        style={{ minWidth: refInput?.current?.clientWidth ?? "200px" }}
        side="bottom"
        avoidCollisions={inspectionPanel || editNode}
        align="center"
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
            <CommandGroup defaultChecked={false}>
              {(options ?? []).map((option, index) => (
                <CommandItem
                  className="group"
                  key={option.id}
                  value={option.id}
                  onSelect={(currentValue) => {
                    setSelectedOption &&
                      setSelectedOption(
                        currentValue === selectedOption ? "" : currentValue,
                      );
                    setSelectedOptions &&
                      setSelectedOptions(
                        selectedOptions?.includes(currentValue)
                          ? selectedOptions.filter(
                              (item) => item !== currentValue,
                            )
                          : [...selectedOptions, currentValue],
                      );
                    !setSelectedOptions && setShowOptions(false);
                  }}
                >
                  <div className="group flex w-full items-center justify-between">
                    <div className="flex items-center">
                      <div
                        className={cn(
                          "relative mr-2 h-4 w-4",
                          selectedOption === option.id ||
                            selectedOptions?.includes(option.id)
                            ? "opacity-100"
                            : "opacity-0",
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
                      <span data-testid={`option-${index}`}>
                        {option.name}{" "}
                      </span>

                      {/* Display the name property of the option */}
                    </div>
                    {optionButton && optionButton(option)}
                  </div>
                </CommandItem>
              ))}
              {optionsButton && optionsButton}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContentInput>
    </Popover>
  );
};

export default CustomInputPopoverObject;

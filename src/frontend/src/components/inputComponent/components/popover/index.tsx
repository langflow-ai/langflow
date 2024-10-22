import { PopoverAnchor } from "@radix-ui/react-popover";
import { useEffect, useRef, useState } from "react";
import useAlertStore from "../../../../stores/alertStore";
import { cn } from "../../../../utils/utils";
import ForwardedIconComponent from "../../../genericIconComponent";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "../../../ui/command";
import { Input } from "../../../ui/input";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
} from "../../../ui/popover";
import { getInputClassName } from "../helpers/get-input-class-name";

const CustomInputPopover = ({
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
  className,
  password,
  pwdVisible,
  editNode,
  placeholder,
  onChange,
  blurOnEnter,
  options,
  optionsPlaceholder,
  optionButton,
  optionsButton,
  handleKeyDown,
  showOptions,
  nodeStyle,
}) => {
  const setErrorData = useAlertStore.getState().setErrorData;
  const PopoverContentInput = editNode
    ? PopoverContent
    : PopoverContentWithoutPortal;

  const handleInputChange = (e) => {
    if (password) {
      if (
        e.target.value.split("").every((char) => char === "•") &&
        e.target.value !== ""
      ) {
        setErrorData({
          title: `Invalid characters: ${e.target.value}`,
          list: [
            "It seems you are trying to paste a password. Make sure the value is visible before copying from another field.",
          ],
        });
      }
    }
    onChange && onChange(e.target.value);
  };

  const isSelected = (selectedOption !== "" || !onChange) && setSelectedOption;
  const areOptionsSelected =
    (selectedOptions?.length !== 0 || !onChange) && setSelectedOptions;

  const [inputWidth, setInputWidth] = useState(25);

  useEffect(() => {
    setInputWidth(
      selectedOption?.length > 25
        ? selectedOption?.length * 8
        : selectedOption?.length * 10,
    );
  }, [selectedOption]);

  return (
    <Popover modal open={showOptions} onOpenChange={setShowOptions}>
      <PopoverAnchor>
        <Input
          id={id}
          ref={refInput}
          type="text"
          onBlur={onInputLostFocus}
          value={
            isSelected
              ? selectedOption
              : areOptionsSelected
                ? selectedOptions?.join(", ")
                : value
          }
          autoFocus={autoFocus}
          onClick={() => {
            (isSelected || areOptionsSelected) && setShowOptions(true);
          }}
          disabled={disabled}
          required={required}
          className={getInputClassName({
            disabled,
            password,
            setSelectedOption,
            selectedOption,
            pwdVisible,
            value,
            editNode,
            setSelectedOptions,
            isSelected,
            areOptionsSelected,
            nodeStyle,
            className,
          })}
          placeholder={password && editNode ? "Key" : placeholder}
          onChange={handleInputChange}
          onKeyDown={(e) => {
            handleKeyDown(e);
            if (blurOnEnter && e.key === "Enter") refInput.current?.blur();
          }}
          data-testid={editNode ? id + "-edit" : id}
        />
        {value && selectedOption !== "" && nodeStyle && (
          <div
            className="pointer-events-none absolute left-1 top-1 h-[calc(100%-9px)] rounded-sm bg-accent-emerald-foreground bg-emerald-100 opacity-30"
            style={{ width: `${inputWidth}px` }}
          />
        )}
      </PopoverAnchor>
      <PopoverContentInput
        className="noflow nowheel nopan nodelete nodrag p-0"
        style={{ minWidth: refInput?.current?.clientWidth ?? "200px" }}
        side="bottom"
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
              {options.map((option, id) => (
                <CommandItem
                  className="group"
                  key={option + id}
                  value={option}
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
                          selectedOption === option ||
                            selectedOptions?.includes(option)
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

                      {option}
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

export default CustomInputPopover;

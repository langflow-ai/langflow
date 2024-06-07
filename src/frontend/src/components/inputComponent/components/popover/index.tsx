import { PopoverAnchor } from "@radix-ui/react-popover";
import useAlertStore from "../../../../stores/alertStore";
import { classNames, cn } from "../../../../utils/utils";
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
  return (
    <Popover modal open={showOptions} onOpenChange={setShowOptions}>
      <PopoverAnchor>
        <Input
          id={id}
          ref={refInput}
          type="text"
          onBlur={onInputLostFocus}
          value={
            (selectedOption !== "" || !onChange) && setSelectedOption
              ? selectedOption
              : (selectedOptions?.length !== 0 || !onChange) &&
                  setSelectedOptions
                ? selectedOptions?.join(", ")
                : value
          }
          autoFocus={autoFocus}
          disabled={disabled}
          onClick={() => {
            (((selectedOption !== "" || !onChange) && setSelectedOption) ||
              ((selectedOptions?.length !== 0 || !onChange) &&
                setSelectedOptions)) &&
              setShowOptions(true);
          }}
          required={required}
          className={classNames(
            password &&
              (!setSelectedOption || selectedOption === "") &&
              !pwdVisible &&
              value !== ""
              ? " text-clip password "
              : "",
            editNode ? " input-edit-node " : "",
            password && (setSelectedOption || setSelectedOptions)
              ? "pr-[62.9px]"
              : "",
            (!password && (setSelectedOption || setSelectedOptions)) ||
              (password && !(setSelectedOption || setSelectedOptions))
              ? "pr-8"
              : "",
            className!,
          )}
          placeholder={password && editNode ? "Key" : placeholder}
          onChange={handleInputChange}
          onKeyDown={(e) => {
            handleKeyDown(e);
            if (blurOnEnter && e.key === "Enter") refInput.current?.blur();
          }}
          data-testid={editNode ? id + "-edit" : id}
        />
      </PopoverAnchor>
      <PopoverContentInput
        className="nocopy nowheel nopan nodelete nodrag noundo p-0"
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

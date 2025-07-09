import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";
import {
  NumberDecrementStepper,
  NumberIncrementStepper,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
} from "@chakra-ui/number-input";
import { MinusIcon, PlusIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { handleKeyDown } from "../../../../../utils/reactflowUtils";
import type { InputProps, IntComponentType } from "../../types";

export default function IntComponent({
  value,
  handleOnNewValue,
  rangeSpec,
  disabled,
  editNode = false,
  id = "",
  readonly,
}: InputProps<number, IntComponentType>): JSX.Element {
  const min = -Infinity;
  // Clear component state
  useEffect(() => {
    if (disabled && value !== 0) {
      handleOnNewValue({ value: 0 }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue]);

  const [cursor, setCursor] = useState<number | null>(null);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    ref.current?.setSelectionRange(cursor, cursor);
  }, [ref, cursor, value]);

  const handleChangeInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCursor(e.target.selectionStart);
    handleOnNewValue({ value: Number(e.target.value) });
  };

  const getStepValue = () => {
    return (Number.isInteger(rangeSpec?.step) ? rangeSpec.step : 1) ?? 1;
  };

  const getMinValue = () => {
    return rangeSpec?.min ?? min;
  };

  const getMaxValue = () => {
    return rangeSpec?.max ?? undefined;
  };

  const getInputClassName = () => {
    return cn(
      editNode ? "input-edit-node" : "",
      "nopan nodelete nodrag noflow primary-input ",
    );
  };

  const DISABLED_INPUT_CLASS =
    "cursor-default bg-secondary border-border border rounded-md py-2 px-3 text-sm text-input placeholder:text-input";

  const handleNumberChange = (newValue) => {
    handleOnNewValue({ value: Number(newValue) });
  };

  const handleInputChange = (event) => {
    const inputValue = Number(event.target.value);
    if (inputValue < getMinValue()) {
      event.target.value = getMinValue().toString();
    }
  };

  const iconClassName =
    "text-placeholder-foreground h-3 w-3 group-increment-hover:text-primary group-decrement-hover:text-primary transition-colors";
  const stepperClassName = " w-5 rounded-r-sm border-l-[1px]";
  const incrementStepperClassName =
    " border-b-[1px] hover:rounded-tr-[5px] hover:bg-muted group-increment";
  const decrementStepperClassName =
    " hover:rounded-br-[5px] hover:bg-muted group-decrement";
  const inputRef = useRef(null);

  return (
    <div className="w-full">
      <NumberInput
        id={id}
        step={getStepValue()}
        min={getMinValue()}
        max={getMaxValue()}
        onChange={handleNumberChange}
        isDisabled={disabled || readonly}
        value={value ?? ""}
      >
        <NumberInputField
          className={
            disabled || readonly ? DISABLED_INPUT_CLASS : getInputClassName()
          }
          onChange={handleChangeInput}
          onKeyDown={(event) => handleKeyDown(event, value, "")}
          onInput={handleInputChange}
          disabled={disabled || readonly}
          placeholder={editNode ? "Integer number" : "Type an integer number"}
          data-testid={id}
          ref={inputRef}
        />
        <NumberInputStepper className={stepperClassName}>
          <NumberIncrementStepper
            className={incrementStepperClassName}
            _disabled={{ cursor: "default" }}
          >
            <PlusIcon
              className={iconClassName}
              strokeWidth={ICON_STROKE_WIDTH}
            />
          </NumberIncrementStepper>
          <NumberDecrementStepper
            className={decrementStepperClassName}
            _disabled={{ cursor: "default" }}
          >
            <MinusIcon
              className={iconClassName}
              strokeWidth={ICON_STROKE_WIDTH}
            />
          </NumberDecrementStepper>
        </NumberInputStepper>
      </NumberInput>
    </div>
  );
}

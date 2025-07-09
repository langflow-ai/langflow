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
import type { FloatComponentType, InputProps } from "../../types";

export default function FloatComponent({
  value,
  handleOnNewValue,
  rangeSpec,
  disabled,
  editNode = false,
  id = "",
}: InputProps<number, FloatComponentType>): JSX.Element {
  const step = rangeSpec?.step ?? 0.1;
  const min = rangeSpec?.min;
  const max = rangeSpec?.max;

  // Local state for input value
  const [localValue, setLocalValue] = useState<string>(value.toString());

  // Clear component state
  useEffect(() => {
    if (disabled && value !== 0) {
      handleOnNewValue({ value: 0 }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue]);

  // Update local value when prop changes
  useEffect(() => {
    setLocalValue(value.toString());
  }, [value]);

  const [cursor, setCursor] = useState<number | null>(null);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    ref.current?.setSelectionRange(cursor, cursor);
  }, [ref, cursor, localValue]);

  const handleChangeInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCursor(e.target.selectionStart);
    setLocalValue(e.target.value);
  };

  const handleBlur = () => {
    handleOnNewValue({ value: Number(localValue) });
  };

  const handleNumberChange = (newValue) => {
    setLocalValue(newValue);
  };

  const handleInputChange = (event) => {
    const inputValue = Number(event.target.value);
    if (inputValue < min) {
      event.target.value = min.toString();
    } else if (inputValue > max) {
      event.target.value = max.toString();
    }
  };

  const getInputClassName = () => {
    return cn(
      editNode ? "input-edit-node" : "",
      "nopan nodelete nodrag noflow primary-input",
    );
  };

  const iconClassName =
    "text-placeholder-foreground h-3 w-3 group-increment-hover:text-primary group-decrement-hover:text-primary transition-colors";
  const stepperClassName = "w-5 rounded-r-sm border-l-[1px]";
  const incrementStepperClassName =
    "border-b-[1px] hover:rounded-tr-[5px] hover:bg-muted group-increment";
  const decrementStepperClassName =
    "hover:rounded-br-[5px] hover:bg-muted group-decrement";
  const inputRef = useRef(null);

  return (
    <div className="w-full">
      <NumberInput
        id={id}
        step={step}
        min={min}
        max={max}
        onChange={handleNumberChange}
        value={localValue ?? ""}
        onBlur={handleBlur}
      >
        <NumberInputField
          className={getInputClassName()}
          onChange={handleChangeInput}
          onKeyDown={(event) => handleKeyDown(event, localValue, "")}
          onInput={handleInputChange}
          disabled={disabled}
          placeholder={editNode ? "Float number" : "Type a float number"}
          data-testid={id}
          ref={inputRef}
          onBlur={handleBlur}
        />
        <NumberInputStepper className={stepperClassName}>
          <NumberIncrementStepper className={incrementStepperClassName}>
            <PlusIcon className={iconClassName} />
          </NumberIncrementStepper>
          <NumberDecrementStepper className={decrementStepperClassName}>
            <MinusIcon className={iconClassName} />
          </NumberDecrementStepper>
        </NumberInputStepper>
      </NumberInput>
    </div>
  );
}

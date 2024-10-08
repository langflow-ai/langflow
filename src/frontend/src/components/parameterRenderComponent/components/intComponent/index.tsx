import { cn } from "@/utils/utils";
import {
  NumberDecrementStepper,
  NumberIncrementStepper,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
} from "@chakra-ui/number-input";
import { useEffect, useRef, useState } from "react";
import { handleKeyDown } from "../../../../utils/reactflowUtils";
import { InputProps, IntComponentType } from "../../types";

export default function IntComponent({
  value,
  handleOnNewValue,
  rangeSpec,
  disabled,
  editNode = false,
  id = "",
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
      "nopan nodelete nodrag noflow primary-input",
    );
  };

  const handleNumberChange = (newValue) => {
    handleOnNewValue({ value: Number(newValue) });
  };

  const handleInputChange = (event) => {
    const inputValue = Number(event.target.value);
    if (inputValue < getMinValue()) {
      event.target.value = getMinValue().toString();
    }
  };

  const inputRef = useRef(null);

  return (
    <div className="w-full">
      <NumberInput
        id={id}
        step={getStepValue()}
        min={getMinValue()}
        max={getMaxValue()}
        onChange={handleNumberChange}
        value={value ?? ""}
      >
        <NumberInputField
          className={getInputClassName()}
          onChange={handleChangeInput}
          onKeyDown={(event) => handleKeyDown(event, value, "")}
          onInput={handleInputChange}
          disabled={disabled}
          placeholder={editNode ? "Integer number" : "Type an integer number"}
          data-testid={id}
          ref={inputRef}
        />
        <NumberInputStepper paddingRight={10}>
          <NumberIncrementStepper fontSize={8} marginTop={6} />
          <NumberDecrementStepper fontSize={8} marginBottom={6} />
        </NumberInputStepper>
      </NumberInput>
    </div>
  );
}

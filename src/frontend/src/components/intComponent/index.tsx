import { cn } from "@/utils/utils";
import {
  NumberDecrementStepper,
  NumberIncrementStepper,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
} from "@chakra-ui/number-input";
import { useEffect, useRef, useState } from "react";
import { IntComponentType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";

export default function IntComponent({
  value,
  onChange,
  rangeSpec,
  disabled,
  editNode = false,
  id = "",
}: IntComponentType): JSX.Element {
  const min = -Infinity;
  // Clear component state
  useEffect(() => {
    if (disabled && value !== 0) {
      onChange(0, undefined, true);
    }
  }, [disabled, onChange]);

  const [cursor, setCursor] = useState<number | null>(null);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    ref.current?.setSelectionRange(cursor, cursor);
  }, [ref, cursor, value]);

  const handleChangeInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCursor(e.target.selectionStart);
    onChange(Number(e.target.value));
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
    onChange(Number(newValue));
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

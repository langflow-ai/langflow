import {
  NumberDecrementStepper,
  NumberIncrementStepper,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
} from "@chakra-ui/number-input";
import { MinusIcon, PlusIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";
import { handleKeyDown } from "../../../../../utils/reactflowUtils";
import type { InputProps, IntComponentType } from "../../types";

export default function IntComponent({
  value,
  handleOnNewValue,
  rangeSpec,
  name,
  disabled,
  editNode = false,
  id = "",
  readonly,
  showParameter = true,
}: InputProps<number, IntComponentType>): JSX.Element | null {
  const min = -Infinity;
  // Clear component state when disabled
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

  const parseAndValidate = (raw: string): number | null => {
    const trimmed = raw.trim();
    if (trimmed === "") return null;
    const num = Number(trimmed);
    if (!Number.isFinite(num) || !Number.isInteger(num)) return null;
    const minVal = getMinValue();
    const maxVal = getMaxValue();
    if (num < minVal) return minVal;
    if (maxVal !== undefined && num > maxVal) return maxVal;
    return num;
  };

  const handleChangeInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCursor(e.target.selectionStart ?? null);
    const raw = e.target.value;
    const parsed = parseAndValidate(raw);
    handleOnNewValue({
      value: parsed !== null ? parsed : (null as unknown as number),
    });
  };

  const getStepValue = () => {
    return (Number.isInteger(rangeSpec?.step) ? rangeSpec.step : 1) ?? 1;
  };

  const getMinValue = () => {
    // max_tokens must be at least 1; enforce even when rangeSpec is missing (e.g. saved flows)
    if (name === "max_tokens") {
      return rangeSpec?.min ?? 1;
    }
    return rangeSpec?.min ?? min;
  };

  const getMaxValue = () => {
    return rangeSpec?.max ?? undefined;
  };

  const minVal = getMinValue();
  const isAtOrBelowMin =
    typeof minVal === "number" &&
    Number.isFinite(minVal) &&
    (value == null || value <= minVal);

  // Clamp existing out-of-range values to min on load (e.g. max_tokens -14 -> 1).
  // For max_tokens, 0 means "empty/no limit" — do not clamp 0 to 1.
  useEffect(() => {
    if (
      typeof minVal === "number" &&
      Number.isFinite(minVal) &&
      typeof value === "number" &&
      value < minVal &&
      !(name === "max_tokens" && value === 0)
    ) {
      handleOnNewValue({ value: minVal }, { skipSnapshot: true });
    }
  }, [minVal, value, handleOnNewValue, name]);

  const getInputClassName = () => {
    return cn(
      editNode ? "input-edit-node" : "",
      "nopan nodelete nodrag noflow primary-input ",
    );
  };

  const DISABLED_INPUT_CLASS =
    "cursor-default bg-secondary border-border border rounded-md py-2 px-3 text-sm text-input placeholder:text-input";

  const handleNumberChange = (newValue: string | number) => {
    if (newValue === "" || newValue === undefined) {
      handleOnNewValue({ value: null as unknown as number });
      return;
    }
    const num = Number(newValue);
    if (!Number.isFinite(num)) {
      handleOnNewValue({ value: null as unknown as number });
      return;
    }
    const minVal = getMinValue();
    const maxVal = getMaxValue();
    let clamped = Math.round(num);
    if (clamped < minVal) clamped = minVal;
    if (maxVal !== undefined && clamped > maxVal) clamped = maxVal;
    handleOnNewValue({ value: clamped });
  };

  const handleInputChange = (event: React.FormEvent<HTMLInputElement>) => {
    const inputValue = Number((event.target as HTMLInputElement).value);
    if (Number.isFinite(inputValue) && inputValue < getMinValue()) {
      (event.target as HTMLInputElement).value = getMinValue().toString();
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

  if (!showParameter) {
    return null;
  }

  return (
    <div className="w-full">
      <NumberInput
        id={id}
        step={getStepValue()}
        min={getMinValue()}
        max={getMaxValue()}
        onChange={handleNumberChange}
        isDisabled={disabled || readonly}
        value={
          name === "max_tokens" && (value === 0 || value === null)
            ? ""
            : (value ?? "")
        }
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
            isDisabled={isAtOrBelowMin}
            onClickCapture={
              isAtOrBelowMin
                ? (e: React.MouseEvent) => {
                    e.preventDefault();
                    e.stopPropagation();
                  }
                : undefined
            }
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
